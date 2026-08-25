"""Offline, additive MongoDB -> PostgreSQL staging migrator.

It never changes MongoDB and never enables PostgreSQL in the API.  It first creates a
compressed Mongo dump, then copies every document from every runtime collection to
a lossless JSONB staging area.  Re-running with the same source fingerprint is safe.
Run only against a restored backup or a maintenance-window snapshot.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from bson import json_util
from motor.motor_asyncio import AsyncIOMotorClient

COLLECTIONS = (
    "users", "auth_accounts", "verification_tokens", "security_events",
    "states", "cities", "neighborhoods", "categories", "subcategories",
    "orders", "proposals", "messages", "reviews", "reports", "blocks",
    "favorites", "notifications", "wallets", "wallet_transactions",
    "deposits", "bank_accounts", "withdrawals", "payments", "payment_events",
    "disputes", "risk_flags", "platform_config", "admin_users", "admin_roles",
    "admin_actions", "feature_flags", "tickets",
)
SOURCE_NAME = "mongodb"
BATCH_SIZE = 500


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be set in the environment.")
    return value


def canonical_document(document: dict[str, Any]) -> tuple[str, str, str, datetime | None]:
    # bson.json_util makes ObjectId/date values lossless and deterministic enough for
    # source hashes. IDs created by this app are document['id']; _id is a fallback.
    legacy_id = str(document.get("id") or document["_id"])
    payload = json.loads(json_util.dumps(document, sort_keys=True))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    raw_created = document.get("created_at")
    created_at = None
    if isinstance(raw_created, datetime):
        created_at = raw_created
    elif isinstance(raw_created, str):
        try:
            created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
        except ValueError:
            pass
    return legacy_id, hashlib.sha256(encoded.encode("utf-8")).hexdigest(), encoded, created_at


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def create_backup(mongo_uri: str, backup_dir: Path) -> Path:
    """Create an encrypted-at-rest destination on your backup volume before calling this."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    archive = backup_dir / f"fazum-mongo-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.archive.gz"
    # mongodump config prevents the URI (and its password) from appearing in the process list.
    fd, config_name = tempfile.mkstemp(prefix="fazum-mongodump-", suffix=".yml")
    os.close(fd)
    config = Path(config_name)
    try:
        config.write_text("uri: " + json.dumps(mongo_uri) + "\n", encoding="utf-8")
        subprocess.run(["mongodump", "--config", str(config), "--archive=" + str(archive), "--gzip"],
                       check=True, capture_output=True, text=True)
    finally:
        config.unlink(missing_ok=True)
    if not archive.exists() or archive.stat().st_size == 0:
        raise RuntimeError("mongodump did not create a usable archive.")
    return archive


async def snapshot_fingerprint(mongo_db) -> tuple[str, dict[str, int]]:
    counts = {collection: await mongo_db[collection].count_documents({}) for collection in COLLECTIONS}
    # Counts are a fast, stable resume key. A new write changes the high-water fingerprint
    # and forces a new run rather than silently mixing snapshots.
    packed = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode()).hexdigest(), counts


async def get_or_start_run(pg, fingerprint: str, counts: dict[str, int], backup_sha256: str) -> asyncpg.Record:
    row = await pg.fetchrow(
        """INSERT INTO migration_runs(source, source_fingerprint, status, details)
           VALUES($1,$2,'RUNNING',$3::jsonb)
           ON CONFLICT(source,source_fingerprint)
           DO UPDATE SET details = migration_runs.details || EXCLUDED.details
           RETURNING id,status,details""",
        SOURCE_NAME, fingerprint, json.dumps({"source_counts": counts, "backup_sha256": backup_sha256}),
    )
    if row["status"] in ("COMPLETED", "ROLLED_BACK"):
        raise RuntimeError(f"Refusing to change a {row['status']} migration run.")
    return row


async def stage_collection(mongo_db, pg, run_id, collection: str) -> int:
    staged = 0
    cursor = mongo_db[collection].find({}, no_cursor_timeout=True).batch_size(BATCH_SIZE)
    async for document in cursor:
        legacy_id, source_hash, payload, source_created_at = canonical_document(document)
        await pg.execute(
            """INSERT INTO migration_staging
               (migration_run_id,collection_name,legacy_id,source_hash,payload,source_created_at)
               VALUES($1,$2,$3,$4,$5::jsonb,$6)
               ON CONFLICT(migration_run_id,collection_name,legacy_id)
               DO UPDATE SET source_hash=EXCLUDED.source_hash,payload=EXCLUDED.payload,
                 source_created_at=EXCLUDED.source_created_at,staged_at=now()""",
            run_id, collection, legacy_id, source_hash, payload, source_created_at,
        )
        staged += 1
    await cursor.close()
    return staged


async def validate(pg, run_id, source_counts: dict[str, int]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for collection, source_count in source_counts.items():
        destination_count = await pg.fetchval(
            "SELECT count(*) FROM migration_staging WHERE migration_run_id=$1 AND collection_name=$2",
            run_id, collection,
        )
        result[collection] = {"source": source_count, "staged": destination_count}
    mismatches = {k: v for k, v in result.items() if v["source"] != v["staged"]}
    if mismatches:
        raise RuntimeError("Staging validation failed: " + json.dumps(mismatches, ensure_ascii=False))
    return result


async def main(args) -> None:
    mongo_uri, postgres_dsn = require_env("MONGO_URL"), require_env("POSTGRES_DSN")
    backup = create_backup(mongo_uri, Path(args.backup_dir))
    backup_sha256 = sha256_file(backup)
    mongo_client = AsyncIOMotorClient(mongo_uri)
    pg = await asyncpg.connect(postgres_dsn)
    run = None
    try:
        mongo_db = mongo_client[require_env("DB_NAME")]
        await mongo_db.command("ping")
        fingerprint, counts = await snapshot_fingerprint(mongo_db)
        run = await get_or_start_run(pg, fingerprint, counts, backup_sha256)
        for collection in COLLECTIONS:
            await stage_collection(mongo_db, pg, run["id"], collection)
        validation = await validate(pg, run["id"], counts)
        await pg.execute(
            "UPDATE migration_runs SET status='VALIDATED',finished_at=now(),details=details || $2::jsonb WHERE id=$1",
            run["id"], json.dumps({"staging_validation": validation, "backup_path": str(backup)}),
        )
        print(json.dumps({"run_id": str(run["id"]), "status": "VALIDATED", "backup": str(backup)}, ensure_ascii=False))
    except Exception as error:
        # Preserve the staged evidence for inspection; status makes the failure explicit.
        if run is not None:
            await pg.execute("UPDATE migration_runs SET status='FAILED',finished_at=now(),details=details || $2::jsonb WHERE id=$1",
                             run["id"], json.dumps({"error": str(error)}))
        raise
    finally:
        await pg.close()
        mongo_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-dir", required=True, help="Encrypted, access-restricted backup directory")
    asyncio.run(main(parser.parse_args()))
