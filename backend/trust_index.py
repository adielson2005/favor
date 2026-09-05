"""Internal trust index — a staff-only signal (GREEN/YELLOW/RED) for an admin
manually reviewing an account, never shown to the end user and never wired to any
automatic action (no auto-block, no auto-status-change). Computed fresh on every
read, never persisted: a stored `trust_score` field would become a de facto
shadow ban-list the moment anyone writes a query against it, and would go stale
the instant a new risk_flags/report/dispute lands without a resync job.
Computing it on demand keeps it explicitly "how this looks right now," matching
its only intended use — a human deciding whether to look closer.

Reuses fraud.py's dispute_count/reports_against/cancellation_rate (exported,
no longer private) instead of duplicating those aggregations — they're the same
read-only counts, just weighted differently here (per-account snapshot for staff
review, not a per-event gate for money movement). This module depends on
fraud.py, never the reverse, so fraud.py's "never auto-block on one signal" gate
logic stays independent and legible on its own.
"""
from datetime import datetime, timezone
from typing import Optional

from database import db
from fraud import HIGH_CANCELLATION_RATE, MANY_DISPUTES, cancellation_rate, dispute_count, reports_against

GREEN, YELLOW, RED = "GREEN", "YELLOW", "RED"

MIN_ORDERS_FOR_CANCELLATION_SIGNAL = 5  # don't punish a brand-new account's first cancelled order as "100% cancellation"
REPORTS_AGAINST_CAP = 3  # cap contribution so one report-brigading campaign can't dominate the score
NEW_ACCOUNT_HOURS = 24
ESTABLISHED_ACCOUNT_DAYS = 30

YELLOW_THRESHOLD = 2
RED_THRESHOLD = 5


def _hours_since(iso_str: Optional[str]) -> Optional[float]:
    if not iso_str:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso_str)).total_seconds() / 3600
    except ValueError:
        return None


async def _open_risk_flags_by_level(user_id: str) -> dict[str, int]:
    counts = {"HIGH": 0, "CRITICAL": 0, "MEDIUM": 0}
    async for flag in db.risk_flags.find({"user_id": user_id, "status": "OPEN"}, {"_id": 0, "level": 1}):
        if flag["level"] in counts:
            counts[flag["level"]] += 1
    return counts


async def compute_trust_index(user_id: str) -> dict:
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise ValueError(f"Usuário {user_id} não encontrado.")

    factors: list[dict] = []
    score = 0

    risk_levels = await _open_risk_flags_by_level(user_id)
    high_critical = risk_levels["HIGH"] + risk_levels["CRITICAL"]
    if high_critical:
        weight = high_critical * 3
        score += weight
        factors.append({
            "reason": "open_risk_flags_high_or_critical", "weight": weight,
            "detail": f"{high_critical} alerta(s) de risco alto/crítico em aberto",
        })
    if risk_levels["MEDIUM"]:
        weight = risk_levels["MEDIUM"] * 1
        score += weight
        factors.append({
            "reason": "open_risk_flags_medium", "weight": weight,
            "detail": f"{risk_levels['MEDIUM']} alerta(s) de risco médio em aberto",
        })

    reports = min(await reports_against(user_id), REPORTS_AGAINST_CAP)
    if reports:
        weight = reports * 2
        score += weight
        factors.append({
            "reason": "reports_against", "weight": weight,
            "detail": f"{reports} denúncia(s) contra este usuário (teto de {REPORTS_AGAINST_CAP})",
        })

    disputes = await dispute_count(user_id)
    if disputes >= MANY_DISPUTES:
        score += 2
        factors.append({"reason": "many_disputes", "weight": 2, "detail": f"{disputes} disputas registradas"})

    total_orders = await db.orders.count_documents({"$or": [{"client_id": user_id}, {"worker_id": user_id}]})
    if total_orders >= MIN_ORDERS_FOR_CANCELLATION_SIGNAL:
        rate = await cancellation_rate(user_id)
        if rate >= HIGH_CANCELLATION_RATE:
            score += 2
            factors.append({
                "reason": "high_cancellation_rate", "weight": 2,
                "detail": f"taxa de cancelamento de {round(rate * 100)}% em {total_orders} pedidos",
            })

    age_hours = _hours_since(user.get("created_at"))
    is_new = age_hours is not None and age_hours < NEW_ACCOUNT_HOURS
    if is_new:
        score += 1
        factors.append({"reason": "new_account", "weight": 1, "detail": "conta criada há menos de 24 horas"})

    if not user.get("verified_email") or not user.get("verified_phone"):
        score += 1
        factors.append({"reason": "unverified_contact", "weight": 1, "detail": "e-mail ou telefone não verificado"})

    is_established = age_hours is not None and age_hours >= ESTABLISHED_ACCOUNT_DAYS * 24
    if user.get("verified_identity") and is_established and high_critical == 0 and risk_levels["MEDIUM"] == 0:
        score -= 2
        factors.append({
            "reason": "verified_and_established", "weight": -2,
            "detail": "identidade verificada, conta com 30+ dias, sem alertas de risco em aberto",
        })

    level = RED if score >= RED_THRESHOLD else YELLOW if score >= YELLOW_THRESHOLD else GREEN
    return {"level": level, "score": score, "factors": factors}
