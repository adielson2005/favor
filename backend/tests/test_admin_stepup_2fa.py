"""Tests for step-up 2FA on high-value admin financial actions (admin_auth.py's
require_step_up_totp, wired into routes/admin.py's admin_adjust_wallet and
admin_approve_withdrawal). Uses a fresh throwaway OWNER-role admin per test that
needs 2FA — never touches the shared demo admin_token account's 2FA state, since
many other test files credit wallets through it as a setup step and must keep
working exactly as before.
"""
import os
import uuid

import pyotp
import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
MEMBER_PASSWORD = "MemberPass123!"
TAG = f"STEPUP_{uuid.uuid4().hex[:6]}"
THRESHOLD = 1000.0  # matches wallet.py's DEFAULT_FINANCIAL_CONFIG


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _random_phone():
    return "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"


def _register(api, tag):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    token, user_id = body["token"], body["user"]["id"]
    hdrs = auth(token)
    api.post(f"{API}/auth/verify-email", headers=hdrs, json={"code": body["dev_code_email"]}, timeout=15)
    api.post(f"{API}/auth/verify-phone", headers=hdrs, json={"code": body["dev_code_phone"]}, timeout=15)
    return token, user_id


def _create_owner_admin(api, root_admin_token, tag_suffix=""):
    email = f"{TAG}{tag_suffix}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/admin/team", headers=auth(root_admin_token),
                 json={"name": "Teste Owner Stepup", "email": email, "password": MEMBER_PASSWORD, "role": "OWNER"}, timeout=15)
    assert r.status_code == 200, r.text
    login = api.post(f"{API}/admin/auth/login", json={"email": email, "password": MEMBER_PASSWORD}, timeout=15)
    assert login.status_code == 200, login.text
    return login.json()["token"]


def _enable_2fa(api, admin_token) -> str:
    setup = api.post(f"{API}/admin/auth/2fa/setup", headers=auth(admin_token), timeout=15)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    verify = api.post(f"{API}/admin/auth/2fa/verify", headers=auth(admin_token), json={"code": code}, timeout=15)
    assert verify.status_code == 200, verify.text
    return secret


def _add_bank_account(api, token, suffix):
    r = api.post(f"{API}/bank-accounts", headers=auth(token), json={
        "holder_name": f"Test {suffix}", "document": "12345678900", "bank_code": "001",
        "agency": "0001", "account_number": f"{suffix}0000", "account_type": "checking", "password": TEST_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _get_wallet(api, token):
    r = api.get(f"{API}/wallet", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_wallet_adjust_below_threshold_needs_no_2fa(api, admin_token):
    _, user_id = _register(api, "stepup_below")
    r = api.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(admin_token),
                 json={"user_id": user_id, "amount": 50, "reason": TAG}, timeout=15)
    assert r.status_code == 200, r.text


def test_wallet_adjust_above_threshold_blocked_without_2fa(api, admin_token):
    owner = _create_owner_admin(api, admin_token, "_nototp")
    _, user_id = _register(api, "stepup_no2fa")
    r = requests.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(owner),
                       json={"user_id": user_id, "amount": THRESHOLD, "reason": TAG}, timeout=15)
    assert r.status_code == 403, r.text


def test_wallet_adjust_above_threshold_wrong_code_rejected(api, admin_token):
    owner = _create_owner_admin(api, admin_token, "_wrongcode")
    _enable_2fa(api, owner)
    _, user_id = _register(api, "stepup_wrongcode")
    r = requests.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(owner),
                       json={"user_id": user_id, "amount": THRESHOLD, "reason": TAG, "totp_code": "000000"}, timeout=15)
    assert r.status_code == 401, r.text


def test_wallet_adjust_above_threshold_correct_code_succeeds(api, admin_token):
    owner = _create_owner_admin(api, admin_token, "_correctcode")
    secret = _enable_2fa(api, owner)
    _, user_id = _register(api, "stepup_correctcode")
    code = pyotp.TOTP(secret).now()
    r = requests.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(owner),
                       json={"user_id": user_id, "amount": THRESHOLD, "reason": TAG, "totp_code": code}, timeout=15)
    assert r.status_code == 200, r.text


def test_withdrawal_approve_below_threshold_still_works_with_no_body(api, admin_token):
    # Mirrors test_security_overhaul.py's existing race-condition test, which posts
    # to this endpoint with NO json body at all — must keep working unchanged.
    worker_token, worker_id = _register(api, "stepup_wd_below")
    r = api.post(f"{API}/admin/wallets/{worker_id}/adjust", headers=auth(admin_token),
                 json={"user_id": worker_id, "amount": 50, "reason": TAG}, timeout=15)
    assert r.status_code == 200, r.text
    bank_id = _add_bank_account(api, worker_token, "wdbelow")
    wd = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token),
                  json={"amount": 25, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert wd.status_code == 200, wd.text
    r2 = requests.post(f"{API}/admin/withdrawals/{wd.json()['id']}/approve", headers=auth(admin_token), timeout=15)
    assert r2.status_code == 200, r2.text


def test_withdrawal_approve_above_threshold_requires_2fa(api, admin_token):
    owner = _create_owner_admin(api, admin_token, "_wd")
    worker_token, worker_id = _register(api, "stepup_wd_above")
    # Two sub-threshold credits rather than one big one — the shared admin_token
    # (demo OWNER) has no 2FA enabled, so a single credit >= THRESHOLD through it
    # would now correctly get blocked by the very feature under test.
    for _ in range(2):
        r = api.post(f"{API}/admin/wallets/{worker_id}/adjust", headers=auth(admin_token),
                     json={"user_id": worker_id, "amount": (THRESHOLD + 200) / 2, "reason": TAG}, timeout=15)
        assert r.status_code == 200, r.text
    bank_id = _add_bank_account(api, worker_token, "wdabove")
    wd = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token),
                  json={"amount": THRESHOLD, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert wd.status_code == 200, wd.text
    wd_id = wd.json()["id"]

    no_2fa = requests.post(f"{API}/admin/withdrawals/{wd_id}/approve", headers=auth(owner), timeout=15)
    assert no_2fa.status_code == 403, no_2fa.text

    secret = _enable_2fa(api, owner)
    wrong = requests.post(f"{API}/admin/withdrawals/{wd_id}/approve", headers=auth(owner),
                           json={"totp_code": "000000"}, timeout=15)
    assert wrong.status_code == 401, wrong.text

    before = _get_wallet(api, worker_token)
    code = pyotp.TOTP(secret).now()
    ok = requests.post(f"{API}/admin/withdrawals/{wd_id}/approve", headers=auth(owner),
                        json={"totp_code": code}, timeout=15)
    assert ok.status_code == 200, ok.text
    after = _get_wallet(api, worker_token)
    assert round(before["processing"] - after["processing"], 2) == THRESHOLD


def test_config_reauth_threshold_is_configurable(api, admin_token):
    # Raises the threshold rather than lowering it: `platform_config` is a single
    # global document shared with every other test file running concurrently under
    # xdist, and those files credit wallets via the shared admin_token as setup for
    # unrelated tests. Raising can only relax enforcement (never wrongly 403 an
    # unrelated test's small credit); lowering could make those flaky.
    original = api.get(f"{API}/admin/config", headers=auth(admin_token), timeout=15)
    assert original.status_code == 200, original.text
    original_threshold = original.json()["admin_reauth_threshold"]
    try:
        patched = api.patch(f"{API}/admin/config", headers=auth(admin_token),
                             json={"admin_reauth_threshold": 999999.0}, timeout=15)
        assert patched.status_code == 200, patched.text
        assert patched.json()["admin_reauth_threshold"] == 999999.0

        owner = _create_owner_admin(api, admin_token, "_highthreshold")
        _, user_id = _register(api, "stepup_highthreshold")
        r = requests.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(owner),
                           json={"user_id": user_id, "amount": THRESHOLD + 500, "reason": TAG}, timeout=15)
        assert r.status_code == 200, r.text  # would need 2FA under the default threshold
    finally:
        api.patch(f"{API}/admin/config", headers=auth(admin_token),
                  json={"admin_reauth_threshold": original_threshold}, timeout=15)
