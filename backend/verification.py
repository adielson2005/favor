"""Real, hash-backed, single-use, attempt-limited, auto-expiring verification codes for
email, phone, and password-reset flows — one collection (`verification_tokens`) instead
of three sets of loose fields on the user document. Requesting a new code invalidates
any still-pending code of the same type, so only the latest code issued can ever work.

Also owns `account_status`: a stored field (not purely derived) so an admin's
SUSPENDED/BLOCKED decision can never be silently overwritten by a user completing
email/phone verification.
"""
import time
from typing import Optional

from fastapi import HTTPException

from auth import generate_otp, hash_password, verify_password
from database import db, new_id, now

MAX_ATTEMPTS = 5

TYPE_EMAIL = "EMAIL"
TYPE_PHONE = "PHONE"
TYPE_PASSWORD_RESET = "PASSWORD_RESET"

ACCOUNT_STATUSES = ("PENDING_VERIFICATION", "ACTIVE", "SUSPENDED", "BLOCKED")


async def create_verification_token(user_id: str, type_: str, ttl_seconds: int) -> str:
    # A fresh request supersedes anything still pending for this type — marking the old
    # row "used" makes it permanently unusable, so a leaked/old code stops working the
    # instant a new one is issued, not just when it naturally expires.
    await db.verification_tokens.update_many(
        {"user_id": user_id, "type": type_, "used_at": None},
        {"$set": {"used_at": now()}},
    )
    code = generate_otp()
    await db.verification_tokens.insert_one({
        "id": new_id(), "user_id": user_id, "type": type_,
        "token_hash": hash_password(code), "expires_at": time.time() + ttl_seconds,
        "used_at": None, "attempts": 0, "max_attempts": MAX_ATTEMPTS,
        "created_at": now(), "verified_at": None,
    })
    return code


async def verify_token(user_id: str, type_: str, code: str) -> None:
    """Raises HTTPException on any failure; returns normally only once the code is
    confirmed correct, unexpired, unused, and under the attempt limit — and marks it
    used_at in that same success path, so it can never be replayed."""
    token = await db.verification_tokens.find_one(
        {"user_id": user_id, "type": type_, "used_at": None},
        sort=[("created_at", -1)],
    )
    if not token:
        raise HTTPException(400, "Solicite um novo código antes de verificar.")
    if time.time() > token["expires_at"]:
        raise HTTPException(400, "Esse código expirou. Solicite um novo.")
    if token["attempts"] >= token["max_attempts"]:
        raise HTTPException(429, "Muitas tentativas com este código. Solicite um novo.")
    if not verify_password(code, token["token_hash"]):
        await db.verification_tokens.update_one({"id": token["id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, "Código incorreto.")
    await db.verification_tokens.update_one({"id": token["id"]}, {"$set": {"used_at": now(), "verified_at": now()}})


async def promote_if_verified(user_id: str) -> None:
    """Call after a successful email or phone verification. Activates the account only
    when BOTH are now verified AND it's still in its default pending state — a user
    finishing verification must never silently lift an admin's SUSPENDED/BLOCKED."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        return
    if user.get("verified_email") and user.get("verified_phone") and user.get("account_status") == "PENDING_VERIFICATION":
        await db.users.update_one({"id": user_id}, {"$set": {"account_status": "ACTIVE"}})


def require_active_account(user: dict) -> None:
    if user.get("account_status") != "ACTIVE":
        raise HTTPException(403, "Confirme seu e-mail e telefone para continuar. Verifique em Configurações > Segurança.")
