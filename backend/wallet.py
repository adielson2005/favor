"""Core ledger engine. Money is always stored as integer centavos — never float —
so arithmetic can't drift from rounding. Every balance change is a single atomic
MongoDB document operation (conditional find_one_and_update), which is how we get
correctness without needing multi-document transactions (this deployment runs
MongoDB as a standalone instance, not a replica set, so those aren't available).

Rule this whole module exists to enforce: a wallet's cached balance may ONLY change
in the same call that appends a wallet_transactions ledger row. There is no path
that lets a balance move without a corresponding, permanent, auditable record.
"""
from typing import Literal, Optional

from database import db, new_id, now

Bucket = Literal["available", "pending", "processing"]


class InsufficientFundsError(Exception):
    pass


def to_cents(reais: float) -> int:
    return round(reais * 100)


def to_reais(cents: int) -> float:
    return round(cents / 100, 2)


def wallet_public(wallet: dict) -> dict:
    return {
        "available": to_reais(wallet.get("available_cents", 0)),
        "pending": to_reais(wallet.get("pending_cents", 0)),
        "processing": to_reais(wallet.get("processing_cents", 0)),
        "total_received": to_reais(wallet.get("total_received_cents", 0)),
        "total_spent": to_reais(wallet.get("total_spent_cents", 0)),
        "currency": wallet.get("currency", "BRL"),
    }


def transaction_public(txn: dict) -> dict:
    return dict(txn) | {"amount": to_reais(txn.get("amount_cents", 0))}


async def get_or_create_wallet(user_id: str) -> dict:
    wallet = await db.wallets.find_one({"user_id": user_id}, {"_id": 0})
    if wallet:
        return wallet
    wallet = {
        "id": new_id(), "user_id": user_id, "currency": "BRL",
        "available_cents": 0, "pending_cents": 0, "processing_cents": 0,
        "total_received_cents": 0, "total_spent_cents": 0, "created_at": now(),
    }
    try:
        await db.wallets.insert_one(dict(wallet))
    except Exception:
        # Unique index on user_id — a concurrent request already created it.
        existing = await db.wallets.find_one({"user_id": user_id}, {"_id": 0})
        if existing:
            return existing
        raise
    return wallet


async def _find_by_idempotency_key(key: Optional[str]) -> Optional[dict]:
    if not key:
        return None
    existing = await db.wallet_transactions.find_one({"idempotency_key": key}, {"_id": 0})
    return existing


def _base_txn(user_id: str, wallet_id: str, type_: str, amount_cents: int, direction: str, status: str,
              bucket: str, reference_type: str, reference_id: str, description: str,
              provider: Optional[str] = None, provider_transaction_id: Optional[str] = None,
              idempotency_key: Optional[str] = None) -> dict:
    txn = {
        "id": new_id(), "user_id": user_id, "wallet_id": wallet_id, "type": type_,
        "amount_cents": amount_cents, "direction": direction, "status": status, "bucket": bucket,
        "reference_type": reference_type, "reference_id": reference_id,
        "provider": provider, "provider_transaction_id": provider_transaction_id,
        "description": description, "created_at": now(), "updated_at": now(),
    }
    # Only set when present — the unique index on this field is sparse, and a sparse
    # index only skips documents where the key is ABSENT, not ones where it's null.
    # Storing idempotency_key: None on every transaction would collide on the very
    # second insert, since MongoDB indexes null as a real, non-unique-safe value.
    if idempotency_key:
        txn["idempotency_key"] = idempotency_key
    return txn


async def credit_wallet(
    user_id: str, amount_cents: int, type_: str, reference_type: str, reference_id: str,
    bucket: Bucket = "available", provider: Optional[str] = None, provider_transaction_id: Optional[str] = None,
    description: str = "", status: str = "COMPLETED", idempotency_key: Optional[str] = None,
) -> dict:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    existing = await _find_by_idempotency_key(idempotency_key)
    if existing:
        return existing
    wallet = await get_or_create_wallet(user_id)
    # Ledger row first, balance second: if the insert below fails for any reason
    # (duplicate key, transient error), the balance is never touched — there is no
    # path where money moves without a permanent record already existing for it.
    txn = _base_txn(user_id, wallet["id"], type_, amount_cents, "IN", status, bucket,
                    reference_type, reference_id, description, provider, provider_transaction_id, idempotency_key)
    await db.wallet_transactions.insert_one(dict(txn))
    inc = {f"{bucket}_cents": amount_cents}
    if bucket == "available":
        inc["total_received_cents"] = amount_cents
    await db.wallets.update_one({"id": wallet["id"]}, {"$inc": inc})
    txn.pop("_id", None)
    return txn


async def debit_wallet(
    user_id: str, amount_cents: int, type_: str, reference_type: str, reference_id: str,
    bucket: Bucket = "available", description: str = "", status: str = "COMPLETED",
    idempotency_key: Optional[str] = None, count_as_spent: bool = True,
) -> dict:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    existing = await _find_by_idempotency_key(idempotency_key)
    if existing:
        return existing
    wallet = await get_or_create_wallet(user_id)
    # Same ledger-first ordering as credit_wallet. The txn starts PENDING; if the
    # conditional balance update below can't find enough funds, we flip this row to
    # FAILED instead of deleting it — a rejected debit attempt is itself something
    # worth keeping for fraud review, not something to erase.
    txn = _base_txn(user_id, wallet["id"], type_, amount_cents, "OUT", "PENDING", bucket,
                    reference_type, reference_id, description, idempotency_key=idempotency_key)
    await db.wallet_transactions.insert_one(dict(txn))

    field = f"{bucket}_cents"
    inc = {field: -amount_cents}
    if count_as_spent and bucket == "available":
        inc["total_spent_cents"] = amount_cents
    # The $gte guard makes this a single atomic all-or-nothing check-and-debit —
    # two concurrent debits against the same near-empty balance can't both succeed.
    claimed = await db.wallets.find_one_and_update({"id": wallet["id"], field: {"$gte": amount_cents}}, {"$inc": inc})
    if not claimed:
        await db.wallet_transactions.update_one({"id": txn["id"]}, {"$set": {"status": "FAILED", "updated_at": now()}})
        raise InsufficientFundsError("Saldo insuficiente.")

    await db.wallet_transactions.update_one({"id": txn["id"]}, {"$set": {"status": status, "updated_at": now()}})
    txn["status"] = status
    txn.pop("_id", None)
    return txn


async def move_bucket(
    user_id: str, amount_cents: int, from_bucket: Bucket, to_bucket: Bucket,
    type_: str, reference_type: str, reference_id: str, description: str = "",
) -> dict:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    wallet = await get_or_create_wallet(user_id)
    txn = _base_txn(user_id, wallet["id"], type_, amount_cents, "MOVE", "PENDING",
                    f"{from_bucket}->{to_bucket}", reference_type, reference_id, description)
    await db.wallet_transactions.insert_one(dict(txn))

    from_field, to_field = f"{from_bucket}_cents", f"{to_bucket}_cents"
    claimed = await db.wallets.find_one_and_update(
        {"id": wallet["id"], from_field: {"$gte": amount_cents}},
        {"$inc": {from_field: -amount_cents, to_field: amount_cents}},
    )
    if not claimed:
        await db.wallet_transactions.update_one({"id": txn["id"]}, {"$set": {"status": "FAILED", "updated_at": now()}})
        raise InsufficientFundsError(f"Saldo insuficiente em {from_bucket}.")

    await db.wallet_transactions.update_one({"id": txn["id"]}, {"$set": {"status": "COMPLETED", "updated_at": now()}})
    txn["status"] = "COMPLETED"
    txn.pop("_id", None)
    return txn


async def mark_transaction(txn_id: str, status: str):
    await db.wallet_transactions.update_one({"id": txn_id}, {"$set": {"status": status, "updated_at": now()}})


DEFAULT_FINANCIAL_CONFIG = {
    "id": "financial", "commission_percent": 12.0, "min_withdrawal": 20.0,
    "max_withdrawal_per_day": 5000.0, "max_deposit_per_transaction": 10000.0,
}


async def get_commission_config() -> dict:
    config = await db.platform_config.find_one({"id": "financial"}, {"_id": 0})
    return config or dict(DEFAULT_FINANCIAL_CONFIG)
