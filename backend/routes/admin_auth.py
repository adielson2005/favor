from typing import Optional

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request

from admin_auth import create_admin_token, get_current_admin_user, hash_password, require_permission, verify_password
from admin_permissions import permissions_for_role
from auth import rate_limit
from database import db, new_id, now
from models import AdminLoginIn, Admin2FAVerifyIn, AdminUserCreateIn, AdminUserPatchIn
from routes.admin import log_action

router = APIRouter(prefix="/admin")


def admin_public(admin: dict) -> dict:
    granted = permissions_for_role(admin.get("role", ""))
    return {
        "id": admin["id"], "name": admin["name"], "email": admin["email"], "role": admin.get("role"),
        "active": admin.get("active", True), "totp_enabled": bool(admin.get("totp_enabled")),
        "last_login_at": admin.get("last_login_at"), "created_at": admin.get("created_at"),
        "permissions": ["*"] if granted == "*" else sorted(granted),
    }


async def _count_active_owners(exclude_id: Optional[str] = None) -> int:
    query = {"role": "OWNER", "active": True}
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    return await db.admin_users.count_documents(query)


# ---------- auth ----------

@router.post("/auth/login")
async def admin_login(body: AdminLoginIn, request: Request):
    ip = request.client.host if request.client else None
    email = body.email.lower()
    rate_limit(f"admin-login:{ip}:{email}", max_attempts=8, window_seconds=300)
    # Same IP-rotation gap as the consumer login (routes/auth.py) — a second bucket
    # keyed only on the email catches an attacker spreading attempts across many IPs
    # against the same admin account.
    rate_limit(f"admin-login-identifier:{email}", max_attempts=20, window_seconds=300)
    admin = await db.admin_users.find_one({"email": email})
    if not admin or not verify_password(body.password, admin["password_hash"]):
        if admin:
            await log_action(admin["id"], "ADMIN_LOGIN", f"admin:{admin['id']}", ip=ip, result="failure", metadata={"reason": "bad_credentials"})
        raise HTTPException(401, "E-mail ou senha incorretos.")
    if not admin.get("active", True):
        await log_action(admin["id"], "ADMIN_LOGIN", f"admin:{admin['id']}", ip=ip, result="failure", metadata={"reason": "inactive"})
        raise HTTPException(403, "Esta conta administrativa foi desativada.")
    if admin.get("totp_enabled"):
        code = (body.totp_code or "").strip()
        if not code or not pyotp.TOTP(admin["totp_secret"]).verify(code, valid_window=1):
            await log_action(admin["id"], "ADMIN_LOGIN", f"admin:{admin['id']}", ip=ip, result="failure", metadata={"reason": "totp"})
            raise HTTPException(401, "Código de autenticação de dois fatores inválido.")
    token = create_admin_token(admin["id"], admin.get("token_version", 0))
    await db.admin_users.update_one({"id": admin["id"]}, {"$set": {"last_login_at": now()}})
    await log_action(admin["id"], "ADMIN_LOGIN", f"admin:{admin['id']}", ip=ip, result="success")
    return {"token": token, "admin": admin_public(admin)}


@router.get("/auth/me")
async def admin_me(admin: dict = Depends(get_current_admin_user)):
    return admin_public(admin)


@router.post("/auth/logout")
async def admin_logout(request: Request, admin: dict = Depends(get_current_admin_user)):
    ip = request.client.host if request.client else None
    await db.admin_users.update_one({"id": admin["id"]}, {"$inc": {"token_version": 1}})
    await log_action(admin["id"], "ADMIN_LOGOUT", f"admin:{admin['id']}", ip=ip)
    return {"message": "Sessão encerrada."}


# ---------- 2FA (TOTP) — self-service, available to any admin account ----------

@router.post("/auth/2fa/setup")
async def admin_2fa_setup(admin: dict = Depends(get_current_admin_user)):
    rate_limit(f"admin-2fa-setup:{admin['id']}", max_attempts=10, window_seconds=600)
    secret = pyotp.random_base32()
    # Stored as "pending" until confirmed via /2fa/verify — never activates a secret
    # the caller hasn't proven they can actually generate codes with.
    await db.admin_users.update_one({"id": admin["id"]}, {"$set": {"totp_secret_pending": secret}})
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin["email"], issuer_name="FAZUM Admin")
    return {"secret": secret, "otpauth_url": uri}


@router.post("/auth/2fa/verify")
async def admin_2fa_verify(body: Admin2FAVerifyIn, admin: dict = Depends(get_current_admin_user)):
    rate_limit(f"admin-2fa-verify:{admin['id']}", max_attempts=10, window_seconds=600)
    pending = admin.get("totp_secret_pending")
    if not pending:
        raise HTTPException(400, "Nenhuma configuração de 2FA em andamento. Inicie novamente.")
    if not pyotp.TOTP(pending).verify((body.code or "").strip(), valid_window=1):
        raise HTTPException(401, "Código inválido. Tente novamente.")
    await db.admin_users.update_one({"id": admin["id"]}, {
        "$set": {"totp_secret": pending, "totp_enabled": True},
        "$unset": {"totp_secret_pending": ""},
    })
    await log_action(admin["id"], "ADMIN_2FA_ENABLED", f"admin:{admin['id']}")
    return {"message": "Autenticação de dois fatores ativada."}


@router.post("/auth/2fa/disable")
async def admin_2fa_disable(body: Admin2FAVerifyIn, admin: dict = Depends(get_current_admin_user)):
    rate_limit(f"admin-2fa-disable:{admin['id']}", max_attempts=5, window_seconds=600)
    if not admin.get("totp_enabled"):
        raise HTTPException(400, "A autenticação de dois fatores não está ativada.")
    # Disabling 2FA needs the SAME proof of possession that enabling it did — a
    # hijacked session token alone must never be enough to strip this protection.
    if not pyotp.TOTP(admin["totp_secret"]).verify((body.code or "").strip(), valid_window=1):
        raise HTTPException(401, "Código inválido.")
    await db.admin_users.update_one({"id": admin["id"]}, {
        "$set": {"totp_enabled": False}, "$unset": {"totp_secret": "", "totp_secret_pending": ""},
        "$inc": {"token_version": 1},  # force re-login everywhere — same as any other sensitive change
    })
    await log_action(admin["id"], "ADMIN_2FA_DISABLED", f"admin:{admin['id']}")
    return {"message": "Autenticação de dois fatores desativada."}


VALID_ROLES = ("OWNER", "MANAGER", "SUPPORT", "MAINTENANCE")

# ---------- team (OWNER manages MANAGER/SUPPORT/MAINTENANCE accounts) ----------

@router.get("/team")
async def list_team(admin: dict = Depends(require_permission("admin_team.view"))):
    members = await db.admin_users.find({}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "totp_secret_pending": 0}).sort("created_at", 1).to_list(200)
    return members


@router.post("/team")
async def create_team_member(body: AdminUserCreateIn, admin: dict = Depends(require_permission("admin_team.manage"))):
    rate_limit(f"admin-team-manage:{admin['id']}", max_attempts=150, window_seconds=600)
    if body.role not in VALID_ROLES:
        raise HTTPException(400, "Papel inválido.")
    email = body.email.lower()
    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(400, "Já existe uma conta administrativa com este e-mail.")
    member = {
        "id": new_id(), "name": body.name, "email": email, "password_hash": hash_password(body.password),
        "role": body.role, "active": True, "token_version": 0, "totp_enabled": False,
        "last_login_at": None, "created_at": now(), "updated_at": now(),
    }
    await db.admin_users.insert_one(dict(member))
    await log_action(admin["id"], "ADMIN_TEAM_CREATED", f"admin:{member['id']}", metadata={"role": body.role})
    return admin_public(member)


@router.patch("/team/{admin_id}")
async def patch_team_member(admin_id: str, body: AdminUserPatchIn, admin: dict = Depends(require_permission("admin_team.manage"))):
    rate_limit(f"admin-team-manage:{admin['id']}", max_attempts=150, window_seconds=600)
    target = await db.admin_users.find_one({"id": admin_id})
    if not target:
        raise HTTPException(404, "Conta administrativa não encontrada.")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data.get("role") not in (None,) + VALID_ROLES:
        raise HTTPException(400, "Papel inválido.")
    # Never let the last active OWNER lock everyone (including themselves) out —
    # same "don't remove the last way in" guard used for login-method unlinking.
    demoting_or_deactivating = (data.get("role") not in (None, "OWNER") and target.get("role") == "OWNER") or (data.get("active") is False and target.get("role") == "OWNER")
    if demoting_or_deactivating and await _count_active_owners(exclude_id=admin_id) == 0:
        raise HTTPException(400, "Não é possível remover o último administrador principal ativo.")
    if not data:
        return admin_public(target)
    data["updated_at"] = now()
    if data.get("active") is False:
        data["token_version"] = target.get("token_version", 0) + 1  # force logout
    await db.admin_users.update_one({"id": admin_id}, {"$set": data})
    await log_action(admin["id"], "ADMIN_TEAM_UPDATED", f"admin:{admin_id}", metadata=data)
    return admin_public(await db.admin_users.find_one({"id": admin_id}))


@router.post("/team/{admin_id}/revoke-sessions")
async def revoke_team_member_sessions(admin_id: str, admin: dict = Depends(require_permission("admin_team.manage"))):
    rate_limit(f"admin-team-manage:{admin['id']}", max_attempts=150, window_seconds=600)
    target = await db.admin_users.find_one({"id": admin_id})
    if not target:
        raise HTTPException(404, "Conta administrativa não encontrada.")
    await db.admin_users.update_one({"id": admin_id}, {"$inc": {"token_version": 1}})
    await log_action(admin["id"], "ADMIN_TEAM_SESSIONS_REVOKED", f"admin:{admin_id}")
    return {"message": "Sessões encerradas."}
