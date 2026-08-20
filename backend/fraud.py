"""Rule-based risk engine — deliberately simple and extensible, not a real ML risk
model. Every signal is a named "reason" with a weight; reasons are summed into a
score and mapped to one of four levels. Extending it means adding one more signal
function and a weight, not restructuring the module — that's the point.

Fail-safe rule for this whole module: "when in doubt, don't move money automatically."
No single weak signal alone should ever reach CRITICAL — that only happens when
several signals combine, per the "never block on one indicator alone" rule.
"""
from datetime import datetime, timezone
from typing import Optional

from database import db, new_id, now

LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"

LARGE_WITHDRAWAL_CENTS = 100_000  # R$1000
MEDIUM_PAYMENT_CENTS = 100_000  # R$1000
LARGE_PAYMENT_CENTS = 500_000  # R$5000
NEW_ACCOUNT_HOURS = 24
NEW_BANK_ACCOUNT_HOURS = 24
MAX_WITHDRAWALS_PER_DAY = 5
HIGH_CANCELLATION_RATE = 0.5
MANY_DISPUTES = 3
MANY_REPORTS = 3
AMOUNT_VS_HISTORY_MULTIPLIER = 5

# Each reason's contribution to the score. Weak/behavioral signals (new account,
# new bank account, unverified email) are deliberately worth too little to trigger
# anything on their own — every real user is a "new account" once, and that alone
# must never add friction to an ordinary payment. Only amount-based reasons or a
# genuine combination of weak signals cross into MEDIUM+.
REASON_WEIGHTS = {
    "new_account": 1,
    "new_bank_account": 1,
    "unverified_email": 1,
    "large_amount": 2,
    "very_large_amount": 4,
    "too_many_withdrawals_today": 3,
    "high_cancellation_rate": 2,
    "many_disputes": 2,
    "many_reports": 3,
    "amount_far_above_history": 1,
    "external_payment_flagged": 2,
}

MEDIUM_THRESHOLD = 2
HIGH_THRESHOLD = 4
CRITICAL_THRESHOLD = 7


def _level_for_reasons(reasons: list[str]) -> str:
    score = sum(REASON_WEIGHTS.get(r, 1) for r in reasons)
    if score >= CRITICAL_THRESHOLD:
        return CRITICAL
    if score >= HIGH_THRESHOLD:
        return HIGH
    if score >= MEDIUM_THRESHOLD:
        return MEDIUM
    return LOW


def _hours_since(iso_str: Optional[str]) -> Optional[float]:
    if not iso_str:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso_str)).total_seconds() / 3600
    except ValueError:
        return None


async def _cancellation_rate(user_id: str) -> float:
    query = {"$or": [{"client_id": user_id}, {"worker_id": user_id}]}
    total = await db.orders.count_documents(query)
    if not total:
        return 0.0
    cancelled = await db.orders.count_documents({**query, "status": "cancelled"})
    return cancelled / total


async def _dispute_count(user_id: str) -> int:
    order_ids = [o["id"] async for o in db.orders.find({"$or": [{"client_id": user_id}, {"worker_id": user_id}]}, {"id": 1})]
    if not order_ids:
        return 0
    return await db.disputes.count_documents({"order_id": {"$in": order_ids}})


async def _reports_against(user_id: str) -> int:
    return await db.reports.count_documents({"target_type": "user", "target_id": user_id, "status": {"$ne": "REJECTED"}})


async def _avg_payment_cents(user_id: str) -> Optional[int]:
    amounts = [p["gross_amount"] async for p in db.payments.find({"client_id": user_id, "status": {"$ne": "pending"}}, {"gross_amount": 1}).limit(50)]
    if not amounts:
        return None
    return round((sum(amounts) / len(amounts)) * 100)


async def create_risk_flag(user_id: str, kind: str, reference_id: str, level: str, reasons: list[str]) -> dict:
    flag = {
        "id": new_id(), "user_id": user_id, "kind": kind, "reference_id": reference_id,
        "level": level, "reasons": reasons, "status": "OPEN", "created_at": now(),
    }
    await db.risk_flags.insert_one(dict(flag))
    flag.pop("_id", None)
    return flag


async def check_withdrawal_risk(user: dict, amount_cents: int, bank_account: dict, client_ip: Optional[str] = None) -> tuple[str, list[str]]:
    reasons = []
    if amount_cents >= LARGE_WITHDRAWAL_CENTS:
        reasons.append("large_amount")

    age_hours = _hours_since(user.get("created_at"))
    if age_hours is not None and age_hours < NEW_ACCOUNT_HOURS:
        reasons.append("new_account")

    bank_age_hours = _hours_since(bank_account.get("created_at"))
    if bank_age_hours is not None and bank_age_hours < NEW_BANK_ACCOUNT_HOURS:
        reasons.append("new_bank_account")

    since = now()[:10]  # today, ISO date prefix — good enough for a simple daily count
    recent_count = await db.withdrawals.count_documents({"user_id": user["id"], "created_at": {"$gte": since}})
    if recent_count >= MAX_WITHDRAWALS_PER_DAY:
        reasons.append("too_many_withdrawals_today")

    if not user.get("verified_email"):
        reasons.append("unverified_email")

    if await _cancellation_rate(user["id"]) >= HIGH_CANCELLATION_RATE:
        reasons.append("high_cancellation_rate")

    if await _dispute_count(user["id"]) >= MANY_DISPUTES:
        reasons.append("many_disputes")

    if await _reports_against(user["id"]) >= MANY_REPORTS:
        reasons.append("many_reports")

    return _level_for_reasons(reasons), reasons


async def check_payment_risk(user: dict, amount_cents: int, order: dict, client_ip: Optional[str] = None) -> tuple[str, list[str]]:
    reasons = []
    if amount_cents >= LARGE_PAYMENT_CENTS:
        reasons.append("very_large_amount")
    elif amount_cents >= MEDIUM_PAYMENT_CENTS:
        reasons.append("large_amount")

    age_hours = _hours_since(user.get("created_at"))
    if age_hours is not None and age_hours < NEW_ACCOUNT_HOURS:
        reasons.append("new_account")

    if await _cancellation_rate(user["id"]) >= HIGH_CANCELLATION_RATE:
        reasons.append("high_cancellation_rate")

    if await _dispute_count(user["id"]) >= MANY_DISPUTES:
        reasons.append("many_disputes")

    if await _reports_against(user["id"]) >= MANY_REPORTS:
        reasons.append("many_reports")

    avg_cents = await _avg_payment_cents(user["id"])
    if avg_cents and amount_cents >= avg_cents * AMOUNT_VS_HISTORY_MULTIPLIER:
        reasons.append("amount_far_above_history")

    if any((order.get("external_payment_flags") or {}).values()):
        reasons.append("external_payment_flagged")

    return _level_for_reasons(reasons), reasons
