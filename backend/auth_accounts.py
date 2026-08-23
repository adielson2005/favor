"""Links a user to the credentials that can authenticate as them (password, Google
sub, ...) — one row per method instead of overloading `users.password_hash`/email
matching for identity. The (provider, provider_account_id) unique index is what
actually guarantees a given Google account can never end up linked to two different
FAZUM users, even under a race.
"""
from typing import Optional

from fastapi import HTTPException

from database import db, new_id, now

PROVIDER_PASSWORD = "PASSWORD"
PROVIDER_GOOGLE = "GOOGLE"


async def link_account(user_id: str, provider: str, provider_account_id: str) -> None:
    existing = await db.auth_accounts.find_one({"provider": provider, "provider_account_id": provider_account_id})
    if existing:
        if existing["user_id"] != user_id:
            raise HTTPException(409, "Essa conta já está vinculada a outro usuário.")
        return  # already linked to this same user — nothing to do
    await db.auth_accounts.insert_one({
        "id": new_id(), "user_id": user_id, "provider": provider, "provider_account_id": provider_account_id,
        "created_at": now(), "updated_at": now(),
    })


async def find_user_id_by_account(provider: str, provider_account_id: str) -> Optional[str]:
    row = await db.auth_accounts.find_one({"provider": provider, "provider_account_id": provider_account_id})
    return row["user_id"] if row else None


async def list_accounts(user_id: str) -> list[dict]:
    return await db.auth_accounts.find({"user_id": user_id}, {"_id": 0}).to_list(20)


async def unlink_account(user_id: str, provider: str) -> None:
    accounts = await list_accounts(user_id)
    remaining_others = [a for a in accounts if a["provider"] != provider]
    user = await db.users.find_one({"id": user_id}, {"password_hash": 1})
    has_password = bool((user or {}).get("password_hash"))
    if not remaining_others and not has_password:
        raise HTTPException(400, "Esse é seu único método de login. Crie uma senha antes de desvincular.")
    result = await db.auth_accounts.delete_many({"user_id": user_id, "provider": provider})
    if result.deleted_count == 0:
        raise HTTPException(404, "Esse método não está vinculado à sua conta.")
