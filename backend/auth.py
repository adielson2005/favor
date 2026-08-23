import os
import random
import time
from typing import Optional

import bcrypt
import jwt
from fastapi import Header, HTTPException

from database import db

OTP_TTL_SECONDS = 10 * 60  # 10 minutes


def generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def time_now() -> float:
    return time.time()


def time_now_plus(seconds: int) -> float:
    return time.time() + seconds

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def create_token(user_id: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "tv": token_version, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> tuple[str, int]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessão inválida. Entre novamente.")
    # Tokens issued before token_version existed carry no "tv" claim — treat as version 0,
    # matching the default for accounts that have never had a session-revoking event.
    return payload["sub"], payload.get("tv", 0)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "É preciso estar conectado.")
    user_id, token_version = decode_token(authorization.split(" ", 1)[1].strip())
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(401, "Sessão inválida. Entre novamente.")
    if token_version != user.get("token_version", 0):
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    if user.get("blocked"):
        raise HTTPException(403, "Sua conta está bloqueada. Fale com o suporte.")
    return user


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


# ---------- rate limiting (single-instance, in-memory sliding window) ----------

_attempts: dict[str, list[float]] = {}


def rate_limit(key: str, max_attempts: int = 10, window_seconds: int = 300):
    now = time.time()
    bucket = [t for t in _attempts.get(key, []) if now - t < window_seconds]
    if len(bucket) >= max_attempts:
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente novamente.")
    bucket.append(now)
    _attempts[key] = bucket
