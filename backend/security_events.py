"""Immutable audit trail for sensitive actions taken BY a regular user (as opposed
to `admin_actions` in routes/admin.py, which logs actions taken ON users BY an
admin). Same shape, same "never editable by the user" rule — this only ever gets
inserted into, never updated.
"""
from database import db, new_id, now


async def log_security_event(user_id: str, event: str, detail: str = "", ip: str | None = None):
    await db.security_events.insert_one({
        "id": new_id(), "user_id": user_id, "event": event, "detail": detail,
        "ip": ip, "created_at": now(),
    })
