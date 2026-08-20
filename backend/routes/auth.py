import os

from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from auth import (
    create_token, generate_otp, get_current_user, hash_password, rate_limit,
    time_now, time_now_plus, verify_password, OTP_TTL_SECONDS,
)
from database import db, new_id, now
from models import (
    ChangePasswordIn, ForgotPasswordIn, GoogleAuthIn, LoginIn, NotificationPrefsIn, PreferenceIn,
    RegisterIn, ResetPasswordIn, VerifyEmailIn,
)
from security_events import log_security_event

router = APIRouter(prefix="/auth")

# No transactional email provider is wired up yet (SendGrid/SES/SMTP). Until one is
# configured, verification/reset codes are returned directly in the API response
# instead of being emailed — same "clearly flagged as pending" pattern used for
# GOOGLE_CLIENT_ID. Flip EMAIL_DELIVERY_ENABLED once a real provider sends the code.
EMAIL_DELIVERY_ENABLED = os.environ.get("EMAIL_DELIVERY_ENABLED", "").lower() in ("1", "true", "yes")


def public_me(user: dict) -> dict:
    from routes.public import public_user

    return public_user(user)


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    rate_limit(f"register:{request.client.host if request.client else 'unknown'}", max_attempts=40, window_seconds=300)
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Já existe uma conta com este e-mail.")
    user = {
        "id": new_id(), "name": body.name.strip(), "email": email,
        "password_hash": hash_password(body.password),
        "initials": "".join(w[0] for w in body.name.strip().split()[:2]).upper() or "?",
        "bio": "", "rating": 5.0, "rating_count": 0, "jobs_done": 0,
        "city_id": body.city_id, "neighborhood_id": body.neighborhood_id,
        "preference": body.preference if body.preference in ("client", "worker", "both") else "both",
        "verified_email": False, "verified_phone": False, "verified_identity": False,
        "is_admin": False, "blocked": False, "member_since": now(), "is_demo": False,
        "created_at": now(),
    }
    await db.users.insert_one(dict(user))
    return {"token": create_token(user["id"], user.get("token_version", 0)), "user": public_me(user)}


@router.post("/login")
async def login(body: LoginIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    rate_limit(f"login:{ip}:{body.email.lower()}")
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    if user.get("blocked"):
        raise HTTPException(403, "Sua conta está bloqueada. Fale com o suporte.")
    await log_security_event(user["id"], "login", ip=ip)
    from routes.public import notify
    await notify(user["id"], "Novo login detectado", "Se não foi você, altere sua senha imediatamente.", "security")
    return {"token": create_token(user["id"], user.get("token_version", 0)), "user": public_me(user)}


@router.post("/google")
async def google_auth(body: GoogleAuthIn, request: Request):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(501, "Login com Google ainda não foi configurado neste servidor.")
    rate_limit(f"google:{request.client.host if request.client else 'unknown'}")
    try:
        payload = google_id_token.verify_oauth2_token(body.id_token, google_requests.Request(), client_id)
    except ValueError:
        raise HTTPException(401, "Não foi possível verificar sua conta Google.")
    if not payload.get("email_verified"):
        raise HTTPException(401, "Seu e-mail do Google precisa estar verificado.")
    email = payload["email"].lower()
    user = await db.users.find_one({"email": email})
    if user:
        if user.get("blocked"):
            raise HTTPException(403, "Sua conta está bloqueada. Fale com o suporte.")
        if not user.get("verified_email"):
            await db.users.update_one({"id": user["id"]}, {"$set": {"verified_email": True}})
            user["verified_email"] = True
    else:
        name = payload.get("name") or email.split("@")[0]
        user = {
            "id": new_id(), "name": name, "email": email, "password_hash": None,
            "initials": "".join(w[0] for w in name.strip().split()[:2]).upper() or "?",
            "bio": "", "rating": 5.0, "rating_count": 0, "jobs_done": 0,
            "city_id": body.city_id, "neighborhood_id": None, "preference": "both",
            "verified_email": True, "verified_phone": False, "verified_identity": False,
            "is_admin": False, "blocked": False, "member_since": now(), "is_demo": False,
            "created_at": now(),
        }
        await db.users.insert_one(dict(user))
    return {"token": create_token(user["id"], user.get("token_version", 0)), "user": public_me(user)}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordIn, request: Request):
    rate_limit(f"forgot:{request.client.host if request.client else 'unknown'}:{body.email.lower()}")
    user = await db.users.find_one({"email": body.email.lower()})
    result = {"message": "Se esse e-mail tiver uma conta, enviamos um código de recuperação."}
    if not user:
        # Same response whether or not the account exists — don't leak which emails are registered.
        return result
    code = generate_otp()
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "password_reset_code_hash": hash_password(code), "password_reset_expires": time_now_plus(OTP_TTL_SECONDS),
    }})
    if not EMAIL_DELIVERY_ENABLED:
        result["dev_code"] = code
        result["dev_note"] = "Nenhum provedor de e-mail configurado — código exibido aqui apenas em desenvolvimento."
    return result


@router.post("/reset-password")
async def reset_password(body: ResetPasswordIn, request: Request):
    rate_limit(f"reset:{request.client.host if request.client else 'unknown'}:{body.email.lower()}")
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("password_reset_code_hash") or not user.get("password_reset_expires"):
        raise HTTPException(400, "Código inválido ou expirado.")
    if time_now() > user["password_reset_expires"]:
        raise HTTPException(400, "Esse código expirou. Solicite um novo.")
    if not verify_password(body.code, user["password_reset_code_hash"]):
        raise HTTPException(400, "Código incorreto.")
    # Bump token_version so any session an attacker held before this reset — the exact
    # scenario forgot-password recovery exists to defend against — stops working immediately.
    await db.users.update_one({"id": user["id"]}, {
        "$set": {"password_hash": hash_password(body.password)},
        "$unset": {"password_reset_code_hash": "", "password_reset_expires": ""},
        "$inc": {"token_version": 1},
    })
    await log_security_event(user["id"], "password_reset", ip=request.client.host if request.client else None)
    return {"message": "Senha alterada com sucesso."}


@router.post("/send-verification")
async def send_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("verified_email"):
        return {"message": "Seu e-mail já está verificado."}
    rate_limit(f"verify-send:{user['id']}")
    code = generate_otp()
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "email_verification_code_hash": hash_password(code), "email_verification_expires": time_now_plus(OTP_TTL_SECONDS),
    }})
    result = {"message": "Enviamos um código de verificação para o seu e-mail."}
    if not EMAIL_DELIVERY_ENABLED:
        result["dev_code"] = code
        result["dev_note"] = "Nenhum provedor de e-mail configurado — código exibido aqui apenas em desenvolvimento."
    return result


@router.post("/verify-email")
async def verify_email(body: VerifyEmailIn, user: dict = Depends(get_current_user)):
    if user.get("verified_email"):
        return public_me(user)
    if not user.get("email_verification_code_hash") or not user.get("email_verification_expires"):
        raise HTTPException(400, "Solicite um novo código antes de verificar.")
    if time_now() > user["email_verification_expires"]:
        raise HTTPException(400, "Esse código expirou. Solicite um novo.")
    if not verify_password(body.code, user["email_verification_code_hash"]):
        raise HTTPException(400, "Código incorreto.")
    await db.users.update_one({"id": user["id"]}, {
        "$set": {"verified_email": True},
        "$unset": {"email_verification_code_hash": "", "email_verification_expires": ""},
    })
    user["verified_email"] = True
    return public_me(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, request: Request, user: dict = Depends(get_current_user)):
    rate_limit(f"change-password:{user['id']}")
    if not verify_password(body.current_password, user.get("password_hash") or ""):
        raise HTTPException(401, "Senha atual incorreta.")
    # Bump token_version too: a password change is exactly the moment a user wants every
    # OTHER session (including a possibly-compromised one) to stop working right away.
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}, "$inc": {"token_version": 1}})
    await log_security_event(user["id"], "password_change", ip=request.client.host if request.client else None)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": user["id"], "title": "Senha alterada",
        "body": "Sua senha foi alterada. Se não foi você, entre em contato com o suporte.",
        "type": "security", "order_id": None, "read": False, "created_at": now(),
    })
    return {"message": "Senha alterada com sucesso."}


@router.delete("/me")
async def delete_account(user: dict = Depends(get_current_user)):
    # Soft delete: anonymize and block login, but keep the row so existing orders,
    # messages, and reviews that reference this id don't end up pointing at nothing.
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "name": "Conta excluída", "email": f"deleted-{user['id']}@faze.local", "password_hash": None,
        "bio": "", "avatar_b64": None, "blocked": True, "deleted_at": now(),
    }})
    return {"message": "Conta excluída."}


@router.patch("/preference")
async def set_preference(body: PreferenceIn, user: dict = Depends(get_current_user)):
    if body.preference not in ("client", "worker", "both"):
        raise HTTPException(400, "Preferência inválida.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"preference": body.preference}})
    user["preference"] = body.preference
    return public_me(user)


@router.get("/notification-prefs")
async def get_notification_prefs(user: dict = Depends(get_current_user)):
    return {"prefs": user.get("notification_prefs") or {}}


@router.patch("/notification-prefs")
async def set_notification_prefs(body: NotificationPrefsIn, user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"notification_prefs": body.prefs}})
    return {"prefs": body.prefs}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return public_me(user)
