"""Mongo (faze_isolated) -> PostgreSQL ETL. Read-only against Mongo, idempotent
against Postgres (every table upserts on its primary key, or no-ops on conflict
for append-only/ledger tables), safe to run more than once.

This does NOT touch the running API — MongoDB stays the backend's sole source of
truth this phase (see the migration plan's FASE 8 deferral). This script only
populates a validation/mirror Postgres database so the schema can be proven
against real data before any cutover decision is made.

Load order follows FK dependency tiers (roots first). Within each tier, order
doesn't matter. `python -m etl.checks` should be run first — this script trusts
its "skip-and-log, don't invent data" policy for the specific orphans it found
(see ORPHAN POLICY below) but does not re-derive that policy from scratch.

ORPHAN POLICY (matches etl/checks.py's findings against faze_isolated):
- A row whose *required* FK target is missing is skipped entirely and logged
  (e.g. proposals/messages pointing at a deleted order, an admin_action pointing
  at a deleted admin) — these are dev-data artifacts, not data worth inventing a
  fake parent for.
- A row whose FK is *nullable* just gets that one field nulled out instead of
  being dropped (e.g. a notification pointing at a deleted order keeps existing,
  just loses the order_id link) — the row itself is still meaningful.
- Two exceptions are pre-loaded as synthetic `users` rows rather than treated as
  orphans, because they're real, load-bearing string constants the app already
  depends on: 'platform' (commission wallet owner, wallet.py) and 'system' (chat
  system-message sender, routes/public.py). See identity.py's docstring.

Usage (from backend/, MUST be run against the isolated environment):
    ENV_FILE=.env.isolated ./venv/Scripts/python.exe -m etl.run
"""
import asyncio
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import Table  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from app.db.base import Base, get_engine  # noqa: E402
import app.db.models  # noqa: E402,F401 — populates Base.metadata
from database import db  # noqa: E402
from etl.money_fields import MONEY_FIELDS  # noqa: E402

TABLES = Base.metadata.tables
STATS: dict[str, int] = {}
SKIPPED: dict[str, int] = {}


def _require_isolated_db() -> None:
    if db.name != "faze_isolated":
        raise RuntimeError(
            f"Recusando rodar contra o banco '{db.name}'. Este ETL só pode ler de "
            f"'faze_isolated' — rode com ENV_FILE=.env.isolated."
        )


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value)


def to_cents(value: Any) -> Optional[int]:
    if value is None:
        return None
    cents = Decimal(str(value)) * 100
    return int(cents.to_integral_value(rounding=ROUND_HALF_UP))


def upsert(conn: Connection, table: Table, rows: list[dict], do_nothing: bool = False) -> None:
    if not rows:
        return
    # Postgres caps a single statement at 65535 bound parameters — batch so a big
    # collection (messages, notifications, wallet_transactions...) never exceeds
    # that regardless of column count.
    batch_size = max(1, 60000 // max(len(table.columns), 1))
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        stmt = pg_insert(table).values(batch)
        if do_nothing:
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        else:
            update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
        conn.execute(stmt)
    STATS[table.name] = STATS.get(table.name, 0) + len(rows)


def skip(table_name: str, count: int = 1) -> None:
    SKIPPED[table_name] = SKIPPED.get(table_name, 0) + count


SYNTHESIZED_USER_IDS = {"platform", "system"}


async def existing_ids(coll_name: str, field: str = "id") -> set:
    ids = set(await db[coll_name].distinct(field))
    if coll_name == "users":
        # 'platform'/'system' are synthesized straight into Postgres by load_users()
        # (see identity.py's docstring) — they never exist in Mongo, so a plain
        # Mongo distinct() here would make every legitimate reference to them (the
        # platform wallet, every system chat message) look like an orphan.
        ids |= SYNTHESIZED_USER_IDS
    return ids


# ---------- geography / catalog (roots) ----------

async def load_geography(conn: Connection) -> None:
    states = await db.states.find({}, {"_id": 0}).to_list(1000)
    upsert(conn, TABLES["states"], [
        {"id": s["id"], "name": s["name"], "uf": s["uf"], "active": s.get("active", True)} for s in states
    ])
    cities = await db.cities.find({}, {"_id": 0}).to_list(5000)
    upsert(conn, TABLES["cities"], [
        {"id": c["id"], "state_id": c["state_id"], "name": c["name"], "active": c.get("active", True)}
        for c in cities
    ])
    neighborhoods = await db.neighborhoods.find({}, {"_id": 0}).to_list(20000)
    upsert(conn, TABLES["neighborhoods"], [
        {
            "id": n["id"], "city_id": n["city_id"], "name": n["name"], "kind": n["kind"],
            "active": n.get("active", True), "zone": n.get("zone"),
        }
        for n in neighborhoods
    ])


async def load_catalog(conn: Connection) -> None:
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    upsert(conn, TABLES["categories"], [
        {"id": c["id"], "name": c["name"], "icon": c["icon"], "active": c.get("active", True), "order": c.get("order", 0)}
        for c in categories
    ])
    subcategories = await db.subcategories.find({}, {"_id": 0}).to_list(5000)
    upsert(conn, TABLES["subcategories"], [
        {"id": s["id"], "category_id": s["category_id"], "name": s["name"], "active": s.get("active", True)}
        for s in subcategories
    ])


# ---------- admin (roots) ----------

async def load_admin_users(conn: Connection) -> None:
    admins = await db.admin_users.find({}, {"_id": 0}).to_list(1000)
    upsert(conn, TABLES["admin_users"], [
        {
            "id": a["id"], "name": a["name"], "email": a["email"], "password_hash": a["password_hash"],
            "role": a["role"], "totp_secret": a.get("totp_secret"), "totp_secret_pending": a.get("totp_secret_pending"),
            "totp_enabled": a.get("totp_enabled", False), "active": a.get("active", True),
            "token_version": a.get("token_version", 0), "last_login_at": parse_dt(a.get("last_login_at")),
            "last_active_at": parse_dt(a.get("last_active_at")), "created_at": parse_dt(a["created_at"]),
            "updated_at": parse_dt(a.get("updated_at") or a["created_at"]),
        }
        for a in admins
    ])


async def load_admin_roles(conn: Connection) -> None:
    roles = await db.admin_roles.find({}, {"_id": 0}).to_list(100)
    upsert(conn, TABLES["admin_roles"], [{"id": r["key"], "name": r["name"]} for r in roles])


# ---------- identity ----------

# 'city-parauapebas' / 'st-pa' are the real seeded ids (seed.py) — used only as a
# fallback anchor for the two synthetic users below if present; otherwise we fall
# back to whatever city/state actually exists so this never hard-fails on a
# differently-seeded environment.
async def _anchor_city_state() -> tuple[str, str]:
    city = await db.cities.find_one({"id": "city-parauapebas"}) or await db.cities.find_one({})
    if not city:
        raise RuntimeError("Nenhuma cidade encontrada — carregue geography antes de identity.")
    return city["id"], city["state_id"]


async def load_users(conn: Connection) -> None:
    city_id, state_id = await _anchor_city_state()
    now = datetime.now(timezone.utc)
    synthesized = [
        {
            "id": "platform", "name": "Plataforma fazum", "email": None, "phone": None, "password_hash": None,
            "city_id": city_id, "state_id": state_id, "neighborhood_id": None, "preference": "both",
            "account_status": "ACTIVE", "member_since": now, "created_at": now,
        },
        {
            "id": "system", "name": "Sistema", "email": None, "phone": None, "password_hash": None,
            "city_id": city_id, "state_id": state_id, "neighborhood_id": None, "preference": "both",
            "account_status": "ACTIVE", "member_since": now, "created_at": now,
        },
    ]
    upsert(conn, TABLES["users"], synthesized)

    # Some real users predate state_id being recorded at registration (confirmed:
    # 292/2118 in faze_isolated have city_id but no state_id) — backfill from the
    # city's own state_id rather than dropping the user or leaving state_id NULL.
    cities = await db.cities.find({}, {"_id": 0, "id": 1, "state_id": 1}).to_list(5000)
    city_state = {c["id"]: c["state_id"] for c in cities}

    users = await db.users.find({}, {"_id": 0}).to_list(200000)
    rows = []
    for u in users:
        state_id = u.get("state_id") or city_state.get(u["city_id"]) or state_id
        rows.append({
            "id": u["id"], "name": u["name"], "email": u.get("email"), "phone": u.get("phone"),
            "password_hash": u.get("password_hash"), "initials": u.get("initials"), "bio": u.get("bio"),
            "rating": u.get("rating", 0), "rating_count": u.get("rating_count", 0), "jobs_done": u.get("jobs_done", 0),
            "city_id": u["city_id"], "neighborhood_id": u.get("neighborhood_id"), "state_id": state_id,
            # 3/2118 real users predate this field too — default to the most
            # permissive value rather than guessing an intent that isn't recorded.
            "preference": u.get("preference", "both"), "verified_email": u.get("verified_email", False),
            "verified_phone": u.get("verified_phone", False), "verified_identity": u.get("verified_identity", False),
            "email_verified_at": parse_dt(u.get("email_verified_at")), "phone_verified_at": parse_dt(u.get("phone_verified_at")),
            "account_status": u.get("account_status", "PENDING_VERIFICATION"), "is_admin": u.get("is_admin", False),
            "blocked": u.get("blocked", False), "member_since": parse_dt(u["member_since"]), "is_demo": u.get("is_demo", False),
            "created_at": parse_dt(u["created_at"]), "avatar_b64": u.get("avatar_b64"),
            "notification_prefs": u.get("notification_prefs", {}), "token_version": u.get("token_version", 0),
        })
    upsert(conn, TABLES["users"], rows)


async def load_auth_accounts(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.auth_accounts.find({}, {"_id": 0}).to_list(200000)
    rows = []
    for d in docs:
        if d["user_id"] not in user_ids:
            skip("auth_accounts")
            continue
        rows.append({
            "id": d["id"], "user_id": d["user_id"], "provider": d["provider"],
            "provider_account_id": d["provider_account_id"], "created_at": parse_dt(d["created_at"]),
        })
    upsert(conn, TABLES["auth_accounts"], rows)


async def load_verification_tokens(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.verification_tokens.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for d in docs:
        if d["user_id"] not in user_ids:
            skip("verification_tokens")
            continue
        rows.append({
            "id": d["id"], "user_id": d["user_id"], "type": d["type"], "token_hash": d["token_hash"],
            # expires_at is a Unix float (time.time() + ttl_seconds in verification.py),
            # NOT an ISO string like every other timestamp field in this codebase.
            "expires_at": datetime.fromtimestamp(d["expires_at"], tz=timezone.utc),
            "used_at": parse_dt(d.get("used_at")), "verified_at": parse_dt(d.get("verified_at")),
            "attempts": d.get("attempts", 0), "max_attempts": d.get("max_attempts", 5),
            "created_at": parse_dt(d["created_at"]),
        })
    upsert(conn, TABLES["verification_tokens"], rows)


# ---------- orders + everything that hangs off one ----------

async def load_orders(conn: Connection) -> None:
    category_ids = await existing_ids("categories")
    city_ids = await existing_ids("cities")
    docs = await db.orders.find({}, {"_id": 0}).to_list(500000)
    rows, photo_rows, history_rows = [], [], []
    for o in docs:
        if o["category_id"] not in category_ids or o["city_id"] not in city_ids:
            skip("orders")
            continue
        rows.append({
            "id": o["id"], "title": o["title"], "description": o.get("description", ""), "type": o["type"],
            "category_id": o["category_id"], "subcategory_id": o.get("subcategory_id"), "city_id": o["city_id"],
            "neighborhood_id": o.get("neighborhood_id"), "date_label": o.get("date_label"), "time_label": o.get("time_label"),
            "budget_cents": to_cents(o.get("budget", 0)) or 0, "fields": o.get("fields", {}), "urgent": o.get("urgent", False),
            "recurrence": o.get("recurrence", "none"), "status": o["status"], "worker_id": o.get("worker_id"),
            "client_id": o["client_id"], "accepted_amount_cents": to_cents(o.get("accepted_amount")),
            "accepted_at": parse_dt(o.get("accepted_at")),
            "started_at": parse_dt(o.get("started_at")), "completion_requested_at": parse_dt(o.get("completion_requested_at")),
            "completed_at": parse_dt(o.get("completed_at")), "cancelled_at": parse_dt(o.get("cancelled_at")),
            "reviewed_by_client": o.get("reviewed_by_client", False), "reviewed_by_worker": o.get("reviewed_by_worker", False),
            "is_demo": o.get("is_demo", False), "created_at": parse_dt(o["created_at"]),
            "external_payment_flags": o.get("external_payment_flags", {}),
            "external_payment_restricted": o.get("external_payment_restricted", False),
            "pre_dispute_status": o.get("pre_dispute_status"),
        })
        for i, photo_b64 in enumerate(o.get("photos") or []):
            photo_rows.append({
                "id": f"{o['id']}:{i}", "order_id": o["id"], "position": i, "data_b64": photo_b64,
                "created_at": parse_dt(o["created_at"]),
            })
        # Synthesized one-row history per order (no real transition log exists in
        # Mongo pre-migration — service_status_history is a new table, see orders.py).
        history_rows.append({
            "id": f"init:{o['id']}", "order_id": o["id"], "from_status": None, "to_status": o["status"], "changed_by": None,
            "reason": "migração inicial — histórico anterior não existia", "metadata": {},
            "created_at": parse_dt(o["created_at"]),
        })
    upsert(conn, TABLES["orders"], rows)
    upsert(conn, TABLES["order_photos"], photo_rows, do_nothing=True)
    upsert(conn, TABLES["service_status_history"], history_rows, do_nothing=True)


async def load_proposals(conn: Connection) -> None:
    order_ids, user_ids = await existing_ids("orders"), await existing_ids("users")
    docs = await db.proposals.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for p in docs:
        if p["order_id"] not in order_ids or p["worker_id"] not in user_ids:
            skip("proposals")
            continue
        rows.append({
            "id": p["id"], "order_id": p["order_id"], "worker_id": p["worker_id"], "amount_cents": to_cents(p["amount"]) or 0,
            "message": p.get("message", ""), "eta": p.get("eta", ""), "status": p["status"], "created_at": parse_dt(p["created_at"]),
        })
    upsert(conn, TABLES["proposals"], rows)


async def load_messages(conn: Connection) -> None:
    order_ids, user_ids = await existing_ids("orders"), await existing_ids("users")
    docs = await db.messages.find({}, {"_id": 0}).to_list(2000000)
    rows = []
    for m in docs:
        if m["order_id"] not in order_ids or m["sender_id"] not in user_ids:
            skip("messages")
            continue
        rows.append({
            "id": m["id"], "order_id": m["order_id"], "sender_id": m["sender_id"], "type": m["type"],
            "text": m.get("text"), "image_b64": m.get("image_b64"), "created_at": parse_dt(m["created_at"]),
        })
    upsert(conn, TABLES["messages"], rows)


async def load_reviews(conn: Connection) -> None:
    order_ids, user_ids = await existing_ids("orders"), await existing_ids("users")
    docs = await db.reviews.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for r in docs:
        if r["order_id"] not in order_ids or r["from_id"] not in user_ids or r["to_id"] not in user_ids:
            skip("reviews")
            continue
        rows.append({
            "id": r["id"], "order_id": r["order_id"], "from_id": r["from_id"], "to_id": r["to_id"],
            "stars": r["stars"], "comment": r.get("comment", ""), "created_at": parse_dt(r["created_at"]),
        })
    upsert(conn, TABLES["reviews"], rows)


async def load_reports(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.reports.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for r in docs:
        if r["reporter_id"] not in user_ids:
            skip("reports")
            continue
        rows.append({
            "id": r["id"], "reporter_id": r["reporter_id"], "target_type": r["target_type"], "target_id": r["target_id"],
            "reason": r["reason"], "details": r.get("details", ""),
            # routes/admin.py only ever accepts/writes uppercase status values — a
            # handful of records in faze_isolated predate that validation and carry
            # lowercase values (e.g. 'resolved'). Normalizing casing here isn't
            # inventing data, just conforming stale rows to the invariant the app
            # has enforced on every write path for a while now.
            "status": r.get("status", "OPEN").upper(),
            "resolution": r.get("resolution"), "updated_at": parse_dt(r.get("updated_at")), "created_at": parse_dt(r["created_at"]),
        })
    upsert(conn, TABLES["reports"], rows)


async def load_blocks(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.blocks.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for b in docs:
        if b["user_id"] not in user_ids or b["blocked_user_id"] not in user_ids or b["user_id"] == b["blocked_user_id"]:
            skip("blocks")
            continue
        rows.append({
            "id": b["id"], "user_id": b["user_id"], "blocked_user_id": b["blocked_user_id"], "created_at": parse_dt(b["created_at"]),
        })
    upsert(conn, TABLES["blocks"], rows)


async def load_favorites(conn: Connection) -> None:
    user_ids, order_ids = await existing_ids("users"), await existing_ids("orders")
    docs = await db.favorites.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for f in docs:
        if f["user_id"] not in user_ids or f["order_id"] not in order_ids:
            skip("favorites")
            continue
        rows.append({"id": f["id"], "user_id": f["user_id"], "order_id": f["order_id"], "created_at": parse_dt(f["created_at"])})
    upsert(conn, TABLES["favorites"], rows)


async def load_notifications(conn: Connection) -> None:
    user_ids, order_ids = await existing_ids("users"), await existing_ids("orders")
    docs = await db.notifications.find({}, {"_id": 0}).to_list(2000000)
    rows = []
    for n in docs:
        if n["user_id"] not in user_ids:
            skip("notifications")
            continue
        order_id = n.get("order_id")
        if order_id and order_id not in order_ids:
            order_id = None  # nullable FK — keep the notification, drop the dangling link
        rows.append({
            "id": n["id"], "user_id": n["user_id"], "title": n["title"], "body": n.get("body", ""), "type": n["type"],
            "order_id": order_id, "read": n.get("read", False), "created_at": parse_dt(n["created_at"]),
        })
    upsert(conn, TABLES["notifications"], rows)


# ---------- financial ----------

async def load_wallets(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.wallets.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for w in docs:
        if w["user_id"] not in user_ids:
            skip("wallets")
            continue
        rows.append({
            "id": w["id"], "user_id": w["user_id"], "currency": w.get("currency", "BRL"),
            "available_cents": w.get("available_cents", 0), "pending_cents": w.get("pending_cents", 0),
            "processing_cents": w.get("processing_cents", 0), "total_received_cents": w.get("total_received_cents", 0),
            "total_spent_cents": w.get("total_spent_cents", 0), "created_at": parse_dt(w["created_at"]),
        })
    upsert(conn, TABLES["wallets"], rows)


async def load_wallet_transactions(conn: Connection) -> None:
    user_ids, wallet_ids = await existing_ids("users"), await existing_ids("wallets")
    docs = await db.wallet_transactions.find({}, {"_id": 0}).to_list(2000000)
    rows = []
    for t in docs:
        if t["user_id"] not in user_ids or t["wallet_id"] not in wallet_ids:
            skip("wallet_transactions")
            continue
        rows.append({
            "id": t["id"], "user_id": t["user_id"], "wallet_id": t["wallet_id"], "type": t["type"],
            "amount_cents": t["amount_cents"], "direction": t["direction"], "status": t["status"], "bucket": t["bucket"],
            "reference_type": t["reference_type"], "reference_id": t["reference_id"], "provider": t.get("provider"),
            "provider_transaction_id": t.get("provider_transaction_id"), "description": t.get("description", ""),
            "created_at": parse_dt(t["created_at"]), "updated_at": parse_dt(t.get("updated_at") or t["created_at"]),
            "idempotency_key": t.get("idempotency_key"),
        })
    upsert(conn, TABLES["wallet_transactions"], rows, do_nothing=True)


async def load_deposits(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.deposits.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for d in docs:
        if d["user_id"] not in user_ids:
            skip("deposits")
            continue
        rows.append({
            "id": d["id"], "user_id": d["user_id"], "amount_cents": to_cents(d["amount"]) or 0,
            "method": d.get("method", "pix"), "status": d["status"], "provider": d.get("provider"),
            "provider_transaction_id": d.get("provider_transaction_id"), "created_at": parse_dt(d["created_at"]),
            "updated_at": parse_dt(d.get("updated_at") or d["created_at"]), "idempotency_key": d.get("idempotency_key"),
        })
    upsert(conn, TABLES["deposits"], rows)


async def load_bank_accounts(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.bank_accounts.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for b in docs:
        if b["user_id"] not in user_ids:
            skip("bank_accounts")
            continue
        rows.append({
            "id": b["id"], "user_id": b["user_id"], "holder_name": b["holder_name"], "document": b["document"],
            "bank_code": b["bank_code"], "agency": b["agency"], "account_number": b["account_number"],
            "account_type": b.get("account_type", "checking"), "is_primary": b.get("is_primary", False),
            "active": b.get("active", True), "created_at": parse_dt(b["created_at"]),
        })
    upsert(conn, TABLES["bank_accounts"], rows)


async def load_withdrawals(conn: Connection) -> None:
    user_ids, bank_account_ids = await existing_ids("users"), await existing_ids("bank_accounts")
    docs = await db.withdrawals.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for w in docs:
        if w["user_id"] not in user_ids or w["bank_account_id"] not in bank_account_ids:
            skip("withdrawals")
            continue
        # 26/180 in faze_isolated carry risk_level="REVIEW_REQUIRED" — not a real risk
        # score (fraud.py only ever produces LOW/MEDIUM/HIGH/CRITICAL), a legacy dev
        # artifact where the field got the status value instead. routes/wallet.py:207
        # only ever sets status="REVIEW_REQUIRED" when risk=="HIGH", so that's the one
        # value consistent with the app's own logic for every row this happened to.
        risk_level = "HIGH" if w["risk_level"] == "REVIEW_REQUIRED" else w["risk_level"]
        rows.append({
            "id": w["id"], "user_id": w["user_id"], "amount_cents": to_cents(w["amount"]) or 0,
            "bank_account_id": w["bank_account_id"], "bank_account_snapshot": w.get("bank_account_snapshot", {}),
            "status": w["status"], "risk_level": risk_level, "risk_reasons": w.get("risk_reasons", []),
            "created_at": parse_dt(w["created_at"]), "updated_at": parse_dt(w.get("updated_at") or w["created_at"]),
            "idempotency_key": w.get("idempotency_key"), "reason": w.get("reason"),
        })
    upsert(conn, TABLES["withdrawals"], rows)


async def load_payments(conn: Connection) -> None:
    order_ids, user_ids = await existing_ids("orders"), await existing_ids("users")
    docs = await db.payments.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for p in docs:
        if p["order_id"] not in order_ids or p["client_id"] not in user_ids:
            skip("payments")
            continue
        rows.append({
            "id": p["id"], "order_id": p["order_id"], "client_id": p["client_id"], "worker_id": p.get("worker_id"),
            "gross_amount_cents": to_cents(p["gross_amount"]) or 0, "commission_amount_cents": to_cents(p["commission_amount"]) or 0,
            "worker_net_amount_cents": to_cents(p["worker_net_amount"]) or 0, "commission_percent": p["commission_percent"],
            "method": p["method"], "status": p["status"], "provider": p.get("provider"),
            "provider_transaction_id": p.get("provider_transaction_id"), "idempotency_key": p.get("idempotency_key"),
            "client_ip": p.get("client_ip"), "created_at": parse_dt(p["created_at"]),
            "updated_at": parse_dt(p.get("updated_at") or p["created_at"]),
        })
    upsert(conn, TABLES["payments"], rows)


async def load_payment_events(conn: Connection) -> None:
    docs = await db.payment_events.find({}, {"_id": 0}).to_list(500000)
    rows = [
        {"id": e["id"], "event_id": e["event_id"], "payload": e.get("payload", {}), "processed_at": parse_dt(e["processed_at"])}
        for e in docs
    ]
    upsert(conn, TABLES["payment_events"], rows, do_nothing=True)


async def load_disputes(conn: Connection) -> None:
    order_ids, user_ids = await existing_ids("orders"), await existing_ids("users")
    docs = await db.disputes.find({}, {"_id": 0}).to_list(500000)
    rows, evidence_rows = [], []
    for d in docs:
        if d["order_id"] not in order_ids or d["reporter_id"] not in user_ids:
            skip("disputes")
            continue
        rows.append({
            "id": d["id"], "order_id": d["order_id"], "reporter_id": d["reporter_id"], "target_type": d["target_type"],
            "reason": d["reason"], "description": d.get("description", ""), "status": d.get("status", "OPEN"),
            "resolution": d.get("resolution", ""), "created_at": parse_dt(d["created_at"]),
            "updated_at": parse_dt(d.get("updated_at") or d["created_at"]),
        })
        for i, evidence_b64 in enumerate(d.get("evidence") or []):
            evidence_rows.append({
                "id": f"{d['id']}:{i}", "dispute_id": d["id"], "position": i, "data_b64": evidence_b64,
                "created_at": parse_dt(d["created_at"]),
            })
    upsert(conn, TABLES["disputes"], rows)
    upsert(conn, TABLES["dispute_evidence"], evidence_rows, do_nothing=True)


async def load_risk_flags(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.risk_flags.find({}, {"_id": 0}).to_list(500000)
    rows = []
    for r in docs:
        if r["user_id"] not in user_ids:
            skip("risk_flags")
            continue
        rows.append({
            "id": r["id"], "user_id": r["user_id"], "kind": r["kind"], "reference_id": r["reference_id"],
            "level": r["level"], "reasons": r.get("reasons", []), "status": r.get("status", "OPEN"),
            "note": r.get("note"), "created_at": parse_dt(r["created_at"]), "updated_at": parse_dt(r.get("updated_at")),
        })
    upsert(conn, TABLES["risk_flags"], rows, do_nothing=True)


async def load_security_events(conn: Connection) -> None:
    user_ids = await existing_ids("users")
    docs = await db.security_events.find({}, {"_id": 0}).to_list(2000000)
    rows = []
    for e in docs:
        if e["user_id"] not in user_ids:
            skip("security_events")
            continue
        rows.append({
            "id": e["id"], "user_id": e["user_id"], "event": e["event"], "detail": e.get("detail", ""),
            "ip": e.get("ip"), "created_at": parse_dt(e["created_at"]),
        })
    upsert(conn, TABLES["security_events"], rows, do_nothing=True)


# ---------- support ----------

async def load_tickets(conn: Connection) -> None:
    user_ids, admin_ids = await existing_ids("users"), await existing_ids("admin_users")
    docs = await db.tickets.find({}, {"_id": 0}).to_list(500000)
    rows, message_rows = [], []
    for t in docs:
        if t["created_by"] not in user_ids:
            skip("tickets")
            continue
        assigned_to = t.get("assigned_to")
        if assigned_to and assigned_to not in admin_ids:
            assigned_to = None
        rows.append({
            "id": t["id"], "created_by": t["created_by"], "category": t["category"], "subject": t["subject"],
            "description": t.get("description", ""), "status": t["status"], "assigned_to": assigned_to,
            "created_at": parse_dt(t["created_at"]), "updated_at": parse_dt(t.get("updated_at") or t["created_at"]),
        })
        for m in t.get("messages") or []:
            message_rows.append({
                "id": m["id"], "ticket_id": t["id"], "author_type": m["author_type"], "author_id": m["author_id"],
                "text": m.get("text"), "created_at": parse_dt(m["created_at"]),
            })
    upsert(conn, TABLES["tickets"], rows)
    upsert(conn, TABLES["ticket_messages"], message_rows, do_nothing=True)


# ---------- admin (leaves) ----------

async def load_admin_actions(conn: Connection) -> None:
    admin_ids = await existing_ids("admin_users")
    docs = await db.admin_actions.find({}, {"_id": 0}).to_list(2000000)
    rows = []
    for a in docs:
        if a["admin_id"] not in admin_ids:
            skip("admin_actions")
            continue
        rows.append({
            "id": a["id"], "admin_id": a["admin_id"], "action": a["action"], "target": a.get("target"),
            "result": a.get("result", "success"), "ip": a.get("ip"), "metadata": a.get("metadata", {}),
            "created_at": parse_dt(a["created_at"]),
        })
    upsert(conn, TABLES["admin_actions"], rows, do_nothing=True)


async def load_feature_flags(conn: Connection) -> None:
    admin_ids = await existing_ids("admin_users")
    docs = await db.feature_flags.find({}, {"_id": 0}).to_list(1000)
    rows = []
    for f in docs:
        updated_by = f.get("updated_by")
        if updated_by and updated_by not in admin_ids:
            updated_by = None
        rows.append({
            "id": f["key"], "enabled": f["enabled"], "description": f.get("description"),
            "updated_by": updated_by, "updated_at": parse_dt(f.get("updated_at")),
        })
    upsert(conn, TABLES["feature_flags"], rows)


async def load_system_settings(conn: Connection) -> None:
    docs = await db.platform_config.find({}, {"_id": 0}).to_list(1000)
    rows = []
    for d in docs:
        doc_id = d["id"]
        value = {k: v for k, v in d.items() if k != "id"}
        rows.append({"id": doc_id, "value": value, "updated_by": None, "updated_at": None})
    upsert(conn, TABLES["system_settings"], rows)


STEPS = [
    ("geography", load_geography),
    ("catalog", load_catalog),
    ("admin_roles", load_admin_roles),
    ("admin_users", load_admin_users),
    ("users", load_users),
    ("auth_accounts", load_auth_accounts),
    ("verification_tokens", load_verification_tokens),
    ("orders (+order_photos, +service_status_history)", load_orders),
    ("proposals", load_proposals),
    ("messages", load_messages),
    ("reviews", load_reviews),
    ("reports", load_reports),
    ("blocks", load_blocks),
    ("favorites", load_favorites),
    ("notifications", load_notifications),
    ("wallets", load_wallets),
    ("wallet_transactions", load_wallet_transactions),
    ("deposits", load_deposits),
    ("bank_accounts", load_bank_accounts),
    ("withdrawals", load_withdrawals),
    ("payments", load_payments),
    ("payment_events", load_payment_events),
    ("disputes (+dispute_evidence)", load_disputes),
    ("risk_flags", load_risk_flags),
    ("security_events", load_security_events),
    ("tickets (+ticket_messages)", load_tickets),
    ("admin_actions", load_admin_actions),
    ("feature_flags", load_feature_flags),
    ("system_settings", load_system_settings),
]


async def main() -> None:
    _require_isolated_db()
    engine = get_engine()
    print(f"ETL: '{db.name}' -> {engine.url.database} ({len(STEPS)} passos)\n")
    for label, step in STEPS:
        with engine.begin() as conn:
            await step(conn)
        print(f"  [ok] {label}")

    print("\n=== Linhas carregadas (upsert) por tabela ===")
    for name, count in sorted(STATS.items()):
        print(f"  {name}: {count}")
    if SKIPPED:
        print("\n=== Linhas puladas (FK obrigatória órfã) ===")
        for name, count in sorted(SKIPPED.items()):
            print(f"  {name}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
