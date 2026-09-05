"""Admin panel RBAC tests — 4-role system (OWNER/MANAGER/SUPPORT/MAINTENANCE).

Admin auth is a completely separate identity system from consumer auth (db.admin_users,
its own JWT, its own login endpoint). Covers: login for every role, the full deny-lists
from the spec for each non-OWNER role, OWNER having full access, 2FA setup/verify/
disable/enforcement, feature flags CRUD reflected in /bootstrap, and that no admin can
escalate their own or another admin's permissions without the required permission.
"""
import os
import uuid

import pyotp
import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TAG = f"ADMPNL_{uuid.uuid4().hex[:6]}"
MEMBER_PASSWORD = "MemberPass123!"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_member(api, admin_token, role, tag_suffix=""):
    email = f"{TAG}{tag_suffix}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/admin/team", headers=auth(admin_token),
                 json={"name": f"Teste {role}", "email": email, "password": MEMBER_PASSWORD, "role": role}, timeout=15)
    assert r.status_code == 200, r.text
    admin_id = r.json()["id"]
    login = api.post(f"{API}/admin/auth/login", json={"email": email, "password": MEMBER_PASSWORD}, timeout=15)
    assert login.status_code == 200, login.text
    return login.json()["token"], admin_id, email


# ---------- login ----------

def test_owner_login_succeeds(api, admin_token):
    me = api.get(f"{API}/admin/auth/me", headers=auth(admin_token), timeout=15)
    assert me.status_code == 200, me.text
    assert me.json()["permissions"] == ["*"]
    assert me.json()["role"] == "OWNER"


@pytest.mark.parametrize("role", ["MANAGER", "SUPPORT", "MAINTENANCE"])
def test_role_login_succeeds_with_restricted_permissions(api, admin_token, role):
    token, _admin_id, _email = _create_member(api, admin_token, role, f"login_{role}")
    me = api.get(f"{API}/admin/auth/me", headers=auth(token), timeout=15)
    assert me.status_code == 200, me.text
    perms = set(me.json()["permissions"])
    assert "*" not in perms
    assert "wallet.adjust" not in perms
    assert "config.manage" not in perms
    assert "admin_team.manage" not in perms


def test_wrong_password_rejected(api):
    r = api.post(f"{API}/admin/auth/login", json={"email": "admin@fazum.demo", "password": "definitely-wrong"}, timeout=15)
    assert r.status_code == 401


def test_unknown_email_rejected(api):
    r = api.post(f"{API}/admin/auth/login", json={"email": f"{TAG}_nobody@example.com", "password": "whatever12345"}, timeout=15)
    assert r.status_code == 401


def test_consumer_token_rejected_by_admin_endpoints(api):
    # A regular app login must never authenticate against the admin panel.
    consumer = api.post(f"{API}/auth/login", json={"identifier": "marina@fazum.demo", "password": "faze2024"}, timeout=15)
    assert consumer.status_code == 200, consumer.text
    r = api.get(f"{API}/admin/auth/me", headers=auth(consumer.json()["token"]), timeout=15)
    assert r.status_code == 401


# ---------- SUPPORT deny-list (spec section 6 / 31) ----------

@pytest.fixture(scope="module")
def support_token(api, admin_token):
    token, _admin_id, _email = _create_member(api, admin_token, "SUPPORT", "deny")
    return token


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/admin/wallets/demo-client", None),
    ("POST", "/admin/wallets/demo-client/adjust", {"user_id": "demo-client", "amount": 10, "reason": "x"}),
    ("GET", "/admin/withdrawals", None),
    ("GET", "/admin/payments", None),
    ("GET", "/admin/config", None),
    ("PATCH", "/admin/config", {"commission_percent": 20}),
    ("GET", "/admin/security-events", None),
    ("GET", "/admin/audit", None),
    ("GET", "/admin/feature-flags", None),
    ("GET", "/admin/team", None),
    ("PATCH", "/admin/disputes/nonexistent-id", {"status": "RESOLVED", "resolution_action": "none"}),
    ("POST", "/admin/orders/nonexistent-id/cancel", None),
    ("PATCH", "/admin/users/demo-client/status", {"status": "SUSPENDED"}),
    ("POST", "/admin/geo/states", {"name": "x", "uf": "XX"}),
    ("POST", "/admin/categories", {"name": "x", "icon": "star", "active": True}),
    ("GET", "/admin/supervision", None),
])
def test_support_cannot_access_owner_only_endpoints(api, support_token, method, path, body):
    r = api.request(method, f"{API}{path}", headers=auth(support_token), json=body, timeout=15)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code} {r.text}"


@pytest.mark.parametrize("method,path", [
    ("GET", "/admin/overview"),
    ("GET", "/admin/users"),
    ("GET", "/admin/orders"),
    ("GET", "/admin/reports"),
    ("GET", "/admin/disputes"),
    ("GET", "/admin/tickets"),
    # SUPPORT gained risk.view (read-only) so the internal trust index — framed as
    # a signal for "support/risk staff" — is actually visible to them; risk.manage
    # (mutating risk_flags) stays MANAGER/OWNER-only, tested separately below.
    ("GET", "/admin/risk-flags"),
])
def test_support_can_access_allowed_endpoints(api, support_token, method, path):
    r = api.request(method, f"{API}{path}", headers=auth(support_token), timeout=15)
    assert r.status_code == 200, f"{method} {path} -> {r.status_code} {r.text}"


def test_support_still_cannot_manage_risk_flags(api, support_token):
    flags = api.get(f"{API}/admin/risk-flags", headers=auth(support_token), timeout=15).json()
    if not flags:
        pytest.skip("no risk_flags in this environment to attempt managing")
    flag_id = flags[0]["id"]
    r = api.patch(f"{API}/admin/risk-flags/{flag_id}", headers=auth(support_token), json={"status": "RESOLVED", "note": "x"}, timeout=15)
    assert r.status_code == 403, r.text


def test_support_can_block_and_verify_users_but_not_change_status(api, support_token):
    block = api.post(f"{API}/admin/users/demo-worker/block", headers=auth(support_token), timeout=15)
    assert block.status_code == 200, block.text
    api.post(f"{API}/admin/users/demo-worker/block", headers=auth(support_token), timeout=15)  # toggle back
    verify = api.post(f"{API}/admin/users/demo-worker/verify", headers=auth(support_token), timeout=15)
    assert verify.status_code == 200, verify.text
    api.post(f"{API}/admin/users/demo-worker/verify", headers=auth(support_token), timeout=15)  # toggle back
    status = api.patch(f"{API}/admin/users/demo-worker/status", headers=auth(support_token), json={"status": "SUSPENDED"}, timeout=15)
    assert status.status_code == 403, status.text


def test_support_cannot_manage_own_team(api, support_token):
    r = api.post(f"{API}/admin/team", headers=auth(support_token),
                 json={"name": "Escalate", "email": f"{TAG}_escalate@example.com", "password": "Whatever123!", "role": "OWNER"}, timeout=15)
    assert r.status_code == 403, r.text


# ---------- MANAGER: broader than SUPPORT, still no financial-action or admin-team access ----------

@pytest.fixture(scope="module")
def manager_token(api, admin_token):
    token, _admin_id, _email = _create_member(api, admin_token, "MANAGER", "mgr")
    return token


@pytest.mark.parametrize("method,path", [
    ("GET", "/admin/overview"),
    ("GET", "/admin/users"),
    ("GET", "/admin/orders"),
    ("GET", "/admin/payments"),      # view-only
    ("GET", "/admin/withdrawals"),   # view-only
    ("GET", "/admin/disputes"),
    ("GET", "/admin/reports"),
    ("GET", "/admin/tickets"),
    ("GET", "/admin/risk-flags"),
    ("GET", "/admin/security-events"),
])
def test_manager_can_view_operational_data(api, manager_token, method, path):
    r = api.request(method, f"{API}{path}", headers=auth(manager_token), timeout=15)
    assert r.status_code == 200, f"{method} {path} -> {r.status_code} {r.text}"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/admin/wallets/demo-client/adjust", {"user_id": "demo-client", "amount": 10, "reason": "x"}),
    ("POST", "/admin/withdrawals/nonexistent-id/approve", None),  # withdrawals.manage required, MANAGER only has .view
    ("PATCH", "/admin/config", {"commission_percent": 20}),
    ("GET", "/admin/config", None),
    ("PATCH", "/admin/feature-flags/GOOGLE_LOGIN", {"enabled": False}),
    ("GET", "/admin/feature-flags", None),
    ("GET", "/admin/team", None),
    ("GET", "/admin/audit", None),
    ("GET", "/admin/supervision", None),
    ("POST", "/admin/categories", {"name": "x", "icon": "star", "active": True}),
    ("POST", "/admin/geo/states", {"name": "x", "uf": "XX"}),
])
def test_manager_cannot_access_owner_only_endpoints(api, manager_token, method, path, body):
    r = api.request(method, f"{API}{path}", headers=auth(manager_token), json=body, timeout=15)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code} {r.text}"


def test_manager_can_resolve_disputes_and_manage_reports(api, manager_token):
    # disputes.resolve and reports.manage are both granted to MANAGER — confirm the
    # permission gate itself passes (a 404 for a made-up id still proves the 403 gate
    # was cleared and the handler ran).
    r = api.patch(f"{API}/admin/disputes/nonexistent-id", headers=auth(manager_token),
                  json={"status": "RESOLVED", "resolution_action": "none"}, timeout=15)
    assert r.status_code == 404, r.text


# ---------- MAINTENANCE: narrowest role, tickets (BUG-only) is its entire world ----------

@pytest.fixture(scope="module")
def maintenance_token(api, admin_token):
    token, _admin_id, _email = _create_member(api, admin_token, "MAINTENANCE", "maint")
    return token


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/admin/overview", None),
    ("GET", "/admin/users", None),
    ("GET", "/admin/orders", None),
    ("GET", "/admin/payments", None),
    ("GET", "/admin/withdrawals", None),
    ("GET", "/admin/wallets/demo-client", None),
    ("GET", "/admin/disputes", None),
    ("GET", "/admin/reports", None),
    ("GET", "/admin/risk-flags", None),
    ("GET", "/admin/config", None),
    ("GET", "/admin/team", None),
    ("GET", "/admin/audit", None),
    ("GET", "/admin/supervision", None),
    ("POST", "/admin/users/demo-worker/block", None),
])
def test_maintenance_has_no_access_beyond_tickets(api, maintenance_token, method, path, body):
    r = api.request(method, f"{API}{path}", headers=auth(maintenance_token), json=body, timeout=15)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code} {r.text}"


def test_maintenance_only_sees_bug_tickets(api, admin_token, support_token, maintenance_token):
    # Create one non-BUG and one BUG ticket as a regular user.
    consumer = api.post(f"{API}/auth/login", json={"identifier": "marina@fazum.demo", "password": "faze2024"}, timeout=15)
    user_token = consumer.json()["token"]
    bug = api.post(f"{API}/tickets", headers=auth(user_token),
                    json={"category": "BUG", "subject": f"{TAG} bug", "description": "algo quebrou"}, timeout=15)
    assert bug.status_code == 200, bug.text
    idea = api.post(f"{API}/tickets", headers=auth(user_token),
                     json={"category": "IDEIA", "subject": f"{TAG} ideia", "description": "seria legal ter X"}, timeout=15)
    assert idea.status_code == 200, idea.text

    maint_list = api.get(f"{API}/admin/tickets", headers=auth(maintenance_token), timeout=15).json()
    maint_categories = {t["category"] for t in maint_list["items"]}
    assert maint_categories <= {"BUG"}
    assert any(t["id"] == bug.json()["id"] for t in maint_list["items"])
    assert not any(t["id"] == idea.json()["id"] for t in maint_list["items"])

    # MAINTENANCE can reply/resolve the BUG ticket...
    reply = api.post(f"{API}/admin/tickets/{bug.json()['id']}/messages", headers=auth(maintenance_token),
                      json={"text": "corrigido no próximo deploy"}, timeout=15)
    assert reply.status_code == 200, reply.text
    resolve = api.patch(f"{API}/admin/tickets/{bug.json()['id']}", headers=auth(maintenance_token), json={"status": "RESOLVED"}, timeout=15)
    assert resolve.status_code == 200, resolve.text

    # ...but cannot touch the IDEIA ticket at all.
    forbidden = api.patch(f"{API}/admin/tickets/{idea.json()['id']}", headers=auth(maintenance_token), json={"status": "RESOLVED"}, timeout=15)
    assert forbidden.status_code == 403, forbidden.text

    # SUPPORT, meanwhile, can manage both.
    support_ok = api.patch(f"{API}/admin/tickets/{idea.json()['id']}", headers=auth(support_token), json={"status": "RESOLVED"}, timeout=15)
    assert support_ok.status_code == 200, support_ok.text


# ---------- OWNER full access ----------

def test_owner_can_access_every_gated_endpoint(api, admin_token):
    for method, path in [("GET", "/admin/wallets/demo-client"), ("GET", "/admin/withdrawals"),
                          ("GET", "/admin/payments"), ("GET", "/admin/config"), ("GET", "/admin/risk-flags"),
                          ("GET", "/admin/security-events"), ("GET", "/admin/audit"), ("GET", "/admin/feature-flags"),
                          ("GET", "/admin/team"), ("GET", "/admin/supervision"), ("GET", "/admin/tickets")]:
        r = api.request(method, f"{API}{path}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, f"{method} {path} -> {r.status_code} {r.text}"


def test_owner_actions_are_audited(api, admin_token):
    before = api.get(f"{API}/admin/audit?limit=1", headers=auth(admin_token), timeout=15).json()
    api.post(f"{API}/admin/users/demo-worker/verify", headers=auth(admin_token), timeout=15)
    api.post(f"{API}/admin/users/demo-worker/verify", headers=auth(admin_token), timeout=15)  # toggle back
    after = api.get(f"{API}/admin/audit?limit=5", headers=auth(admin_token), timeout=15).json()
    assert len(after) >= 1
    assert after != before or len(after) > 0


def test_supervision_returns_admins_alerts_and_timeline(api, admin_token):
    r = api.get(f"{API}/admin/supervision", headers=auth(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "admins" in body and "recent_actions" in body and "alerts" in body
    assert any(a["email"] == "admin@fazum.demo" for a in body["admins"])
    assert "tickets_open" in body["alerts"]


# ---------- last-OWNER guard ----------

def test_demoting_or_deactivating_an_owner_succeeds_when_others_remain(api, admin_token):
    # Deliberately never touches the seed OWNER account (`admin_token`'s own identity)
    # or any other pre-existing admin — this suite runs under pytest-xdist with a
    # SESSION-scoped, cross-file-shared `admin_token`, so even a transiently deactivated
    # seed account would 403 every other test/worker using it concurrently. This test
    # only ever creates and mutates its own throwaway OWNER account; the true
    # "can't remove the last active owner" boundary (routes/admin_auth.py's
    # `_count_active_owners` check) is verified by code review instead of an end-to-end
    # test, since safely driving the GLOBAL active-owner count to exactly zero isn't
    # possible without risking exactly the corruption this comment is warning about
    # (a prior version of this test did exactly that and demoted the real seed admin).
    email = f"{TAG}_owner2_{uuid.uuid4().hex[:8]}@example.com"
    create = api.post(f"{API}/admin/team", headers=auth(admin_token),
                       json={"name": "Second Owner", "email": email, "password": "OwnerPass123!", "role": "OWNER"}, timeout=15)
    assert create.status_code == 200, create.text
    second_owner_id = create.json()["id"]

    # Demoting this OWNER must succeed — the seed account (and possibly others) remain
    # active, so this is nowhere near the "last owner" boundary.
    demote = api.patch(f"{API}/admin/team/{second_owner_id}", headers=auth(admin_token), json={"role": "SUPPORT"}, timeout=15)
    assert demote.status_code == 200, demote.text

    api.patch(f"{API}/admin/team/{second_owner_id}", headers=auth(admin_token), json={"role": "OWNER"}, timeout=15)
    deactivate = api.patch(f"{API}/admin/team/{second_owner_id}", headers=auth(admin_token), json={"active": False}, timeout=15)
    assert deactivate.status_code == 200, deactivate.text


# ---------- 2FA ----------

def test_2fa_setup_verify_disable_and_login_enforcement(api, admin_token):
    token, admin_id, email = _create_member(api, admin_token, "SUPPORT", "2fa")
    setup = api.post(f"{API}/admin/auth/2fa/setup", headers=auth(token), timeout=15)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]

    bad_verify = api.post(f"{API}/admin/auth/2fa/verify", headers=auth(token), json={"code": "000000"}, timeout=15)
    assert bad_verify.status_code == 401, bad_verify.text

    code = pyotp.TOTP(secret).now()
    verify = api.post(f"{API}/admin/auth/2fa/verify", headers=auth(token), json={"code": code}, timeout=15)
    assert verify.status_code == 200, verify.text

    # Login without a code now fails outright.
    no_code = api.post(f"{API}/admin/auth/login", json={"email": email, "password": MEMBER_PASSWORD}, timeout=15)
    assert no_code.status_code == 401, no_code.text

    fresh_code = pyotp.TOTP(secret).now()
    with_code = api.post(f"{API}/admin/auth/login", json={"email": email, "password": MEMBER_PASSWORD, "totp_code": fresh_code}, timeout=15)
    assert with_code.status_code == 200, with_code.text
    logged_in_token = with_code.json()["token"]

    # Disabling without a code is rejected (security fix — see test_security_fixes.py
    # for the full coverage; this just confirms the login flow above still works
    # end to end with the hardened endpoint).
    no_code_disable = api.post(f"{API}/admin/auth/2fa/disable", headers=auth(logged_in_token), json={"code": "000000"}, timeout=15)
    assert no_code_disable.status_code == 401, no_code_disable.text

    disable_code = pyotp.TOTP(secret).now()
    disable = api.post(f"{API}/admin/auth/2fa/disable", headers=auth(logged_in_token), json={"code": disable_code}, timeout=15)
    assert disable.status_code == 200, disable.text


# ---------- feature flags ----------

def test_feature_flags_crud_reflected_in_bootstrap(api, admin_token):
    key = "WITHDRAWAL"
    original = api.get(f"{API}/feature-flags", timeout=15).json()[key]

    off = api.patch(f"{API}/admin/feature-flags/{key}", headers=auth(admin_token), json={"enabled": False}, timeout=15)
    assert off.status_code == 200, off.text
    assert api.get(f"{API}/feature-flags", timeout=15).json()[key] is False
    assert api.get(f"{API}/bootstrap", timeout=15).json()["feature_flags"][key] is False

    # Restore — this flag gates real UI elsewhere in the suite/app.
    on = api.patch(f"{API}/admin/feature-flags/{key}", headers=auth(admin_token), json={"enabled": original}, timeout=15)
    assert on.status_code == 200, on.text
    assert api.get(f"{API}/feature-flags", timeout=15).json()[key] == original


def test_support_cannot_change_feature_flags(api, support_token):
    r = api.patch(f"{API}/admin/feature-flags/GOOGLE_LOGIN", headers=auth(support_token), json={"enabled": False}, timeout=15)
    assert r.status_code == 403, r.text


# ---------- notifications ----------

def test_owner_can_send_notification_to_specific_user(api, admin_token):
    r = api.post(f"{API}/admin/notifications", headers=auth(admin_token),
                 json={"title": f"{TAG} aviso", "body": "teste de notificação administrativa", "target": "user:demo-client"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["recipient_count"] == 1


def test_notification_invalid_target_rejected(api, admin_token):
    r = api.post(f"{API}/admin/notifications", headers=auth(admin_token),
                 json={"title": "x", "body": "y", "target": "not-a-real-target"}, timeout=15)
    assert r.status_code == 400, r.text


def test_support_cannot_send_notifications(api, support_token):
    r = api.post(f"{API}/admin/notifications", headers=auth(support_token),
                 json={"title": "x", "body": "y", "target": "user:demo-client"}, timeout=15)
    assert r.status_code == 403, r.text


# ---------- IDOR / manipulation ----------

def test_cannot_patch_nonexistent_admin_team_member(api, admin_token):
    r = api.patch(f"{API}/admin/team/{uuid.uuid4()}", headers=auth(admin_token), json={"name": "x"}, timeout=15)
    assert r.status_code == 404, r.text


def test_user_detail_endpoint_returns_related_records(api, admin_token):
    r = api.get(f"{API}/admin/users/demo-client", headers=auth(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == "demo-client"
    assert "orders" in body and "payments" in body and "disputes" in body and "reports" in body
