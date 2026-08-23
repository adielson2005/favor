"""Regression coverage for the concrete findings from this phase's security audit
(see the plan's "Auditoria de segurança" section). Each test maps to exactly one
numbered fix so a future regression here points straight at what broke.
"""
import os
import uuid

import pyotp
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values('/app/frontend/.env').get('EXPO_PUBLIC_BACKEND_URL')
            or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"

TAG = f"SECFIX_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "TestPass123!"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(api, tag):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    phone = "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": phone, "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    token, user_id = body["token"], body["user"]["id"]
    # Financial/proposal actions require an ACTIVE (both email+phone verified) account —
    # activate right away using the dev-mode codes the register response carries.
    hdrs = auth(token)
    api.post(f"{API}/auth/verify-email", headers=hdrs, json={"code": body["dev_code_email"]}, timeout=15)
    api.post(f"{API}/auth/verify-phone", headers=hdrs, json={"code": body["dev_code_phone"]}, timeout=15)
    return token, user_id, email, phone


def _create_order(api, client_token):
    r = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} pedido", "description": "teste", "type": "favor",
        "category_id": "cat-entregas", "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
        "date_label": "Hoje", "time_label": "", "budget": 40, "photos": [], "fields": {},
        "urgent": False, "recurrence": "none",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------- fix 1: IDOR on GET /orders/{id}/proposals ----------

def test_anonymous_cannot_list_proposals(api):
    client_token, _cid, _e, _p = _register(api, f"{TAG}_p_client")
    order_id = _create_order(api, client_token)
    r = requests.get(f"{API}/orders/{order_id}/proposals", timeout=15)
    assert r.status_code == 401, r.text


def test_worker_only_sees_own_proposal_not_everyone_elses(api):
    client_token, _cid, _e, _p = _register(api, f"{TAG}_p_client2")
    worker_a_token, worker_a_id, _e, _p = _register(api, f"{TAG}_p_workera")
    worker_b_token, worker_b_id, _e, _p = _register(api, f"{TAG}_p_workerb")
    order_id = _create_order(api, client_token)

    prop_a = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_a_token),
                       json={"amount": 30, "message": "eu faço", "eta": "hoje"}, timeout=15)
    assert prop_a.status_code == 200, prop_a.text
    prop_b = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_b_token),
                       json={"amount": 35, "message": "eu também", "eta": "amanhã"}, timeout=15)
    assert prop_b.status_code == 200, prop_b.text

    # Worker A must see ONLY their own proposal — never worker B's bid/message.
    as_worker_a = api.get(f"{API}/orders/{order_id}/proposals", headers=auth(worker_a_token), timeout=15).json()
    assert len(as_worker_a) == 1
    assert as_worker_a[0]["worker_id"] == worker_a_id

    # The order's own client still sees every bid.
    as_client = api.get(f"{API}/orders/{order_id}/proposals", headers=auth(client_token), timeout=15).json()
    worker_ids = {p["worker_id"] for p in as_client}
    assert worker_ids == {worker_a_id, worker_b_id}


# ---------- fix 2: 2FA disable needs a valid code + is rate-limited ----------

def test_2fa_disable_rate_limited_after_repeated_wrong_codes(api, admin_token):
    email = f"{TAG}_2fa_{uuid.uuid4().hex[:8]}@example.com"
    create = api.post(f"{API}/admin/team", headers=auth(admin_token),
                       json={"name": "2FA RateLimit", "email": email, "password": "MemberPass123!", "role": "SUPPORT"}, timeout=15)
    assert create.status_code == 200, create.text
    login = api.post(f"{API}/admin/auth/login", json={"email": email, "password": "MemberPass123!"}, timeout=15)
    token = login.json()["token"]

    setup = api.post(f"{API}/admin/auth/2fa/setup", headers=auth(token), timeout=15)
    secret = setup.json()["secret"]
    verify = api.post(f"{API}/admin/auth/2fa/verify", headers=auth(token), json={"code": pyotp.TOTP(secret).now()}, timeout=15)
    assert verify.status_code == 200, verify.text

    codes = []
    for _ in range(7):
        r = api.post(f"{API}/admin/auth/2fa/disable", headers=auth(token), json={"code": "000000"}, timeout=15)
        codes.append(r.status_code)
    assert 429 in codes, f"expected a 429 after repeated wrong disable codes, got {codes}"


# ---------- fix 3: change-email/change-phone revoke the old session ----------

def test_change_phone_revokes_old_token_and_issues_a_fresh_one(api):
    token, _uid, email, _phone = _register(api, f"{TAG}_chgphone")
    new_phone = "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"
    r = api.post(f"{API}/auth/change-phone", headers=auth(token), json={"phone": new_phone, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    assert "token" in r.json() and r.json()["token"] != token

    stale = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert stale.status_code == 401, stale.text

    fresh = api.get(f"{API}/auth/me", headers=auth(r.json()["token"]), timeout=15)
    assert fresh.status_code == 200, fresh.text


def test_change_email_revokes_old_token_and_issues_a_fresh_one(api):
    token, _uid, _email, _phone = _register(api, f"{TAG}_chgemail")
    new_email = f"{TAG}_new_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/change-email", headers=auth(token), json={"email": new_email, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    assert "token" in r.json() and r.json()["token"] != token

    stale = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert stale.status_code == 401, stale.text

    fresh = api.get(f"{API}/auth/me", headers=auth(r.json()["token"]), timeout=15)
    assert fresh.status_code == 200, fresh.text


# ---------- fix 5: max_withdrawal_per_day is actually enforced ----------

def test_withdrawal_over_configured_daily_cap_is_rejected(api, admin_token):
    token, uid, _email, _phone = _register(api, f"{TAG}_wd")
    credit = api.post(f"{API}/admin/wallets/{uid}/adjust", headers=auth(admin_token),
                       json={"user_id": uid, "amount": 500, "reason": f"{TAG} setup"}, timeout=15)
    assert credit.status_code == 200, credit.text
    bank = api.post(f"{API}/bank-accounts", headers=auth(token), json={
        "holder_name": "Test User", "document": "12345678901", "bank_code": "001",
        "agency": "0001", "account_number": "123456", "account_type": "checking", "password": TEST_PASSWORD,
    }, timeout=15)
    assert bank.status_code == 200, bank.text
    bank_account_id = bank.json()["id"]

    original_config = api.get(f"{API}/admin/config", headers=auth(admin_token), timeout=15).json()
    try:
        low_cap = api.patch(f"{API}/admin/config", headers=auth(admin_token), json={"max_withdrawal_per_day": 50}, timeout=15)
        assert low_cap.status_code == 200, low_cap.text

        over_cap = api.post(f"{API}/wallet/withdrawals", headers=auth(token),
                             json={"amount": 100, "bank_account_id": bank_account_id, "password": TEST_PASSWORD}, timeout=15)
        assert over_cap.status_code == 400, over_cap.text
        assert "limite" in over_cap.text.lower()

        under_cap = api.post(f"{API}/wallet/withdrawals", headers=auth(token),
                              json={"amount": 30, "bank_account_id": bank_account_id, "password": TEST_PASSWORD}, timeout=15)
        assert under_cap.status_code == 200, under_cap.text
    finally:
        api.patch(f"{API}/admin/config", headers=auth(admin_token), json={
            "max_withdrawal_per_day": original_config["max_withdrawal_per_day"],
        }, timeout=15)
