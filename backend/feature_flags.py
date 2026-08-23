"""Feature flags — lets the admin panel turn app-facing capabilities on/off
without a new release. `db.feature_flags` is the single source of truth; the
consumer app reads the current state via GET /bootstrap (see routes/public.py).
"""
from database import db, now


async def get_flags() -> dict:
    """Returns {key: enabled} for every known flag."""
    docs = await db.feature_flags.find({}, {"_id": 0}).to_list(200)
    return {d["key"]: d["enabled"] for d in docs}


async def list_flags() -> list[dict]:
    return await db.feature_flags.find({}, {"_id": 0}).sort("key", 1).to_list(200)


async def set_flag(key: str, enabled: bool, admin_id: str) -> dict:
    await db.feature_flags.update_one(
        {"key": key},
        {"$set": {"enabled": enabled, "updated_at": now(), "updated_by": admin_id}},
        upsert=True,
    )
    return await db.feature_flags.find_one({"key": key}, {"_id": 0})
