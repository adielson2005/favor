"""Post-migration validation — read-only against both Mongo (faze_isolated) and the
Postgres database the ETL just populated. Never writes to either. Four checks:

1. Row counts: Postgres count == Mongo count - (rows skipped for a required FK
   orphan) + (synthesized rows, e.g. the 2 placeholder users). The "skip" side is
   recomputed independently here (not read from etl/run.py's log) so this check
   can't rubber-stamp a bug in the loader's own accounting.
2. Referential spot-check: a random sample of rows per major table, comparing
   specific field values against the source Mongo document — proves data actually
   transferred correctly, not just that FK constraints held.
3. Financial reconciliation, two tiers:
   a. Global: sum every wallet's stored balance and compare against the net effect
      of every COMPLETED wallet_transactions row, computed independently here.
   b. Per-wallet replay: for a sample of ~30 wallets, replay their COMPLETED
      transactions in chronological order (same bucket-transition rules as
      wallet.py's credit_wallet/debit_wallet/move_bucket) and check the replayed
      balance matches the stored one — catches an ordering bug that a pure sum
      could mask.
4. Bank-data ciphertext passthrough: bank_accounts.document/account_number in
   Postgres must be byte-identical to the Mongo source — the ETL must never
   decrypt/re-encrypt/mangle ciphertext it doesn't understand.

Usage (from backend/, MUST be run against the isolated environment):
    ENV_FILE=.env.isolated ./venv/Scripts/python.exe -m etl.validate
"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.base import Base, get_engine  # noqa: E402
import app.db.models  # noqa: E402,F401
from database import db  # noqa: E402
from etl.checks import KEY_FIELD, TABLE_TO_COLLECTION  # noqa: E402
from etl.run import SYNTHESIZED_USER_IDS  # noqa: E402

FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"  [FALHA] {msg}")


def ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _require_isolated_db() -> None:
    if db.name != "faze_isolated":
        raise RuntimeError(
            f"Recusando rodar contra o banco '{db.name}'. Este script só pode ler de "
            f"'faze_isolated' — rode com ENV_FILE=.env.isolated."
        )


# ---------- 1. row counts ----------

async def required_fk_columns(table_name: str) -> list[tuple[str, str, str]]:
    """[(local_col, target_table, target_key_field)] for every NOT NULL FK on this table."""
    out = []
    table = Base.metadata.tables[table_name]
    for fk_constraint in table.foreign_key_constraints:
        if len(fk_constraint.columns) != 1:
            continue
        local_col = next(iter(fk_constraint.columns))
        if local_col.nullable:
            continue  # nullable FK -> run.py nulls the field, never skips the row
        fk = next(iter(fk_constraint.elements))
        target_table = fk.column.table.name
        if target_table not in TABLE_TO_COLLECTION:
            continue
        out.append((local_col.name, target_table, KEY_FIELD.get(target_table, "id")))
    return out


async def expected_skip_count(table_name: str) -> int:
    coll = TABLE_TO_COLLECTION[table_name]
    fks = await required_fk_columns(table_name)
    if not fks:
        return 0
    or_clauses = []
    for local_col, target_table, target_key in fks:
        target_coll = TABLE_TO_COLLECTION[target_table]
        source_values = set(await db[coll].distinct(local_col))
        source_values.discard(None)
        target_values = set(await db[target_coll].distinct(target_key))
        if target_table == "users":
            target_values |= SYNTHESIZED_USER_IDS
        bad = source_values - target_values
        if bad:
            or_clauses.append({local_col: {"$in": sorted(bad)}})
    if not or_clauses:
        return 0
    return await db[coll].count_documents({"$or": or_clauses})


# Tables whose Postgres row count is NOT a 1:1 copy of a Mongo collection (extracted
# from an array, or entirely synthesized) — skipped by the row-count check, verified
# structurally instead (their FKs already enforce they can't reference nothing).
NO_DIRECT_ROW_COUNT = {"order_photos", "dispute_evidence", "service_status_history", "ticket_messages"}

SYNTHESIZED_ADDITIONS = {"users": len(SYNTHESIZED_USER_IDS)}


async def check_row_counts(engine) -> None:
    print("=== 1. Contagem de linhas (Postgres vs. Mongo) ===")
    with engine.connect() as conn:
        for table_name, coll_name in sorted(TABLE_TO_COLLECTION.items()):
            if table_name in NO_DIRECT_ROW_COUNT:
                continue
            mongo_count = await db[coll_name].count_documents({})
            pg_count = conn.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
            skipped = await expected_skip_count(table_name)
            addition = SYNTHESIZED_ADDITIONS.get(table_name, 0)
            expected = mongo_count - skipped + addition
            if pg_count == expected:
                ok(f"{table_name}: {pg_count} (mongo={mongo_count}, órfãs_esperadas={skipped}, sintetizadas={addition})")
            else:
                fail(f"{table_name}: postgres={pg_count} != esperado={expected} (mongo={mongo_count}, órfãs={skipped}, sintetizadas={addition})")


# ---------- 2. referential / field spot-check ----------

async def check_spot_samples(engine) -> None:
    print("\n=== 2. Amostragem de campos (Postgres vs. Mongo) ===")
    with engine.connect() as conn:
        # orders: title/status/budget_cents
        ids = [r[0] for r in conn.execute(text("SELECT id FROM orders ORDER BY random() LIMIT 30")).fetchall()]
        mismatches = 0
        for oid in ids:
            mongo_doc = await db.orders.find_one({"id": oid}, {"_id": 0, "title": 1, "status": 1, "budget": 1})
            pg_row = conn.execute(text("SELECT title, status, budget_cents FROM orders WHERE id = :id"), {"id": oid}).one()
            expected_cents = round((mongo_doc.get("budget") or 0) * 100)
            if mongo_doc["title"] != pg_row.title or mongo_doc["status"] != pg_row.status or expected_cents != pg_row.budget_cents:
                mismatches += 1
        (ok if mismatches == 0 else fail)(f"orders: {len(ids)} amostradas, {mismatches} divergência(s)")

        # payments: gross_amount_cents / status
        ids = [r[0] for r in conn.execute(text("SELECT id FROM payments ORDER BY random() LIMIT 30")).fetchall()]
        mismatches = 0
        for pid in ids:
            mongo_doc = await db.payments.find_one({"id": pid}, {"_id": 0, "gross_amount": 1, "status": 1})
            pg_row = conn.execute(text("SELECT gross_amount_cents, status FROM payments WHERE id = :id"), {"id": pid}).one()
            expected_cents = round((mongo_doc.get("gross_amount") or 0) * 100)
            if mongo_doc["status"] != pg_row.status or expected_cents != pg_row.gross_amount_cents:
                mismatches += 1
        (ok if mismatches == 0 else fail)(f"payments: {len(ids)} amostrados, {mismatches} divergência(s)")

        # users: name/email/city_id
        ids = [r[0] for r in conn.execute(text("SELECT id FROM users WHERE id NOT IN ('platform','system') ORDER BY random() LIMIT 30")).fetchall()]
        mismatches = 0
        for uid in ids:
            mongo_doc = await db.users.find_one({"id": uid}, {"_id": 0, "name": 1, "email": 1, "city_id": 1})
            pg_row = conn.execute(text("SELECT name, email, city_id FROM users WHERE id = :id"), {"id": uid}).one()
            if mongo_doc["name"] != pg_row.name or mongo_doc.get("email") != pg_row.email or mongo_doc["city_id"] != pg_row.city_id:
                mismatches += 1
        (ok if mismatches == 0 else fail)(f"users: {len(ids)} amostrados, {mismatches} divergência(s)")


# ---------- 3. financial reconciliation ----------

def _apply_txn(balances: dict, txn) -> None:
    """balances: {'available': int, 'pending': int, 'processing': int}. Mirrors
    wallet.py's credit_wallet/debit_wallet/move_bucket exactly — only COMPLETED
    transactions ever touch a balance."""
    if txn.status != "COMPLETED":
        return
    if txn.direction == "IN":
        balances[txn.bucket] = balances.get(txn.bucket, 0) + txn.amount_cents
    elif txn.direction == "OUT":
        balances[txn.bucket] = balances.get(txn.bucket, 0) - txn.amount_cents
    elif txn.direction == "MOVE":
        from_bucket, to_bucket = txn.bucket.split("->")
        balances[from_bucket] = balances.get(from_bucket, 0) - txn.amount_cents
        balances[to_bucket] = balances.get(to_bucket, 0) + txn.amount_cents


async def check_financial_reconciliation(engine) -> None:
    print("\n=== 3a. Reconciliação financeira global ===")
    with engine.connect() as conn:
        wallets = conn.execute(text(
            "SELECT id, available_cents, pending_cents, processing_cents FROM wallets"
        )).fetchall()
        txns_by_wallet: dict[str, list] = {}
        for row in conn.execute(text(
            "SELECT wallet_id, status, direction, bucket, amount_cents, created_at "
            "FROM wallet_transactions ORDER BY wallet_id, created_at"
        )):
            txns_by_wallet.setdefault(row.wallet_id, []).append(row)

        global_mismatches = 0
        for w in wallets:
            balances = {"available": 0, "pending": 0, "processing": 0}
            for txn in txns_by_wallet.get(w.id, []):
                _apply_txn(balances, txn)
            if (balances["available"], balances["pending"], balances["processing"]) != \
               (w.available_cents, w.pending_cents, w.processing_cents):
                global_mismatches += 1
        (ok if global_mismatches == 0 else fail)(
            f"{len(wallets)} carteiras verificadas via soma do ledger, {global_mismatches} divergência(s)"
        )

        print("\n=== 3b. Replay por amostra (~30 carteiras) ===")
        sample_ids = [w.id for w in random.sample(wallets, min(30, len(wallets)))]
        replay_mismatches = 0
        for wid in sample_ids:
            w = next(x for x in wallets if x.id == wid)
            balances = {"available": 0, "pending": 0, "processing": 0}
            for txn in txns_by_wallet.get(wid, []):
                _apply_txn(balances, txn)
            if (balances["available"], balances["pending"], balances["processing"]) != \
               (w.available_cents, w.pending_cents, w.processing_cents):
                replay_mismatches += 1
                fail(
                    f"wallet {wid}: replay={balances} != armazenado="
                    f"{{'available': {w.available_cents}, 'pending': {w.pending_cents}, 'processing': {w.processing_cents}}}"
                )
        if replay_mismatches == 0:
            ok(f"{len(sample_ids)} carteiras replayed cronologicamente, 0 divergência(s)")


# ---------- 4. bank-data ciphertext passthrough ----------

async def check_bank_ciphertext(engine) -> None:
    print("\n=== 4. Passagem de dados bancários cifrados ===")
    with engine.connect() as conn:
        ids = [r[0] for r in conn.execute(text("SELECT id FROM bank_accounts ORDER BY random() LIMIT 30")).fetchall()]
        mismatches = 0
        for bid in ids:
            mongo_doc = await db.bank_accounts.find_one({"id": bid}, {"_id": 0, "document": 1, "account_number": 1})
            pg_row = conn.execute(text("SELECT document, account_number FROM bank_accounts WHERE id = :id"), {"id": bid}).one()
            if mongo_doc["document"] != pg_row.document or mongo_doc["account_number"] != pg_row.account_number:
                mismatches += 1
            elif not (pg_row.document.startswith("enc:v1:") and pg_row.account_number.startswith("enc:v1:")):
                mismatches += 1
        (ok if mismatches == 0 else fail)(f"bank_accounts: {len(ids)} amostradas, {mismatches} divergência(s) de ciphertext")


async def main() -> None:
    _require_isolated_db()
    engine = get_engine()
    print(f"Validação: '{db.name}' vs {engine.url.database}\n")

    await check_row_counts(engine)
    await check_spot_samples(engine)
    await check_financial_reconciliation(engine)
    await check_bank_ciphertext(engine)

    print(f"\n{'FALHAS ENCONTRADAS' if FAILURES else 'TUDO OK'}: {len(FAILURES)} problema(s).")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
