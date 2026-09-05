"""Platform-wide metrics for the admin "Índice FAZUM" dashboard — aggregate/
marketplace-health numbers, distinct from `trust_index.py` (per-user, internal)
and `routes/public.py`'s `user_stats` (per-user, public reputation). Every rate
here is defined precisely against real fields; where a requested metric can't be
measured honestly with what's stored today, the definition says so explicitly
rather than faking it with a misleading proxy (see ACCEPTED_AT_NOTE below).

Nothing here is cached — at current data volumes (low thousands of orders) every
query is a single collection scan or a small group-by, comfortably fast enough to
compute fresh on every request. Revisit only if volume grows by orders of
magnitude (see the migration plan's Parauapebas-first, city-by-city rollout).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi.concurrency import run_in_threadpool

import geo_catalog_repo as geo_repo
from database import db

ACCEPTED_AT_NOTE = (
    "accepted_at só existe em pedidos aceitos após a introdução deste campo — "
    "pedidos aceitos antes disso são ignorados nesta métrica, nunca estimados."
)

ACTIVE_WINDOW_DAYS = 30  # fixed, independent of the report's own `days` filter
TOP_CATEGORIES_LIMIT = 10
TOP_NEIGHBORHOODS_LIMIT = 20

# Índice FAZUM weights — simple, additive/subtractive, always returned with the
# per-factor breakdown that produced them. Not a claim of statistical rigor, just
# a transparent starting formula (same philosophy as trust_index.py).
FAZUM_BASELINE = 50
FAZUM_WEIGHT_RESOLUTION = 25
FAZUM_WEIGHT_RECURRING = 15
FAZUM_WEIGHT_CANCELLATION = -20
FAZUM_WEIGHT_DISPUTE = -15

NON_PUBLISHED_STATUSES = ["accepted", "in_progress", "completion_requested", "completed", "cancelled", "disputed"]


def _since_iso(days: Optional[int]) -> Optional[str]:
    if not days:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _parse(iso_str) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None


def _avg_hours(pairs: list[tuple[Optional[str], Optional[str]]]) -> tuple[Optional[float], int, int]:
    """pairs of (start_iso, end_iso). Returns (avg_hours, n_used, n_skipped)."""
    deltas = []
    skipped = 0
    for start, end in pairs:
        start_dt, end_dt = _parse(start), _parse(end)
        if not start_dt or not end_dt:
            skipped += 1
            continue
        hours = (end_dt - start_dt).total_seconds() / 3600
        if hours < 0:  # defensive, matches user_stats' guard against bad/legacy data
            skipped += 1
            continue
        deltas.append(hours)
    if not deltas:
        return None, 0, skipped
    return round(sum(deltas) / len(deltas), 1), len(deltas), skipped


async def _resolution_and_cancellation(order_match: dict) -> dict:
    terminal_match = {**order_match, "status": {"$in": ["completed", "cancelled"]}}
    completed = await db.orders.count_documents({**order_match, "status": "completed"})
    cancelled = await db.orders.count_documents({**order_match, "status": "cancelled"})
    total = completed + cancelled
    return {
        "completed": completed, "cancelled": cancelled, "total_terminal": total,
        "resolution_rate": round(completed / total, 3) if total else None,
        "cancellation_rate": round(cancelled / total, 3) if total else None,
    }


async def _avg_hours_to_first_proposal(order_match: dict) -> dict:
    pipeline = [
        {"$group": {"_id": "$order_id", "first_proposal_at": {"$min": "$created_at"}}},
    ]
    rows = await db.proposals.aggregate(pipeline).to_list(10000)
    order_ids = [r["_id"] for r in rows]
    orders_by_id = {
        o["id"]: o["created_at"]
        async for o in db.orders.find({"id": {"$in": order_ids}, **order_match}, {"_id": 0, "id": 1, "created_at": 1})
    }
    pairs = [(orders_by_id[r["_id"]], r["first_proposal_at"]) for r in rows if r["_id"] in orders_by_id]
    avg, n, skipped = _avg_hours(pairs)
    return {"avg_hours_to_first_proposal": avg, "sample_size": n}


async def _hire_and_completion_timings(order_match: dict) -> dict:
    fields = {"_id": 0, "created_at": 1, "accepted_at": 1, "started_at": 1, "completed_at": 1}
    orders = await db.orders.find(order_match, fields).to_list(100000)

    hire_pairs = [(o["created_at"], o["accepted_at"]) for o in orders if o.get("accepted_at")]
    avg_hire, n_hire, skipped_hire = _avg_hours(hire_pairs)

    completed_orders = [o for o in orders if o.get("completed_at")]
    hire_to_completion_pairs = [(o["accepted_at"], o["completed_at"]) for o in completed_orders if o.get("accepted_at")]
    avg_hire_to_completion, n_hire_to_completion, _ = _avg_hours(hire_to_completion_pairs)

    start_to_completion_pairs = [(o["started_at"], o["completed_at"]) for o in completed_orders if o.get("started_at")]
    avg_start_to_completion, n_start_to_completion, _ = _avg_hours(start_to_completion_pairs)

    return {
        "avg_hours_to_hire": avg_hire, "hire_sample_size": n_hire, "hire_sample_missing_accepted_at": skipped_hire,
        "avg_hours_hire_to_completion": avg_hire_to_completion, "hire_to_completion_sample_size": n_hire_to_completion,
        "avg_hours_start_to_completion": avg_start_to_completion, "start_to_completion_sample_size": n_start_to_completion,
    }


async def _dispute_rate(order_match: dict, dispute_match: dict) -> dict:
    denom_match = {**order_match, "status": {"$in": NON_PUBLISHED_STATUSES}}
    denominator = await db.orders.count_documents(denom_match)
    disputed_order_ids = set(await db.disputes.distinct("order_id", dispute_match))
    if denominator and disputed_order_ids:
        eligible_ids = set(await db.orders.distinct("id", denom_match))
        disputed_order_ids &= eligible_ids
    return {
        "disputed_orders": len(disputed_order_ids), "eligible_orders": denominator,
        "dispute_rate": round(len(disputed_order_ids) / denominator, 3) if denominator else None,
    }


async def _recurring_client_rate(order_match: dict) -> dict:
    pipeline = [{"$match": order_match}, {"$group": {"_id": "$client_id", "n": {"$sum": 1}}}]
    rows = await db.orders.aggregate(pipeline).to_list(100000)
    if not rows:
        return {"recurring_client_rate": None, "distinct_clients": 0}
    recurring = sum(1 for r in rows if r["n"] > 1)
    return {"recurring_client_rate": round(recurring / len(rows), 3), "distinct_clients": len(rows)}


async def _active_users() -> dict:
    since = _since_iso(ACTIVE_WINDOW_DAYS)
    active_clients = await db.orders.distinct("client_id", {"created_at": {"$gte": since}})
    active_workers_from_orders = await db.orders.distinct(
        "worker_id", {"worker_id": {"$ne": None}, "created_at": {"$gte": since}},
    )
    active_workers_from_proposals = await db.proposals.distinct("worker_id", {"created_at": {"$gte": since}})
    return {
        "active_clients_30d": len(set(active_clients)),
        "active_workers_30d": len(set(active_workers_from_orders) | set(active_workers_from_proposals)),
    }


async def _neighborhoods_served(order_match: dict) -> int:
    served_match = {**order_match, "status": {"$ne": "published"}, "neighborhood_id": {"$ne": None}}
    ids = await db.orders.distinct("neighborhood_id", served_match)
    return len(ids)


async def _categories_top(order_match: dict) -> list[dict]:
    pipeline = [
        {"$match": order_match},
        {"$group": {
            "_id": "$category_id", "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
        }},
        {"$sort": {"total": -1}}, {"$limit": TOP_CATEGORIES_LIMIT},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(TOP_CATEGORIES_LIMIT)
    if geo_repo.GEO_CATALOG_BACKEND == "postgres":
        cats, _, _, _ = await run_in_threadpool(geo_repo.load_ref_maps)
    else:
        cat_ids = [r["_id"] for r in rows if r["_id"]]
        cats = {c["id"]: c async for c in db.categories.find({"id": {"$in": cat_ids}}, {"_id": 0})}
    out = []
    for r in rows:
        cat = cats.get(r["_id"], {})
        terminal = r["completed"] + r["cancelled"]
        out.append({
            "category_id": r["_id"], "name": cat.get("name", r["_id"] or "—"),
            "total_orders": r["total"], "completed_orders": r["completed"],
            "success_rate": round(r["completed"] / terminal, 3) if terminal else None,
        })
    return out


async def _demand_supply_by_neighborhood(order_match: dict) -> list[dict]:
    demand_rows = await db.orders.aggregate([
        {"$match": order_match},
        {"$group": {"_id": "$neighborhood_id", "demand": {"$sum": 1}}},
    ]).to_list(10000)
    supply_rows = await db.orders.aggregate([
        {"$match": {**order_match, "worker_id": {"$ne": None}}},
        {"$group": {"_id": "$neighborhood_id", "supply": {"$addToSet": "$worker_id"}}},
    ]).to_list(10000)
    supply_by_hood = {r["_id"]: len(r["supply"]) for r in supply_rows}
    if geo_repo.GEO_CATALOG_BACKEND == "postgres":
        _, _, hoods, _ = await run_in_threadpool(geo_repo.load_ref_maps)
    else:
        hood_ids = [r["_id"] for r in demand_rows if r["_id"]]
        hoods = {n["id"]: n async for n in db.neighborhoods.find({"id": {"$in": hood_ids}}, {"_id": 0})}
    out = [
        {
            "neighborhood_id": r["_id"], "name": hoods.get(r["_id"], {}).get("name", r["_id"] or "—"),
            "demand": r["demand"], "supply": supply_by_hood.get(r["_id"], 0),
        }
        for r in demand_rows if r["_id"]
    ]
    out.sort(key=lambda x: x["demand"], reverse=True)
    return out[:TOP_NEIGHBORHOODS_LIMIT]


def _fazum_index(resolution_rate, recurring_client_rate, cancellation_rate, dispute_rate) -> dict:
    factors = []
    score = FAZUM_BASELINE
    if resolution_rate is not None:
        contrib = FAZUM_WEIGHT_RESOLUTION * resolution_rate
        score += contrib
        factors.append({"reason": "resolution_rate", "weight": round(contrib, 1), "detail": f"{round(resolution_rate * 100)}% dos pedidos concluídos"})
    if recurring_client_rate is not None:
        contrib = FAZUM_WEIGHT_RECURRING * recurring_client_rate
        score += contrib
        factors.append({"reason": "recurring_client_rate", "weight": round(contrib, 1), "detail": f"{round(recurring_client_rate * 100)}% de clientes recorrentes"})
    if cancellation_rate is not None:
        contrib = FAZUM_WEIGHT_CANCELLATION * cancellation_rate
        score += contrib
        factors.append({"reason": "cancellation_rate", "weight": round(contrib, 1), "detail": f"{round(cancellation_rate * 100)}% de cancelamento"})
    if dispute_rate is not None:
        contrib = FAZUM_WEIGHT_DISPUTE * dispute_rate
        score += contrib
        factors.append({"reason": "dispute_rate", "weight": round(contrib, 1), "detail": f"{round(dispute_rate * 100)}% de disputa entre pedidos aceitos ou além"})
    return {"score": round(max(0, min(100, score)), 1), "factors": factors}


async def _revenue_and_gmv(payment_updated_match: dict) -> dict:
    match = {**payment_updated_match, "status": "released"}
    pipeline = [{"$match": match}, {"$group": {
        "_id": None, "commission_total": {"$sum": "$commission_amount"},
        "gross_total": {"$sum": "$gross_amount"}, "n": {"$sum": 1},
    }}]
    rows = await db.payments.aggregate(pipeline).to_list(1)
    row = rows[0] if rows else {"commission_total": 0, "gross_total": 0, "n": 0}
    return {
        "revenue": {"commission_total": row["commission_total"], "payments_count": row["n"]},
        "gmv": {"gross_total": row["gross_total"]},
    }


async def compute_platform_metrics(days: Optional[int] = None) -> dict:
    since = _since_iso(days)
    order_match: dict = {"created_at": {"$gte": since}} if since else {}
    dispute_match: dict = {"created_at": {"$gte": since}} if since else {}
    payment_match: dict = {"updated_at": {"$gte": since}} if since else {}

    resolution = await _resolution_and_cancellation(order_match)
    first_proposal = await _avg_hours_to_first_proposal(order_match)
    timings = await _hire_and_completion_timings(order_match)
    dispute = await _dispute_rate(order_match, dispute_match)
    recurring = await _recurring_client_rate(order_match)
    active = await _active_users()
    neighborhoods_served = await _neighborhoods_served(order_match)
    jobs_completed = resolution["completed"]

    fazum_index = _fazum_index(
        resolution["resolution_rate"], recurring["recurring_client_rate"],
        resolution["cancellation_rate"], dispute["dispute_rate"],
    )

    categories_top = await _categories_top(order_match)
    demand_supply = await _demand_supply_by_neighborhood(order_match)
    revenue_gmv = await _revenue_and_gmv(payment_match)

    return {
        "window_days": days,
        "active_window_days": ACTIVE_WINDOW_DAYS,
        "operational": {
            "resolution_rate": resolution["resolution_rate"],
            "cancellation_rate": resolution["cancellation_rate"],
            "dispute_rate": dispute["dispute_rate"],
            "avg_hours_to_first_proposal": first_proposal["avg_hours_to_first_proposal"],
            "avg_hours_to_hire": timings["avg_hours_to_hire"],
            "avg_hours_hire_to_completion": timings["avg_hours_hire_to_completion"],
            "avg_hours_start_to_completion": timings["avg_hours_start_to_completion"],
            "recurring_client_rate": recurring["recurring_client_rate"],
            "active_clients_30d": active["active_clients_30d"],
            "active_workers_30d": active["active_workers_30d"],
            "neighborhoods_served": neighborhoods_served,
            "jobs_completed": jobs_completed,
            "accepted_at_note": ACCEPTED_AT_NOTE,
        },
        "categories_top": categories_top,
        "demand_supply_by_neighborhood": demand_supply,
        "fazum_index": fazum_index,
        **revenue_gmv,  # "revenue" / "gmv" keys — stripped by the route if the caller lacks payments.view
    }
