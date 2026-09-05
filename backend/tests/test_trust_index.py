"""Tests for the internal trust index surfaced on GET /admin/users/{id} (see
trust_index.py). Every scenario is built purely through the public HTTP API
(no direct DB access, matching this test suite's convention) — a GREEN case is
just a fresh verified account, and a RED case is reached honestly via 3 real
reports against a target user, which alone (2 pts each, capped at 3) already
clears the RED threshold.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
MEMBER_PASSWORD = "MemberPass123!"
TAG = f"TRUST_{uuid.uuid4().hex[:6]}"


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


def _create_admin_member(api, admin_token, role, tag_suffix=""):
    email = f"{TAG}{tag_suffix}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/admin/team", headers=auth(admin_token),
                 json={"name": f"Teste {role}", "email": email, "password": MEMBER_PASSWORD, "role": role}, timeout=15)
    assert r.status_code == 200, r.text
    login = api.post(f"{API}/admin/auth/login", json={"email": email, "password": MEMBER_PASSWORD}, timeout=15)
    assert login.status_code == 200, login.text
    return login.json()["token"]


def test_fresh_user_is_green(api, admin_token):
    _, user_id = _register(api, "trust_fresh")
    r = api.get(f"{API}/admin/users/{user_id}", headers=auth(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    trust = r.json()["trust_index"]
    assert trust["level"] == "GREEN"
    assert trust["score"] < 2


def test_user_with_multiple_reports_is_red_with_explainable_factors(api, admin_token):
    _, target_id = _register(api, "trust_target")
    for i in range(3):
        reporter_token, _ = _register(api, f"trust_reporter_{i}")
        r = api.post(f"{API}/reports", headers=auth(reporter_token),
                     json={"target_type": "user", "target_id": target_id, "reason": "spam", "details": f"{TAG} report {i}"}, timeout=15)
        assert r.status_code == 200, r.text

    detail = api.get(f"{API}/admin/users/{target_id}", headers=auth(admin_token), timeout=15)
    assert detail.status_code == 200, detail.text
    trust = detail.json()["trust_index"]
    assert trust["level"] == "RED"
    assert trust["score"] >= 5
    assert len(trust["factors"]) > 0
    assert any(f["reason"] == "reports_against" for f in trust["factors"])
    for f in trust["factors"]:
        assert f["reason"] and "detail" in f and "weight" in f


def test_owner_manager_support_see_trust_index(api, admin_token):
    _, user_id = _register(api, "trust_visibility")
    for role in ("MANAGER", "SUPPORT"):
        token = _create_admin_member(api, admin_token, role, f"_vis_{role}")
        r = api.get(f"{API}/admin/users/{user_id}", headers=auth(token), timeout=15)
        assert r.status_code == 200, r.text
        assert "trust_index" in r.json(), f"{role} should see trust_index after the risk.view fix"

    owner_check = api.get(f"{API}/admin/users/{user_id}", headers=auth(admin_token), timeout=15)
    assert owner_check.status_code == 200
    assert "trust_index" in owner_check.json()


def test_maintenance_cannot_view_user_detail_at_all(api, admin_token):
    # MAINTENANCE has no users.view in this system — it never reaches the
    # trust_index gate because the whole endpoint 403s first (least privilege).
    _, user_id = _register(api, "trust_maintenance")
    token = _create_admin_member(api, admin_token, "MAINTENANCE", "_maint")
    r = api.get(f"{API}/admin/users/{user_id}", headers=auth(token), timeout=15)
    assert r.status_code == 403


def test_random_consumer_cannot_view_admin_user_detail(api):
    consumer_token, _ = _register(api, "trust_outsider")
    _, target_id = _register(api, "trust_outsider_target")
    r = api.get(f"{API}/admin/users/{target_id}", headers=auth(consumer_token), timeout=15)
    assert r.status_code in (401, 403)
