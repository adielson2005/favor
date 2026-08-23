"""Admin-panel authentication — entirely separate from the consumer `auth.py`.

Admin sessions live in `db.admin_users` (never `db.users`), carry their own JWT
claim (`typ: "admin"`) so a leaked/reused consumer token can never authenticate
here (and vice versa), and are checked against a role's permission set resolved
from `admin_permissions.py` on every request — the frontend hides screens a
caller can't use, but this is the only real gate.
"""
import time
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException

from admin_permissions import has_permission, permissions_for_role
from auth import JWT_ALG, JWT_SECRET, hash_password, verify_password  # noqa: F401 (re-exported for callers)
from database import db, now

ADMIN_TOKEN_TTL_SECONDS = 12 * 3600  # 12h — a staff tool, re-login is cheap and safer than a 30-day session
PRESENCE_THROTTLE_SECONDS = 60  # how often last_active_at actually writes to the DB
ONLINE_WINDOW_SECONDS = 5 * 60  # "online" in the supervision view = active within this window


def create_admin_token(admin_id: str, token_version: int = 0) -> str:
    payload = {
        "sub": admin_id, "typ": "admin", "tv": token_version,
        "iat": int(time.time()), "exp": int(time.time()) + ADMIN_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_admin_token(token: str) -> tuple[str, int]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessão administrativa inválida. Entre novamente.")
    if payload.get("typ") != "admin":
        # A well-formed consumer-app token decoded fine but isn't an admin session —
        # reject explicitly instead of ever treating one as the other.
        raise HTTPException(401, "Sessão administrativa inválida. Entre novamente.")
    return payload["sub"], payload.get("tv", 0)


async def get_current_admin_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "É preciso estar conectado ao painel administrativo.")
    admin_id, token_version = decode_admin_token(authorization.split(" ", 1)[1].strip())
    admin = await db.admin_users.find_one({"id": admin_id})
    if not admin:
        raise HTTPException(401, "Sessão administrativa inválida. Entre novamente.")
    if token_version != admin.get("token_version", 0):
        raise HTTPException(401, "Sessão administrativa expirada. Entre novamente.")
    if not admin.get("active", True):
        raise HTTPException(403, "Esta conta administrativa foi desativada.")
    admin["permissions"] = permissions_for_role(admin.get("role", ""))
    await _touch_presence(admin)
    return admin


async def _touch_presence(admin: dict) -> None:
    """Cheap presence heartbeat for the OWNER supervision view — throttled so this
    doesn't cost a write on every single authenticated request, just an approximate
    "active within the last minute or so" marker.
    """
    last = admin.get("last_active_at")
    stale = True
    if last:
        try:
            stale = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() > PRESENCE_THROTTLE_SECONDS
        except ValueError:
            stale = True
    if stale:
        ts = now()
        admin["last_active_at"] = ts
        await db.admin_users.update_one({"id": admin["id"]}, {"$set": {"last_active_at": ts}})


def require_permission(*keys: str):
    """FastAPI dependency factory — 403s unless the caller's role grants every key."""
    async def _checker(admin: dict = Depends(get_current_admin_user)) -> dict:
        granted = admin["permissions"]
        if not all(has_permission(granted, key) for key in keys):
            raise HTTPException(403, "Você não tem permissão para essa ação.")
        return admin
    return _checker


def require_any_permission(*keys: str):
    """Like require_permission, but 403s only if the caller has NONE of the keys —
    used for the tickets endpoints, which SUPPORT (support.view) and MAINTENANCE
    (maintenance.view) both reach, just scoped to a different slice of the data."""
    async def _checker(admin: dict = Depends(get_current_admin_user)) -> dict:
        granted = admin["permissions"]
        if not any(has_permission(granted, key) for key in keys):
            raise HTTPException(403, "Você não tem permissão para essa ação.")
        return admin
    return _checker
