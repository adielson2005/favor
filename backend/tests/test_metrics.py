"""Tests for GET /admin/metrics (backend/metrics.py) — the platform-wide "Índice
FAZUM" dashboard. This endpoint aggregates over the WHOLE orders/payments history,
which this test suite shares with every other test file — so exact rate values
(resolution_rate, dispute_rate, etc.) can't be asserted against a fixed number
without a dedicated isolated database. Instead: (1) shape/bounds sanity against
real accumulated data, (2) permission gating (fully deterministic), and (3) a
before/after delta on raw counts around one fully-known order+payment lifecycle,
which stays exact regardless of how much other data exists.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
MEMBER_PASSWORD = "MemberPass123!"
TAG = f"METRICS_{uuid.uuid4().hex[:6]}"


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


def _credit(api, admin_token, user_id, amount):
    r = api.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(admin_token),
                 json={"user_id": user_id, "amount": amount, "reason": TAG}, timeout=15)
    assert r.status_code == 200, r.text


def _get_metrics(api, token):
    r = api.get(f"{API}/admin/metrics", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _category_row(metrics, category_id):
    return next((c for c in metrics["categories_top"] if c["category_id"] == category_id), None)


def test_shape_and_bounds_against_real_data(api, admin_token):
    m = _get_metrics(api, admin_token)
    op = m["operational"]
    for rate_key in ("resolution_rate", "cancellation_rate", "dispute_rate", "recurring_client_rate"):
        v = op[rate_key]
        assert v is None or 0.0 <= v <= 1.0, f"{rate_key}={v} out of [0,1]"
    assert isinstance(op["active_clients_30d"], int) and op["active_clients_30d"] >= 0
    assert isinstance(op["jobs_completed"], int) and op["jobs_completed"] >= 0
    assert isinstance(m["categories_top"], list)
    assert isinstance(m["demand_supply_by_neighborhood"], list)
    assert 0 <= m["fazum_index"]["score"] <= 100
    assert isinstance(m["fazum_index"]["factors"], list)
    # ?days= narrows the window without erroring
    m30 = api.get(f"{API}/admin/metrics?days=30", headers=auth(admin_token), timeout=15)
    assert m30.status_code == 200, m30.text
    assert m30.json()["window_days"] == 30


def test_permission_gating_of_money_fields(api, admin_token):
    owner_metrics = _get_metrics(api, admin_token)
    assert "revenue" in owner_metrics and "gmv" in owner_metrics

    manager_token = _create_admin_member(api, admin_token, "MANAGER", "_mgr")
    manager_metrics = _get_metrics(api, manager_token)
    assert "revenue" in manager_metrics and "gmv" in manager_metrics

    support_token = _create_admin_member(api, admin_token, "SUPPORT", "_sup")
    support_metrics = _get_metrics(api, support_token)
    assert "revenue" not in support_metrics and "gmv" not in support_metrics
    assert "operational" in support_metrics and "fazum_index" in support_metrics

    r = api.get(f"{API}/admin/metrics", timeout=15)
    assert r.status_code == 401


def test_completed_order_delta_reflected_exactly(api, admin_token):
    client_token, client_id = _register(api, "metrics_client")
    worker_token, _ = _register(api, "metrics_worker")
    _credit(api, admin_token, client_id, 100)

    before = _get_metrics(api, admin_token)
    before_jobs = before["operational"]["jobs_completed"]
    before_cat = _category_row(before, "cat-entregas")
    before_cat_completed = before_cat["completed_orders"] if before_cat else 0
    before_revenue = before["revenue"]["commission_total"]

    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} order", "description": "metrics delta test", "type": "favor",
        "category_id": "cat-entregas", "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
        "date_label": "Hoje", "time_label": "", "budget": 40, "photos": [], "fields": {},
        "urgent": False, "recurrence": "none",
    }, timeout=15)
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 40, "message": "", "eta": ""}, timeout=15)
    assert proposal.status_code == 200, proposal.text
    accept = api.post(f"{API}/proposals/{proposal.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text
    pay = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    assert pay.status_code == 200, pay.text
    commission_amount = pay.json()["commission_amount"]
    start = api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15)
    assert start.status_code == 200, start.text
    complete = api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15)
    assert complete.status_code == 200, complete.text

    after = _get_metrics(api, admin_token)
    assert after["operational"]["jobs_completed"] == before_jobs + 1
    after_cat = _category_row(after, "cat-entregas")
    assert after_cat is not None
    assert after_cat["completed_orders"] == before_cat_completed + 1
    assert after["revenue"]["commission_total"] == pytest.approx(before_revenue + commission_amount, abs=0.01)
