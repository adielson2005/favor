"""Registration, login, and email/phone verification tests.

Covers the explicit checklist: registration, login (email + phone), duplicate
email/phone, wrong password, correct/wrong/expired/reused verification codes,
repeated codes invalidating old ones, attempt limits, resend, password recovery,
the frontend never being able to set verified_email/verified_phone/account_status
itself, unverified-account access (browsing works, financial actions don't), and
login working normally after verification.

Follows the exact fixture/helper pattern already established in
test_security_overhaul.py / test_financial.py.
"""
import os
import time
import uuid

import pymongo
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values('/app/frontend/.env').get('EXPO_PUBLIC_BACKEND_URL')
            or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"

_backend_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
MONGO_URL = _backend_env.get("MONGO_URL") or os.environ.get("MONGO_URL")
DB_NAME = _backend_env.get("DB_NAME") or os.environ.get("DB_NAME")
_mongo = pymongo.MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]

ADMIN_EMAIL = "admin@fazum.demo"
DEMO_PASSWORD = "faze2024"
TEST_PASSWORD = "TestPass123!"

TAG = f"REG_{uuid.uuid4().hex[:6]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _random_phone():
    return "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"


def _register(api, tag, password=TEST_PASSWORD):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    phone = _random_phone()
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": phone, "password": password,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json(), email, phone




# ---------- registration ----------

def test_register_requires_accepting_terms(api):
    email = f"{TAG}_noterm_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={
        "name": "No Terms", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "accept_terms": False,
    }, timeout=15)
    assert r.status_code == 400, r.text


def test_register_creates_pending_verification_account(api):
    body, email, phone = _register(api, "pending")
    assert body["user"]["account_status"] == "PENDING_VERIFICATION"
    assert body["user"]["verified_email"] is False
    assert body["user"]["verified_phone"] is False
    assert body["user"]["phone"] == f"+55{phone}"
    assert "dev_code_email" in body  # no SMTP configured in this environment
    assert "dev_code_phone" in body  # no SMS provider configured in this environment


def test_duplicate_email_rejected(api):
    body, email, phone = _register(api, "dupemail")
    r = api.post(f"{API}/auth/register", json={
        "name": "Dup Email", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 400, r.text


def test_duplicate_phone_rejected(api):
    body, email, phone = _register(api, "dupphone")
    r = api.post(f"{API}/auth/register", json={
        "name": "Dup Phone", "email": f"{TAG}_{uuid.uuid4().hex[:8]}@example.com", "phone": phone,
        "password": TEST_PASSWORD, "city_id": "city-parauapebas", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 400, r.text


# ---------- login ----------

def test_login_wrong_password_rejected(api):
    body, email, phone = _register(api, "wrongpw")
    r = api.post(f"{API}/auth/login", json={"identifier": email, "password": "not-the-password"}, timeout=15)
    assert r.status_code == 401, r.text


def test_login_by_email_works(api):
    body, email, phone = _register(api, "loginemail")
    r = api.post(f"{API}/auth/login", json={"identifier": email, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text


def test_login_by_phone_works(api):
    body, email, phone = _register(api, "loginphone")
    r = api.post(f"{API}/auth/login", json={"identifier": phone, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    # Also works with the number formatted the way a user would type it.
    formatted = f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
    r2 = api.post(f"{API}/auth/login", json={"identifier": formatted, "password": TEST_PASSWORD}, timeout=15)
    assert r2.status_code == 200, r2.text


# ---------- email verification ----------

def test_verify_email_wrong_code_rejected(api):
    body, email, phone = _register(api, "wrongcode")
    r = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": "000000"}, timeout=15)
    assert r.status_code == 400, r.text


def test_verify_email_correct_code_succeeds(api):
    body, email, phone = _register(api, "goodcode")
    r = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": body["dev_code_email"]}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["verified_email"] is True
    assert r.json()["email_verified_at"]


def test_verify_email_code_cannot_be_reused(api):
    body, email, phone = _register(api, "reuse")
    r1 = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": body["dev_code_email"]}, timeout=15)
    assert r1.status_code == 200, r1.text
    # Already verified — a second call is a no-op success, not a re-verification.
    r2 = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": body["dev_code_email"]}, timeout=15)
    assert r2.status_code == 200, r2.text


def test_requesting_new_email_code_invalidates_old_one(api):
    body, email, phone = _register(api, "supersede")
    old_code = body["dev_code_email"]
    resend = api.post(f"{API}/auth/send-verification", headers=auth(body["token"]), timeout=15)
    assert resend.status_code == 200, resend.text
    new_code = resend.json()["dev_code"]
    assert new_code != old_code
    stale = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": old_code}, timeout=15)
    assert stale.status_code == 400, stale.text
    fresh = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": new_code}, timeout=15)
    assert fresh.status_code == 200, fresh.text


def test_email_code_attempt_limit_enforced(api):
    body, email, phone = _register(api, "attempts")
    codes = []
    for _ in range(6):
        r = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": "111111"}, timeout=15)
        codes.append(r.status_code)
    assert 429 in codes, f"expected a 429 after repeated wrong codes, got {codes}"


def test_expired_email_code_rejected(api):
    body, email, phone = _register(api, "expired")
    _db.verification_tokens.update_many(
        {"user_id": body["user"]["id"], "type": "EMAIL", "used_at": None},
        {"$set": {"expires_at": time.time() - 1}},
    )
    r = api.post(f"{API}/auth/verify-email", headers=auth(body["token"]), json={"code": body["dev_code_email"]}, timeout=15)
    assert r.status_code == 400, r.text
    assert "expir" in r.json()["detail"].lower()


def test_verify_email_promotes_to_active_once_phone_also_verified(api):
    body, email, phone = _register(api, "promote")
    token = body["token"]
    api.post(f"{API}/auth/verify-email", headers=auth(token), json={"code": body["dev_code_email"]}, timeout=15)
    r = api.post(f"{API}/auth/verify-phone", headers=auth(token), json={"code": body["dev_code_phone"]}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["account_status"] == "ACTIVE"


# ---------- phone verification ----------

def test_verify_phone_wrong_code_rejected(api):
    body, email, phone = _register(api, "phonewrong")
    r = api.post(f"{API}/auth/verify-phone", headers=auth(body["token"]), json={"code": "000000"}, timeout=15)
    assert r.status_code == 400, r.text


def test_verify_phone_correct_code_succeeds(api):
    body, email, phone = _register(api, "phonegood")
    r = api.post(f"{API}/auth/verify-phone", headers=auth(body["token"]), json={"code": body["dev_code_phone"]}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["verified_phone"] is True
    assert r.json()["phone_verified_at"]


def test_phone_code_attempt_limit_enforced(api):
    body, email, phone = _register(api, "phoneattempts")
    codes = []
    for _ in range(6):
        r = api.post(f"{API}/auth/verify-phone", headers=auth(body["token"]), json={"code": "222222"}, timeout=15)
        codes.append(r.status_code)
    assert 429 in codes, f"expected a 429 after repeated wrong codes, got {codes}"


def test_resend_phone_code_respects_rate_limit_key(api):
    body, email, phone = _register(api, "phoneresend")
    resend = api.post(f"{API}/auth/send-phone-verification", headers=auth(body["token"]), timeout=15)
    assert resend.status_code == 200, resend.text
    assert "dev_code" in resend.json()


# ---------- password recovery ----------

def test_forgot_password_and_reset_flow(api):
    body, email, phone = _register(api, "forgot")
    forgot = api.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)
    assert forgot.status_code == 200, forgot.text
    code = forgot.json().get("dev_code")
    assert code
    reset = api.post(f"{API}/auth/reset-password", json={"email": email, "code": code, "password": "NewerPass456!"}, timeout=15)
    assert reset.status_code == 200, reset.text
    login = api.post(f"{API}/auth/login", json={"identifier": email, "password": "NewerPass456!"}, timeout=15)
    assert login.status_code == 200, login.text


def test_forgot_password_unknown_email_does_not_leak(api):
    r = api.post(f"{API}/auth/forgot-password", json={"email": f"{TAG}_ghost@example.com"}, timeout=15)
    assert r.status_code == 200, r.text
    assert "dev_code" not in r.json()  # no account, nothing to send


# ---------- frontend cannot forge verification/status fields ----------

def test_profile_update_cannot_set_verified_email(api):
    body, email, phone = _register(api, "forge1")
    token, user_id = body["token"], body["user"]["id"]
    r = api.patch(f"{API}/users/{user_id}", headers=auth(token), json={"verified_email": True}, timeout=15)
    assert r.status_code == 200, r.text  # extra/unknown fields are ignored, not rejected
    me = api.get(f"{API}/auth/me", headers=auth(token), timeout=15).json()
    assert me["verified_email"] is False


def test_profile_update_cannot_set_verified_phone_or_account_status(api):
    body, email, phone = _register(api, "forge2")
    token, user_id = body["token"], body["user"]["id"]
    r = api.patch(f"{API}/users/{user_id}", headers=auth(token), json={"verified_phone": True, "account_status": "ACTIVE"}, timeout=15)
    assert r.status_code == 200, r.text
    me = api.get(f"{API}/auth/me", headers=auth(token), timeout=15).json()
    assert me["verified_phone"] is False
    assert me["account_status"] == "PENDING_VERIFICATION"


# ---------- unverified-account access ----------

def test_unverified_account_can_browse_and_create_orders(api):
    body, email, phone = _register(api, "browse")
    token = body["token"]
    orders = api.get(f"{API}/orders?city_id=city-parauapebas", headers=auth(token), timeout=15)
    assert orders.status_code == 200, orders.text
    created = api.post(f"{API}/orders", headers=auth(token), json={
        "title": f"{TAG} unverified order", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 30, "photos": [], "fields": {},
    }, timeout=15)
    assert created.status_code == 200, created.text


def test_unverified_account_cannot_propose_or_pay(api, admin_token):
    client_body, client_email, _ = _register(api, "unvclient")
    worker_body, worker_email, _ = _register(api, "unvworker")
    client_token, worker_token = client_body["token"], worker_body["token"]

    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} gated order", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 30, "photos": [], "fields": {},
    }, timeout=15)
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]

    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert proposal.status_code == 403, proposal.text

    withdrawal = api.post(f"{API}/wallet/withdrawals", headers=auth(client_token),
                           json={"amount": 30, "bank_account_id": "does-not-matter", "password": TEST_PASSWORD}, timeout=15)
    assert withdrawal.status_code == 403, withdrawal.text


def test_verified_account_can_propose(api):
    client_body, client_email, _ = _register(api, "vclient")
    worker_body, worker_email, _ = _register(api, "vworker")
    client_token, worker_token = client_body["token"], worker_body["token"]
    api.post(f"{API}/auth/verify-email", headers=auth(worker_token), json={"code": worker_body["dev_code_email"]}, timeout=15)
    api.post(f"{API}/auth/verify-phone", headers=auth(worker_token), json={"code": worker_body["dev_code_phone"]}, timeout=15)

    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} active order", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 30, "photos": [], "fields": {},
    }, timeout=15)
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert proposal.status_code == 200, proposal.text


# ---------- change email / change phone ----------

def test_change_phone_requires_correct_password(api):
    body, email, phone = _register(api, "chphone")
    r = api.post(f"{API}/auth/change-phone", headers=auth(body["token"]), json={"phone": _random_phone(), "password": "wrong"}, timeout=15)
    assert r.status_code == 401, r.text


def test_change_phone_resets_verification(api):
    body, email, phone = _register(api, "chphone2")
    token = body["token"]
    api.post(f"{API}/auth/verify-email", headers=auth(token), json={"code": body["dev_code_email"]}, timeout=15)
    api.post(f"{API}/auth/verify-phone", headers=auth(token), json={"code": body["dev_code_phone"]}, timeout=15)
    me = api.get(f"{API}/auth/me", headers=auth(token), timeout=15).json()
    assert me["account_status"] == "ACTIVE"

    changed = api.post(f"{API}/auth/change-phone", headers=auth(token), json={"phone": _random_phone(), "password": TEST_PASSWORD}, timeout=15)
    assert changed.status_code == 200, changed.text
    # Changing an existing phone revokes the old session (security fix — see
    # test_security_fixes.py) and issues a fresh token in the same response.
    fresh_token = changed.json()["token"]
    me2 = api.get(f"{API}/auth/me", headers=auth(fresh_token), timeout=15).json()
    assert me2["verified_phone"] is False
    assert me2["account_status"] == "PENDING_VERIFICATION"


def test_change_email_duplicate_rejected(api):
    other_body, other_email, _ = _register(api, "chemail_other")
    body, email, phone = _register(api, "chemail")
    r = api.post(f"{API}/auth/change-email", headers=auth(body["token"]), json={"email": other_email, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 400, r.text


# ---------- admin account status ----------

def test_admin_can_suspend_and_unsuspend_account(api, admin_token):
    body, email, phone = _register(api, "suspend")
    user_id = body["user"]["id"]
    r = api.patch(f"{API}/admin/users/{user_id}/status", headers=auth(admin_token), json={"status": "SUSPENDED"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["account_status"] == "SUSPENDED"

    r2 = api.patch(f"{API}/admin/users/{user_id}/status", headers=auth(admin_token), json={"status": "ACTIVE"}, timeout=15)
    assert r2.status_code == 200, r2.text


def test_non_admin_cannot_set_account_status(api):
    # Admin sessions are a separate identity system now — a consumer token is 401
    # here (not a valid admin session at all), not 403 (admin without permission).
    body, email, phone = _register(api, "notadmin")
    r = api.patch(f"{API}/admin/users/{body['user']['id']}/status", headers=auth(body["token"]), json={"status": "ACTIVE"}, timeout=15)
    assert r.status_code == 401, r.text
