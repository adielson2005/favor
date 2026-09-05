"""Pre-migration dry-run — read-only against MongoDB, never writes anything, never
touches Postgres. Three checks, all driven by the actual SQLAlchemy schema
(app.db.models) so they can't silently drift from what etl/run.py will enforce:

1. Orphaned foreign keys: for every real FK in the Postgres schema, scan the
   source Mongo collection for values that don't exist in the target collection.
   A hard FK violates on load; better to know the exact count and examples now.
2. Duplicate idempotency keys: collections that get a UNIQUE constraint on
   idempotency_key (wallet_transactions, deposits, withdrawals, payments) — a
   duplicate here would abort the whole load partway through.
3. Money-rounding sanity: every reais-float field that becomes a BIGINT cents
   column (see etl/money_fields.py) gets checked for values that don't round
   cleanly to the nearest cent — flags float artifacts before they become silent
   off-by-one-cent errors.

Usage (from backend/, MUST be run against the isolated environment):
    ENV_FILE=.env.isolated ./venv/Scripts/python.exe -m etl.checks
"""
import asyncio
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: E402,F401
from database import db  # noqa: E402
from etl.money_fields import MONEY_FIELDS  # noqa: E402

# Postgres table name -> Mongo collection name. Tables absent from this map have
# no direct Mongo source (order_photos, dispute_evidence, service_status_history,
# ticket_messages are all extracted from a parent document's array by etl/run.py,
# not loaded from a same-named collection) and are skipped by the orphan scan.
TABLE_TO_COLLECTION = {
    "states": "states", "cities": "cities", "neighborhoods": "neighborhoods",
    "categories": "categories", "subcategories": "subcategories",
    "users": "users", "auth_accounts": "auth_accounts", "verification_tokens": "verification_tokens",
    "orders": "orders", "proposals": "proposals", "messages": "messages", "reviews": "reviews",
    "reports": "reports", "blocks": "blocks", "favorites": "favorites", "notifications": "notifications",
    "wallets": "wallets", "wallet_transactions": "wallet_transactions", "deposits": "deposits",
    "bank_accounts": "bank_accounts", "withdrawals": "withdrawals", "payments": "payments",
    "payment_events": "payment_events", "disputes": "disputes", "risk_flags": "risk_flags",
    "security_events": "security_events", "tickets": "tickets",
    "admin_users": "admin_users", "admin_roles": "admin_roles", "admin_actions": "admin_actions",
    "feature_flags": "feature_flags", "system_settings": "platform_config",
}

# The Mongo field that holds each collection's natural primary key — "id" for
# almost everything, except admin_roles/feature_flags which use "key" (seed.py).
KEY_FIELD = {"admin_roles": "key", "feature_flags": "key"}

# String constants used directly as a foreign-key value with no matching Mongo
# users doc (see identity.py's docstring) — never flag these as orphans.
SYNTHESIZED_IDS = {"users": {"platform", "system"}}

IDEMPOTENCY_KEY_COLLECTIONS = ["wallet_transactions", "deposits", "withdrawals", "payments"]


def _require_isolated_db() -> None:
    name = db.name
    if name != "faze_isolated":
        raise RuntimeError(
            f"Recusando rodar contra o banco '{name}'. Este script só pode ler de "
            f"'faze_isolated' — rode com ENV_FILE=.env.isolated."
        )


async def check_orphaned_foreign_keys() -> list[dict]:
    findings = []
    for table in Base.metadata.tables.values():
        local_name = table.name
        if local_name not in TABLE_TO_COLLECTION:
            continue
        for fk_constraint in table.foreign_key_constraints:
            if len(fk_constraint.columns) != 1:
                continue  # no composite FKs in this schema
            local_col = next(iter(fk_constraint.columns)).name
            fk = next(iter(fk_constraint.elements))
            target_table = fk.column.table.name
            target_col = fk.column.name
            if target_table not in TABLE_TO_COLLECTION:
                continue

            source_coll = TABLE_TO_COLLECTION[local_name]
            target_coll = TABLE_TO_COLLECTION[target_table]
            target_key_field = KEY_FIELD.get(target_table, "id")

            source_values = set(await db[source_coll].distinct(local_col))
            source_values.discard(None)
            if not source_values:
                continue
            target_values = set(await db[target_coll].distinct(target_key_field))
            exempt = SYNTHESIZED_IDS.get(target_table, set())

            orphans = source_values - target_values - exempt
            if orphans:
                findings.append({
                    "relation": f"{local_name}.{local_col} -> {target_table}.{target_col}",
                    "orphan_count": len(orphans),
                    "examples": sorted(orphans)[:5],
                })
    return findings


async def check_duplicate_idempotency_keys() -> list[dict]:
    findings = []
    for coll_name in IDEMPOTENCY_KEY_COLLECTIONS:
        pipeline = [
            {"$match": {"idempotency_key": {"$ne": None}}},
            {"$group": {"_id": "$idempotency_key", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        dupes = await db[coll_name].aggregate(pipeline).to_list(50)
        if dupes:
            findings.append({
                "collection": coll_name,
                "duplicate_key_count": len(dupes),
                "examples": [d["_id"] for d in dupes[:5]],
            })
    return findings


async def check_money_rounding() -> list[dict]:
    findings = []
    for coll_name, fields in MONEY_FIELDS.items():
        for mongo_field, pg_column in fields:
            bad = []
            cursor = db[coll_name].find({mongo_field: {"$ne": None}}, {"id": 1, mongo_field: 1})
            async for doc in cursor:
                value = doc.get(mongo_field)
                if value is None:
                    continue
                cents = Decimal(str(value)) * 100
                rounded = cents.to_integral_value(rounding=ROUND_HALF_UP)
                if abs(cents - rounded) > Decimal("0.0001"):
                    bad.append({"id": doc.get("id"), "value": value})
            if bad:
                findings.append({
                    "collection": coll_name, "field": mongo_field, "target_column": pg_column,
                    "bad_count": len(bad), "examples": bad[:5],
                })
    return findings


async def main() -> None:
    _require_isolated_db()
    print(f"Rodando dry-run contra '{db.name}' (read-only, nada é escrito).\n")

    print("=== 1. Chaves estrangeiras órfãs ===")
    fk_findings = await check_orphaned_foreign_keys()
    if not fk_findings:
        print("Nenhuma referência órfã encontrada.")
    for f in fk_findings:
        print(f"  {f['relation']}: {f['orphan_count']} órfã(s) — exemplos: {f['examples']}")

    print("\n=== 2. idempotency_key duplicada ===")
    dup_findings = await check_duplicate_idempotency_keys()
    if not dup_findings:
        print("Nenhuma chave de idempotência duplicada encontrada.")
    for f in dup_findings:
        print(f"  {f['collection']}: {f['duplicate_key_count']} chave(s) duplicada(s) — exemplos: {f['examples']}")

    print("\n=== 3. Sanidade de arredondamento monetário (reais -> centavos) ===")
    money_findings = await check_money_rounding()
    if not money_findings:
        print("Nenhum valor com problema de arredondamento encontrado.")
    for f in money_findings:
        print(f"  {f['collection']}.{f['field']} -> {f['target_column']}: {f['bad_count']} valor(es) suspeito(s) — exemplos: {f['examples']}")

    total = len(fk_findings) + len(dup_findings) + len(money_findings)
    print(f"\n{'PROBLEMAS ENCONTRADOS' if total else 'OK'}: {total} categoria(s) de achado(s) não-vazia(s).")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    asyncio.run(main())
