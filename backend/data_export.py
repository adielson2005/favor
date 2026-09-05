"""LGPD Art. 18 — right of access: a complete, honest copy of everything FAZUM
actually stores about one user, for `GET /auth/me/export`. Every section reuses
the exact same public-shaping helper the rest of the app already uses for that
data (never a second, divergent formatting), so what a user sees here can never
drift from what the app itself considers "presentable" about that record.

Deliberately excluded (see the LGPD plan for why): `risk_flags`/trust_index
(internal antifraud signal, never user-facing anywhere else — exposing it here
would just be a new way to reverse-engineer the fraud model), `admin_actions`
(activity done TO the user BY staff, not the user's own data), and
`verification_tokens` (ephemeral security codes — the hash helps no one).
"""
from bank_encryption import decrypt_field
from database import db
from routes.public import private_user
from wallet import get_or_create_wallet, transaction_public, wallet_public


def _mask_account(account: dict) -> dict:
    number = decrypt_field(account.get("account_number", ""))
    masked = f"****{number[-4:]}" if len(number) >= 4 else "****"
    doc = decrypt_field(account.get("document", ""))
    masked_doc = f"***.***.***-{doc[-2:]}" if len(doc) >= 2 else "***"
    return {k: account.get(k) for k in ("id", "holder_name", "bank_code", "agency", "account_type", "is_primary", "created_at")} | {
        "account_number_masked": masked, "document_masked": masked_doc,
    }


async def _list(collection: str, query: dict, limit: int = 1000) -> list[dict]:
    return await db[collection].find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)


async def compile_user_export(user_id: str) -> dict:
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    wallet = await get_or_create_wallet(user_id)
    transactions = await _list("wallet_transactions", {"user_id": user_id})
    bank_accounts = await _list("bank_accounts", {"user_id": user_id, "active": True})

    return {
        "profile": private_user(user),
        "orders_as_client": await _list("orders", {"client_id": user_id}),
        "orders_as_worker": await _list("orders", {"worker_id": user_id}),
        "proposals_sent": await _list("proposals", {"worker_id": user_id}),
        "messages_sent": await _list("messages", {"sender_id": user_id}),
        "reviews_given": await _list("reviews", {"from_id": user_id}),
        "reviews_received": await _list("reviews", {"to_id": user_id}),
        "reports_filed": await _list("reports", {"reporter_id": user_id}),
        "blocks": await _list("blocks", {"user_id": user_id}),
        "favorites": await _list("favorites", {"user_id": user_id}),
        "notifications": await _list("notifications", {"user_id": user_id}),
        "wallet": wallet_public(wallet),
        "wallet_transactions": [transaction_public(t) for t in transactions],
        "payments_as_client": await _list("payments", {"client_id": user_id}),
        "payments_as_worker": await _list("payments", {"worker_id": user_id}),
        "withdrawals": await _list("withdrawals", {"user_id": user_id}),
        "deposits": await _list("deposits", {"user_id": user_id}),
        "bank_accounts": [_mask_account(a) for a in bank_accounts],
        "disputes": await _list("disputes", {"reporter_id": user_id}),
        "security_events": await _list("security_events", {"user_id": user_id}),
        "support_tickets": await _list("tickets", {"created_by": user_id}),
    }
