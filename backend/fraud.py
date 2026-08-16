"""Deliberately simple, rule-based risk checks — a starting point to evolve, not a
real risk engine. Anything flagged HIGH or REVIEW_REQUIRED blocks automatic
processing and routes to admin review instead; the fail-safe rule for this whole
module is "when in doubt, don't move money automatically."
"""
from database import db, now

LOW, MEDIUM, HIGH, REVIEW_REQUIRED = "LOW", "MEDIUM", "HIGH", "REVIEW_REQUIRED"

LARGE_WITHDRAWAL_CENTS = 100_000  # R$1000
NEW_BANK_ACCOUNT_HOURS = 24
MAX_WITHDRAWALS_PER_DAY = 5


async def check_withdrawal_risk(user: dict, amount_cents: int, bank_account: dict) -> str:
    reasons = []
    if amount_cents >= LARGE_WITHDRAWAL_CENTS:
        reasons.append("large_amount")

    added_at = bank_account.get("created_at")
    if added_at:
        from datetime import datetime, timezone
        try:
            age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(added_at)).total_seconds() / 3600
            if age_hours < NEW_BANK_ACCOUNT_HOURS:
                reasons.append("new_bank_account")
        except ValueError:
            pass

    since = now()[:10]  # today, ISO date prefix — good enough for a simple daily count
    recent_count = await db.withdrawals.count_documents({"user_id": user["id"], "created_at": {"$gte": since}})
    if recent_count >= MAX_WITHDRAWALS_PER_DAY:
        reasons.append("too_many_withdrawals_today")

    if not user.get("verified_email"):
        reasons.append("unverified_email")

    if len(reasons) >= 2 or "too_many_withdrawals_today" in reasons:
        return REVIEW_REQUIRED
    if reasons:
        return MEDIUM
    return LOW


async def check_payment_risk(user: dict, amount_cents: int) -> str:
    if amount_cents >= 500_000:  # R$5000 — well above typical FAZÊ order sizes
        return REVIEW_REQUIRED
    if amount_cents >= 100_000:
        return MEDIUM
    return LOW
