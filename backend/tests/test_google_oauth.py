"""Google OAuth 2.0/OIDC tests.

Real Google sign-in obviously can't be automated here (no live browser round-trip
through accounts.google.com), so these tests rely on GOOGLE_AUTH_TEST_MODE — a
dev/CI-only backend flag (must be "true" in this environment's backend/.env) that
accepts a token literally prefixed "TESTMODE:{json}" instead of asking Google to
verify it. Everything AFTER that one substitution — account lookup by sub, auto-link
by verified e-mail, duplicate-account prevention, last-method-unlink protection,
nonce/expiry checks, security events — is exercised for real over HTTP, exactly like
every other test in this suite.

Covers the explicit checklist: new user, existing user (by sub and by e-mail),
already-registered e-mail, Google already linked (idempotent), expired token,
malformed token, invalid nonce, no-phone new account, link, unlink, unlink-last-method
rejection, linking the same Google account to two different users (rejected),
blocked account, and frontend-supplied fields being ignored (only the verified
payload is ever trusted).
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

_backend_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
TEST_MODE_ENABLED = (_backend_env.get("GOOGLE_AUTH_TEST_MODE") or os.environ.get("GOOGLE_AUTH_TEST_MODE", "")).lower() in ("1", "true", "yes")

TAG = f"GOOG_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "TestPass123!"

pytestmark = pytest.mark.skipif(not TEST_MODE_ENABLED, reason="GOOGLE_AUTH_TEST_MODE not enabled in this environment")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def google_token(**overrides):
    import json
    payload = {
        "sub": f"sub-{uuid.uuid4().hex[:12]}",
        "email": f"{TAG}_{uuid.uuid4().hex[:8]}@example.com",
        "email_verified": True,
        "name": "Google Test User",
    }
    payload.update(overrides)
    return f"TESTMODE:{json.dumps(payload)}", payload


def google_login(api, id_token, nonce=None, city_id=None, extra=None):
    body = {"id_token": id_token}
    if nonce is not None:
        body["nonce"] = nonce
    if city_id is not None:
        body["city_id"] = city_id
    if extra:
        body.update(extra)
    return api.post(f"{API}/auth/google", json=body, timeout=15)


def _register(api, tag):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    phone = "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": phone, "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json(), email


# ---------- 1. new user via Google ----------

def test_new_user_via_google_creates_active_email_pending_phone_account(api):
    token, payload = google_token()
    r = google_login(api, token)
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["verified_email"] is True
    assert user["verified_phone"] is False
    assert user["phone"] is None
    assert user["account_status"] == "PENDING_VERIFICATION"  # phone still missing
    assert user["has_password"] is False


# ---------- 2. existing user via Google (by sub) ----------

def test_existing_google_user_logs_in_via_same_sub_no_duplicate(api):
    token, payload = google_token()
    r1 = google_login(api, token)
    assert r1.status_code == 200, r1.text
    user_id_1 = r1.json()["user"]["id"]

    # Same sub, fresh token (as a real re-login would produce) — must resolve to the
    # exact same account, not create a second one.
    token2, _ = google_token(sub=payload["sub"], email=payload["email"])
    r2 = google_login(api, token2)
    assert r2.status_code == 200, r2.text
    assert r2.json()["user"]["id"] == user_id_1


# ---------- 3. Google with an already-registered e-mail (auto-link) ----------

def test_google_with_existing_password_account_email_links_instead_of_duplicating(api):
    body, email = _register(api, "link")
    password_user_id = body["user"]["id"]

    token, _ = google_token(email=email)
    r = google_login(api, token)
    assert r.status_code == 200, r.text
    linked = r.json()["user"]
    assert linked["id"] == password_user_id
    assert linked["has_password"] is True
    assert linked["verified_email"] is True  # Google's verified e-mail promotes it


# ---------- 4. Google already linked — logging in again is idempotent ----------

def test_google_login_again_is_idempotent(api):
    token, payload = google_token()
    r1 = google_login(api, token)
    user_id = r1.json()["user"]["id"]
    token2, _ = google_token(sub=payload["sub"], email=payload["email"])
    r2 = google_login(api, token2)
    r3 = google_login(api, token2)
    assert r2.json()["user"]["id"] == user_id
    assert r3.json()["user"]["id"] == user_id


# ---------- 5. expired token ----------

def test_expired_google_token_rejected(api):
    import time
    token, _ = google_token(exp=time.time() - 60)
    r = google_login(api, token)
    assert r.status_code == 401, r.text


# ---------- 6. malformed/invalid token ----------

def test_malformed_google_token_rejected(api):
    r = google_login(api, "TESTMODE:not-valid-json")
    assert r.status_code == 401, r.text


def test_google_token_missing_sub_rejected(api):
    import json
    bad = f"TESTMODE:{json.dumps({'email': 'no-sub@example.com', 'email_verified': True})}"
    r = google_login(api, bad)
    assert r.status_code == 401, r.text


def test_google_unverified_email_rejected(api):
    token, _ = google_token(email_verified=False)
    r = google_login(api, token)
    assert r.status_code == 401, r.text


# ---------- 8. invalid nonce ----------

def test_invalid_nonce_rejected(api):
    token, _ = google_token(nonce="expected-nonce-abc")
    r = google_login(api, token, nonce="different-nonce-xyz")
    assert r.status_code == 401, r.text


def test_matching_nonce_accepted(api):
    token, _ = google_token(nonce="matching-nonce-123")
    r = google_login(api, token, nonce="matching-nonce-123")
    assert r.status_code == 200, r.text


# ---------- 10. new Google account has no phone ----------

def test_new_google_account_requires_phone_before_active(api):
    token, _ = google_token()
    r = google_login(api, token)
    user = r.json()["user"]
    assert user["phone"] is None
    assert user["account_status"] == "PENDING_VERIFICATION"
    # And financial actions are blocked for it, same as any other unverified account.
    withdrawal = api.post(f"{API}/wallet/withdrawals", headers=auth(r.json()["token"]),
                           json={"amount": 30, "bank_account_id": "x", "password": "whatever"}, timeout=15)
    assert withdrawal.status_code == 403, withdrawal.text


# ---------- 13/14. link and unlink ----------

def test_link_google_to_logged_in_account(api):
    body, email = _register(api, "manuallink")
    token = body["token"]
    google_id_token, _ = google_token(email=f"{TAG}_unrelated@example.com")
    r = api.post(f"{API}/auth/google/link", headers=auth(token), json={"id_token": google_id_token}, timeout=15)
    assert r.status_code == 200, r.text

    accounts = api.get(f"{API}/auth/linked-accounts", headers=auth(token), timeout=15).json()
    providers = {a["provider"] for a in accounts["accounts"]}
    assert "GOOGLE" in providers
    assert "PASSWORD" in providers


def test_unlink_google_when_password_exists_succeeds(api):
    body, email = _register(api, "unlink")
    token = body["token"]
    google_id_token, _ = google_token()
    api.post(f"{API}/auth/google/link", headers=auth(token), json={"id_token": google_id_token}, timeout=15)

    r = api.delete(f"{API}/auth/google/unlink", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    accounts = api.get(f"{API}/auth/linked-accounts", headers=auth(token), timeout=15).json()
    assert all(a["provider"] != "GOOGLE" for a in accounts["accounts"])


def test_cannot_unlink_last_auth_method(api):
    token, _ = google_token()
    r = google_login(api, token)
    user_token = r.json()["token"]
    assert r.json()["user"]["has_password"] is False

    unlink = api.delete(f"{API}/auth/google/unlink", headers=auth(user_token), timeout=15)
    assert unlink.status_code == 400, unlink.text

    # Creating a password (no current_password needed — there wasn't one) unblocks it.
    created = api.post(f"{API}/auth/change-password", headers=auth(user_token),
                        json={"new_password": "BrandNewPass456!"}, timeout=15)
    assert created.status_code == 200, created.text
    # Password creation bumps token_version — need a fresh token to keep going.
    relogin = google_login(api, token)
    fresh_token = relogin.json()["token"]
    unlink2 = api.delete(f"{API}/auth/google/unlink", headers=auth(fresh_token), timeout=15)
    assert unlink2.status_code == 200, unlink2.text


# ---------- 15. same Google account cannot link to two different users ----------

def test_same_google_account_cannot_link_to_two_users(api):
    body_a, email_a = _register(api, "usera")
    body_b, email_b = _register(api, "userb")
    google_id_token, payload = google_token()

    link_a = api.post(f"{API}/auth/google/link", headers=auth(body_a["token"]), json={"id_token": google_id_token}, timeout=15)
    assert link_a.status_code == 200, link_a.text

    # Same sub, still unused by user B — must be rejected, not silently re-linked.
    token_same_sub, _ = google_token(sub=payload["sub"], email=email_b)
    link_b = api.post(f"{API}/auth/google/link", headers=auth(body_b["token"]), json={"id_token": token_same_sub}, timeout=15)
    assert link_b.status_code == 409, link_b.text


# ---------- 16. blocked account ----------

def test_blocked_account_cannot_login_via_google(api, admin_token):
    token, payload = google_token()
    r = google_login(api, token)
    user_id = r.json()["user"]["id"]

    blocked = api.post(f"{API}/admin/users/{user_id}/block", headers=auth(admin_token), timeout=15)
    assert blocked.status_code == 200, blocked.text

    token2, _ = google_token(sub=payload["sub"], email=payload["email"])
    r2 = google_login(api, token2)
    assert r2.status_code == 403, r2.text

    # Clean up so this shared-flavored test doesn't leave a permanently blocked account.
    api.post(f"{API}/admin/users/{user_id}/block", headers=auth(admin_token), timeout=15)


# ---------- 17. frontend-supplied fields are ignored ----------

def test_extra_body_fields_are_ignored_only_verified_payload_matters(api):
    token, payload = google_token()
    r = google_login(api, token, extra={
        "email": "attacker-controlled@evil.com",
        "sub": "attacker-controlled-sub",
        "verified_email": False,
        "account_status": "ACTIVE",
    })
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    # The account was created/matched using the id_token's OWN payload — never the
    # sibling body fields above (Pydantic just ignores fields GoogleAuthIn doesn't
    # declare), so the resulting user must reflect the real (test) Google payload.
    assert user["account_status"] == "PENDING_VERIFICATION"  # not the attacker's "ACTIVE"
    assert user["verified_email"] is True  # not the attacker's False
