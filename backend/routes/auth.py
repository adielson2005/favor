import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

import geo_catalog_repo as geo_repo
from auth import (
    create_token, get_current_user, hash_password, rate_limit, verify_password,
)
from data_export import compile_user_export
from auth_accounts import (
    PROVIDER_GOOGLE, PROVIDER_PASSWORD, find_user_id_by_account, link_account, list_accounts, unlink_account,
)
from database import db, new_id, now
from email_provider import send_email
from models import (
    ChangeEmailIn, ChangePasswordIn, ChangePhoneIn, ForgotPasswordIn, GoogleAuthIn, GoogleLinkIn, LoginIn,
    NotificationPrefsIn, PreferenceIn, RegisterIn, ResetPasswordIn, VerifyEmailIn, VerifyPhoneIn,
)
from phone import normalize_phone_br
from phone_provider import get_phone_provider
from security_events import log_security_event
from verification import (
    TYPE_EMAIL, TYPE_PASSWORD_RESET, TYPE_PHONE, create_verification_token, promote_if_verified, verify_token,
)

router = APIRouter(prefix="/auth")

OTP_TTL_SECONDS = 10 * 60  # 10 minutes


def public_me(user: dict) -> dict:
    from routes.public import private_user

    return private_user(user)


async def _find_by_identifier(identifier: str) -> dict | None:
    """Login accepts either an e-mail or a phone number in the same field. Try e-mail
    first (cheap, exact match on the normalized lowercase string already indexed);
    only attempt phone normalization if that misses, since a malformed "phone" typed
    by someone who actually meant to type an e-mail shouldn't raise a 400 here — it
    should just fail login with the same generic message as any other wrong identifier.
    """
    email = identifier.strip().lower()
    user = await db.users.find_one({"email": email})
    if user:
        return user
    try:
        phone = normalize_phone_br(identifier)
    except HTTPException:
        return None
    return await db.users.find_one({"phone": phone})


def _google_auth_test_mode() -> bool:
    return os.environ.get("GOOGLE_AUTH_TEST_MODE", "").lower() in ("1", "true", "yes")


def _verify_google_id_token(id_token: str, nonce: Optional[str], client_id: str) -> dict:
    """Real signature/issuer/audience/expiration validation via Google's own library
    (google.oauth2.id_token) — this is the ONLY code path that ever gets to say an
    id_token is genuine. GOOGLE_AUTH_TEST_MODE is a dev/CI-only escape hatch (off by
    default, must never be set in production) that lets automated tests exercise the
    real account-linking/creation logic below without contacting Google's servers —
    it only accepts a token literally prefixed "TESTMODE:", never a token that could
    plausibly come from a real Google sign-in.
    """
    if _google_auth_test_mode() and id_token.startswith("TESTMODE:"):
        try:
            payload = json.loads(id_token[len("TESTMODE:"):])
        except (ValueError, TypeError):
            raise HTTPException(401, "Não foi possível verificar sua conta Google.")
        # Mirrors the real library's expiry check so tests can exercise it — the real
        # verify_oauth2_token call below already enforces this on genuine tokens.
        if "exp" in payload and payload["exp"] < time.time():
            raise HTTPException(401, "Sua sessão de login com o Google expirou. Tente novamente.")
    else:
        try:
            payload = google_id_token.verify_oauth2_token(id_token, google_requests.Request(), client_id)
        except ValueError:
            raise HTTPException(401, "Não foi possível verificar sua conta Google.")
    # Only enforced when the caller actually sent a nonce — an older client that
    # doesn't send one yet shouldn't be locked out, but once a nonce is present it
    # must match what the token was actually issued for (replay protection).
    if nonce is not None and payload.get("nonce") != nonce:
        raise HTTPException(401, "Não foi possível confirmar essa tentativa de login. Tente novamente.")
    if not payload.get("sub"):
        raise HTTPException(401, "Não foi possível verificar sua conta Google.")
    return payload


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    rate_limit(f"register:{request.client.host if request.client else 'unknown'}", max_attempts=150, window_seconds=300)
    if not body.accept_terms:
        raise HTTPException(400, "É preciso aceitar os Termos de Uso e a Política de Privacidade.")
    email = body.email.lower()
    phone = normalize_phone_br(body.phone)
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Já existe uma conta com este e-mail.")
    if await db.users.find_one({"phone": phone}):
        raise HTTPException(400, "Já existe uma conta com este telefone.")
    if geo_repo.GEO_CATALOG_BACKEND == "postgres":
        city = await run_in_threadpool(geo_repo.get_city, body.city_id)
    else:
        city = await db.cities.find_one({"id": body.city_id}, {"_id": 0, "state_id": 1})
    user = {
        "id": new_id(), "name": body.name.strip(), "email": email, "phone": phone,
        "password_hash": hash_password(body.password),
        "initials": "".join(w[0] for w in body.name.strip().split()[:2]).upper() or "?",
        "bio": "", "rating": 5.0, "rating_count": 0, "jobs_done": 0,
        "city_id": body.city_id, "neighborhood_id": body.neighborhood_id,
        "state_id": (city or {}).get("state_id"),
        "preference": body.preference if body.preference in ("client", "worker", "both") else "both",
        "verified_email": False, "verified_phone": False, "verified_identity": False,
        "email_verified_at": None, "phone_verified_at": None,
        "account_status": "PENDING_VERIFICATION",
        "is_admin": False, "blocked": False, "member_since": now(), "is_demo": False,
        "created_at": now(),
    }
    await db.users.insert_one(dict(user))
    await link_account(user["id"], PROVIDER_PASSWORD, user["id"])
    await log_security_event(user["id"], "account_created", detail="password", ip=request.client.host if request.client else None)

    result = {"token": create_token(user["id"], 0), "user": public_me(user)}

    email_code = await create_verification_token(user["id"], TYPE_EMAIL, OTP_TTL_SECONDS)
    if not send_email(email, "Confirme seu e-mail — fazum", f"Seu código de verificação é {email_code}. Ele expira em 10 minutos."):
        result["dev_code_email"] = email_code

    phone_code = await create_verification_token(user["id"], TYPE_PHONE, OTP_TTL_SECONDS)
    if not await get_phone_provider().send_otp(phone, phone_code):
        result["dev_code_phone"] = phone_code

    return result


@router.post("/login")
async def login(body: LoginIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    identifier = body.identifier.strip().lower()
    rate_limit(f"login:{ip}:{identifier}")
    # A per-(ip, identifier) bucket alone doesn't resist an attacker rotating IPs
    # against the SAME target account — each new IP gets a fresh bucket. This second,
    # identifier-only bucket (no IP component) catches that; it's more generous since
    # legitimate users behind a shared/corporate IP shouldn't be extra-penalized just
    # because the IP dimension is missing from this specific check.
    rate_limit(f"login-identifier:{identifier}", max_attempts=20, window_seconds=300)
    user = await _find_by_identifier(body.identifier)
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail/telefone ou senha incorretos.")
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
    ip = request.client.host if request.client else None
    rate_limit(f"google:{ip if ip else 'unknown'}", max_attempts=60, window_seconds=300)
    payload = _verify_google_id_token(body.id_token, body.nonce, client_id)
    if not payload.get("email_verified"):
        raise HTTPException(401, "Seu e-mail do Google precisa estar verificado.")
    sub = payload["sub"]
    email = payload["email"].lower()

    # Strongest identity check first: this exact Google account has signed in here
    # before, so its `sub` is already linked to a specific FAZUM user — no email
    # matching involved at all for returning users.
    linked_user_id = await find_user_id_by_account(PROVIDER_GOOGLE, sub)
    if linked_user_id:
        user = await db.users.find_one({"id": linked_user_id})
        if not user:
            raise HTTPException(401, "Sessão inválida. Entre novamente.")
        if user.get("blocked"):
            raise HTTPException(403, "Sua conta está bloqueada. Fale com o suporte.")
        await log_security_event(user["id"], "login_google", ip=ip)
        return {"token": create_token(user["id"], user.get("token_version", 0)), "user": public_me(user)}

    # No account has this Google identity linked yet. If a FAZUM account already
    # exists with this (Google-verified, not frontend-supplied) e-mail, link to it
    # instead of creating a duplicate — this is safe specifically because Google
    # already proved ownership of the address (email_verified check above).
    user = await db.users.find_one({"email": email})
    if user:
        if user.get("blocked"):
            raise HTTPException(403, "Sua conta está bloqueada. Fale com o suporte.")
        await link_account(user["id"], PROVIDER_GOOGLE, sub)
        if not user.get("verified_email"):
            verified_at = now()
            await db.users.update_one({"id": user["id"]}, {"$set": {"verified_email": True, "email_verified_at": verified_at}})
            user["verified_email"] = True
            user["email_verified_at"] = verified_at
            await promote_if_verified(user["id"])
        await log_security_event(user["id"], "google_linked", detail="auto (matched verified e-mail)", ip=ip)
        from routes.public import notify
        await notify(user["id"], "Google vinculado", "Sua conta agora também pode entrar com sua conta Google.", "security")
        await log_security_event(user["id"], "login_google", ip=ip)
        # account_status may have just been promoted to ACTIVE — re-fetch so the
        # response reflects it instead of the pre-promotion in-memory copy.
        return {"token": create_token(user["id"], user.get("token_version", 0)), "user": public_me(await db.users.find_one({"id": user["id"]}))}

    # Genuinely new person — create the account with only what's needed (name,
    # e-mail, picture if Google provided one, the Google identifier itself).
    name = payload.get("name") or email.split("@")[0]
    if geo_repo.GEO_CATALOG_BACKEND == "postgres":
        city = await run_in_threadpool(geo_repo.get_city, body.city_id)
    else:
        city = await db.cities.find_one({"id": body.city_id}, {"_id": 0, "state_id": 1})
    user = {
        # No "phone" key at all (not even None) — `phone` has a sparse unique index,
        # and MongoDB's sparse indexes only skip documents where the field is truly
        # ABSENT, not documents where it's present-but-null. Setting it to None here
        # would make the second phoneless account ever created collide on that index.
        "id": new_id(), "name": name, "email": email, "password_hash": None,
        "initials": "".join(w[0] for w in name.strip().split()[:2]).upper() or "?",
        "bio": "", "avatar_b64": payload.get("picture"), "rating": 5.0, "rating_count": 0, "jobs_done": 0,
        "city_id": body.city_id, "neighborhood_id": None, "state_id": (city or {}).get("state_id"),
        "preference": "both",
        "verified_email": True, "verified_phone": False, "verified_identity": False,
        "email_verified_at": now(), "phone_verified_at": None,
        "account_status": "PENDING_VERIFICATION",
        "is_admin": False, "blocked": False, "member_since": now(), "is_demo": False,
        "created_at": now(),
    }
    await db.users.insert_one(dict(user))
    await link_account(user["id"], PROVIDER_GOOGLE, sub)
    await log_security_event(user["id"], "account_created", detail="google", ip=ip)
    await log_security_event(user["id"], "login_google", ip=ip)
    return {"token": create_token(user["id"], 0), "user": public_me(user)}


@router.post("/google/link")
async def google_link(body: GoogleLinkIn, request: Request, user: dict = Depends(get_current_user)):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(501, "Login com Google ainda não foi configurado neste servidor.")
    rate_limit(f"google-link:{user['id']}")
    payload = _verify_google_id_token(body.id_token, body.nonce, client_id)
    if not payload.get("email_verified"):
        raise HTTPException(401, "Seu e-mail do Google precisa estar verificado.")
    sub = payload["sub"]
    existing_user_id = await find_user_id_by_account(PROVIDER_GOOGLE, sub)
    if existing_user_id and existing_user_id != user["id"]:
        raise HTTPException(409, "Essa conta Google já está vinculada a outro usuário.")
    await link_account(user["id"], PROVIDER_GOOGLE, sub)
    # Only touch verification if the linked Google account's e-mail is actually this
    # user's own registered e-mail — linking must never silently verify (or imply
    # ownership of) some other address.
    if payload.get("email", "").lower() == (user.get("email") or "").lower() and not user.get("verified_email"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"verified_email": True, "email_verified_at": now()}})
        await promote_if_verified(user["id"])
    ip = request.client.host if request.client else None
    await log_security_event(user["id"], "google_linked", detail="manual", ip=ip)
    from routes.public import notify
    await notify(user["id"], "Google vinculado", "Sua conta agora também pode entrar com sua conta Google.", "security")
    return {"message": "Conta Google vinculada com sucesso."}


@router.delete("/google/unlink")
async def google_unlink(request: Request, user: dict = Depends(get_current_user)):
    rate_limit(f"google-unlink:{user['id']}")
    await unlink_account(user["id"], PROVIDER_GOOGLE)
    ip = request.client.host if request.client else None
    await log_security_event(user["id"], "google_unlinked", ip=ip)
    from routes.public import notify
    await notify(user["id"], "Google desvinculado", "Sua conta não pode mais entrar com o Google.", "security")
    return {"message": "Google desvinculado."}


@router.get("/linked-accounts")
async def linked_accounts(user: dict = Depends(get_current_user)):
    accounts = await list_accounts(user["id"])
    return {
        "accounts": [{"provider": a["provider"], "created_at": a["created_at"]} for a in accounts],
        "has_password": bool(user.get("password_hash")),
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordIn, request: Request):
    rate_limit(f"forgot:{request.client.host if request.client else 'unknown'}:{body.email.lower()}")
    user = await db.users.find_one({"email": body.email.lower()})
    result = {"message": "Se esse e-mail tiver uma conta, enviamos um código de recuperação."}
    if not user:
        # Same response whether or not the account exists — don't leak which emails are registered.
        return result
    code = await create_verification_token(user["id"], TYPE_PASSWORD_RESET, OTP_TTL_SECONDS)
    if not send_email(user["email"], "Recuperação de senha — fazum", f"Seu código de recuperação é {code}. Ele expira em 10 minutos."):
        result["dev_code"] = code
    return result


@router.post("/reset-password")
async def reset_password(body: ResetPasswordIn, request: Request):
    rate_limit(f"reset:{request.client.host if request.client else 'unknown'}:{body.email.lower()}")
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(400, "Código inválido ou expirado.")
    await verify_token(user["id"], TYPE_PASSWORD_RESET, body.code)
    # Bump token_version so any session an attacker held before this reset — the exact
    # scenario forgot-password recovery exists to defend against — stops working immediately.
    await db.users.update_one({"id": user["id"]}, {
        "$set": {"password_hash": hash_password(body.password)},
        "$inc": {"token_version": 1},
    })
    await log_security_event(user["id"], "password_reset", ip=request.client.host if request.client else None)
    return {"message": "Senha alterada com sucesso."}


@router.post("/send-verification")
async def send_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("verified_email"):
        return {"message": "Seu e-mail já está verificado."}
    rate_limit(f"verify-send:{user['id']}")
    code = await create_verification_token(user["id"], TYPE_EMAIL, OTP_TTL_SECONDS)
    result = {"message": "Enviamos um código de verificação para o seu e-mail."}
    if not send_email(user["email"], "Confirme seu e-mail — fazum", f"Seu código de verificação é {code}. Ele expira em 10 minutos."):
        result["dev_code"] = code
    return result


@router.post("/verify-email")
async def verify_email(body: VerifyEmailIn, request: Request, user: dict = Depends(get_current_user)):
    if user.get("verified_email"):
        return public_me(user)
    await verify_token(user["id"], TYPE_EMAIL, body.code)
    await db.users.update_one({"id": user["id"]}, {"$set": {"verified_email": True, "email_verified_at": now()}})
    user["verified_email"] = True
    await promote_if_verified(user["id"])
    await log_security_event(user["id"], "email_verified", ip=request.client.host if request.client else None)
    return public_me(await db.users.find_one({"id": user["id"]}))


@router.post("/send-phone-verification")
async def send_phone_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("verified_phone"):
        return {"message": "Seu telefone já está verificado."}
    if not user.get("phone"):
        raise HTTPException(400, "Cadastre um telefone antes de verificar.")
    rate_limit(f"phone-verify-send:{user['id']}")
    code = await create_verification_token(user["id"], TYPE_PHONE, OTP_TTL_SECONDS)
    result = {"message": "Enviamos um código de verificação para o seu telefone."}
    if not await get_phone_provider().send_otp(user["phone"], code):
        result["dev_code"] = code
    return result


@router.post("/verify-phone")
async def verify_phone(body: VerifyPhoneIn, request: Request, user: dict = Depends(get_current_user)):
    if user.get("verified_phone"):
        return public_me(user)
    await verify_token(user["id"], TYPE_PHONE, body.code)
    await db.users.update_one({"id": user["id"]}, {"$set": {"verified_phone": True, "phone_verified_at": now()}})
    user["verified_phone"] = True
    await promote_if_verified(user["id"])
    await log_security_event(user["id"], "phone_verified", ip=request.client.host if request.client else None)
    return public_me(await db.users.find_one({"id": user["id"]}))


@router.post("/change-phone")
async def change_phone(body: ChangePhoneIn, request: Request, user: dict = Depends(get_current_user)):
    rate_limit(f"change-phone:{user['id']}")
    # Setting a phone for the first time (e.g. completing a new Google account's
    # profile) has no existing phone to protect, so it doesn't require password reauth.
    # Once an account has a phone, changing it always requires the password.
    is_first_phone = not user.get("phone")
    if not is_first_phone and not verify_password(body.password or "", user.get("password_hash") or ""):
        raise HTTPException(401, "Senha incorreta.")
    phone = normalize_phone_br(body.phone)
    existing = await db.users.find_one({"phone": phone})
    if existing and existing["id"] != user["id"]:
        raise HTTPException(400, "Já existe uma conta com este telefone.")
    # Changing the number always resets its verification — a new number hasn't proven
    # anything yet, and if this account was already ACTIVE it drops back to pending
    # until the new phone is confirmed (never silently keep financial access active
    # on an unverified contact channel).
    was_active = user.get("account_status") == "ACTIVE"
    # First-time phone (nothing to protect yet — see is_first_phone above) skips the
    # token_version bump/notification: there's no "old" contact channel being taken
    # over, so there's nothing for another session to be alerted about.
    new_token_version = user.get("token_version", 0)
    update: dict = {"$set": {
        "phone": phone, "verified_phone": False, "phone_verified_at": None,
        **({"account_status": "PENDING_VERIFICATION"} if was_active else {}),
    }}
    if not is_first_phone:
        new_token_version += 1
        update["$inc"] = {"token_version": 1}
    await db.users.update_one({"id": user["id"]}, update)
    ip = request.client.host if request.client else None
    await log_security_event(user["id"], "phone_changed", ip=ip)
    if not is_first_phone:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": user["id"], "title": "Telefone alterado",
            "body": "O telefone da sua conta foi alterado. Se não foi você, entre em contato com o suporte.",
            "type": "security", "order_id": None, "read": False, "created_at": now(),
        })
    code = await create_verification_token(user["id"], TYPE_PHONE, OTP_TTL_SECONDS)
    # This bumps token_version, invalidating the caller's OWN current token too — issue
    # a fresh one in the same response so the frontend can carry straight on into phone
    # verification instead of being forced to log in again mid-flow.
    result = {"message": "Telefone atualizado. Enviamos um novo código de verificação.",
              "token": create_token(user["id"], new_token_version),
              "user": public_me(await db.users.find_one({"id": user["id"]}))}
    if not await get_phone_provider().send_otp(phone, code):
        result["dev_code"] = code
    return result


@router.post("/change-email")
async def change_email(body: ChangeEmailIn, request: Request, user: dict = Depends(get_current_user)):
    rate_limit(f"change-email:{user['id']}")
    if not verify_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(401, "Senha incorreta.")
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing and existing["id"] != user["id"]:
        raise HTTPException(400, "Já existe uma conta com este e-mail.")
    # Same reasoning as change-phone: a new address hasn't proven anything yet, so
    # verification resets and an already-ACTIVE account drops back to pending.
    was_active = user.get("account_status") == "ACTIVE"
    new_token_version = user.get("token_version", 0) + 1
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "email": email, "verified_email": False, "email_verified_at": None,
        **({"account_status": "PENDING_VERIFICATION"} if was_active else {}),
    }, "$inc": {"token_version": 1}})
    ip = request.client.host if request.client else None
    await log_security_event(user["id"], "email_changed", ip=ip)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": user["id"], "title": "E-mail alterado",
        "body": "O e-mail da sua conta foi alterado. Se não foi você, entre em contato com o suporte.",
        "type": "security", "order_id": None, "read": False, "created_at": now(),
    })
    code = await create_verification_token(user["id"], TYPE_EMAIL, OTP_TTL_SECONDS)
    # Bumps token_version, so issue a fresh token in the response — same reasoning
    # as change-phone above.
    result = {"message": "E-mail atualizado. Enviamos um novo código de verificação.",
              "token": create_token(user["id"], new_token_version),
              "user": public_me(await db.users.find_one({"id": user["id"]}))}
    if not send_email(email, "Confirme seu e-mail — fazum", f"Seu código de verificação é {code}. Ele expira em 10 minutos."):
        result["dev_code"] = code
    return result


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, request: Request, user: dict = Depends(get_current_user)):
    rate_limit(f"change-password:{user['id']}")
    has_password = bool(user.get("password_hash"))
    # A Google-only account has no password yet — nothing to check against, this call
    # is "create my first password" rather than "change it". Any account that already
    # has one must still prove it before replacing it.
    if has_password and not verify_password(body.current_password or "", user["password_hash"]):
        raise HTTPException(401, "Senha atual incorreta.")
    # Bump token_version too: a password change is exactly the moment a user wants every
    # OTHER session (including a possibly-compromised one) to stop working right away.
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}, "$inc": {"token_version": 1}})
    await link_account(user["id"], PROVIDER_PASSWORD, user["id"])
    ip = request.client.host if request.client else None
    await log_security_event(user["id"], "password_change" if has_password else "password_created", ip=ip)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": user["id"],
        "title": "Senha criada" if not has_password else "Senha alterada",
        "body": "Agora você também pode entrar com e-mail/telefone e senha." if not has_password
                else "Sua senha foi alterada. Se não foi você, entre em contato com o suporte.",
        "type": "security", "order_id": None, "read": False, "created_at": now(),
    })
    return {"message": "Senha criada com sucesso." if not has_password else "Senha alterada com sucesso."}


@router.delete("/me")
async def delete_account(user: dict = Depends(get_current_user)):
    # Soft delete: anonymize and block login, but keep the row so existing orders,
    # messages, and reviews that reference this id don't end up pointing at nothing.
    # Freeing the email/phone (rather than leaving them set) lets the person register
    # again later without hitting the uniqueness constraint against their own deleted row.
    # $unset (not $set to None) for phone — same sparse-unique-index reasoning as the
    # Google-signup path above: a present-but-null value still collides with the next
    # phoneless account, an absent field doesn't.
    await db.users.update_one({"id": user["id"]}, {
        "$set": {
            "name": "Conta excluída", "email": f"deleted-{user['id']}@faze.local",
            "password_hash": None, "bio": "", "avatar_b64": None, "blocked": True,
            "account_status": "BLOCKED", "deleted_at": now(),
        },
        "$unset": {"phone": ""},
    })
    return {"message": "Conta excluída."}


@router.get("/me/export")
async def export_my_data(user: dict = Depends(get_current_user)):
    # LGPD Art. 18 (direito de acesso). Not a routine action — 5/hour is generous
    # for "download my data" while ruling out accidental/scripted scraping.
    rate_limit(f"data-export:{user['id']}", max_attempts=5, window_seconds=3600)
    await log_security_event(user["id"], "data_export_requested")
    return await compile_user_export(user["id"])


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
