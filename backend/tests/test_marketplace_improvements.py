"""Tests for the marketplace-improvements pass: block enforcement, proposal
cancellation, report state machine, urgency/recurrence fields, and the
completion-rate stats endpoint. Reuses the throwaway-account pattern from
test_financial.py so these tests never touch the shared demo accounts.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fazum.demo"
DEMO_PASSWORD = "faze2024"
TEST_PASSWORD = "TestPass123!"
TAG = f"MKT_{uuid.uuid4().hex[:6]}"


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


@pytest.fixture(scope="session")
def _client(api):
    return _register(api, "mkt_client")


@pytest.fixture(scope="session")
def _worker(api):
    return _register(api, "mkt_worker")


@pytest.fixture(scope="session")
def client_token(_client):
    return _client[0]


@pytest.fixture(scope="session")
def client_id(_client):
    return _client[1]


@pytest.fixture(scope="session")
def worker_token(_worker):
    return _worker[0]


@pytest.fixture(scope="session")
def worker_id(_worker):
    return _worker[1]


def make_order(api, client_token, budget=40, urgent=False, recurrence="none"):
    r = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} order", "description": "marketplace test", "type": "favor",
        "category_id": "cat-entregas", "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
        "date_label": "Hoje", "time_label": "", "budget": budget, "photos": [], "fields": {},
        "urgent": urgent, "recurrence": recurrence,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- blocks: enforcement, not just decoration ----------

def test_cannot_block_self(api, client_token, client_id):
    r = api.post(f"{API}/blocks", headers=auth(client_token), json={"blocked_user_id": client_id}, timeout=15)
    assert r.status_code == 400


def test_block_prevents_proposal(api, client_token, worker_token, worker_id):
    order = make_order(api, client_token)
    r = api.post(f"{API}/blocks", headers=auth(client_token), json={"blocked_user_id": worker_id}, timeout=15)
    assert r.status_code == 200, r.text
    try:
        prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                         json={"amount": 30, "message": "", "eta": ""}, timeout=15)
        assert prop.status_code == 403, prop.text
    finally:
        api.delete(f"{API}/blocks/{worker_id}", headers=auth(client_token), timeout=15)


def test_block_prevents_message_both_directions(api, client_token, worker_token, worker_id, client_id):
    order = make_order(api, client_token)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert prop.status_code == 200, prop.text
    accept = api.post(f"{API}/proposals/{prop.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text

    r = api.post(f"{API}/blocks", headers=auth(worker_token), json={"blocked_user_id": client_id}, timeout=15)
    assert r.status_code == 200, r.text
    try:
        msg = api.post(f"{API}/orders/{order['id']}/messages", headers=auth(client_token),
                        json={"text": "oi", "image_b64": None}, timeout=15)
        assert msg.status_code == 403, msg.text
    finally:
        api.delete(f"{API}/blocks/{client_id}", headers=auth(worker_token), timeout=15)


def test_unblock_restores_interaction(api, client_token, worker_token, worker_id):
    order = make_order(api, client_token)
    api.post(f"{API}/blocks", headers=auth(client_token), json={"blocked_user_id": worker_id}, timeout=15)
    api.delete(f"{API}/blocks/{worker_id}", headers=auth(client_token), timeout=15)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert prop.status_code == 200, prop.text


def test_list_blocks_returns_blocked_user_info(api, client_token, worker_token, worker_id):
    api.post(f"{API}/blocks", headers=auth(client_token), json={"blocked_user_id": worker_id}, timeout=15)
    try:
        r = api.get(f"{API}/blocks", headers=auth(client_token), timeout=15)
        assert r.status_code == 200, r.text
        entries = [b for b in r.json() if b["blocked_user_id"] == worker_id]
        assert len(entries) == 1
        assert entries[0]["user"]["id"] == worker_id
    finally:
        api.delete(f"{API}/blocks/{worker_id}", headers=auth(client_token), timeout=15)


# ---------- proposal cancel ----------

def test_worker_can_cancel_own_pending_proposal(api, client_token, worker_token):
    order = make_order(api, client_token)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert prop.status_code == 200, prop.text
    r = api.post(f"{API}/proposals/{prop.json()['id']}/cancel", headers=auth(worker_token), timeout=15)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_cannot_cancel_someone_elses_proposal(api, client_token, worker_token):
    order = make_order(api, client_token)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    assert prop.status_code == 200, prop.text
    # The order's own client tries to cancel the worker's proposal.
    r = api.post(f"{API}/proposals/{prop.json()['id']}/cancel", headers=auth(client_token), timeout=15)
    assert r.status_code == 403


def test_double_cancel_fails_second_time(api, client_token, worker_token):
    order = make_order(api, client_token)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    proposal_id = prop.json()["id"]
    first = api.post(f"{API}/proposals/{proposal_id}/cancel", headers=auth(worker_token), timeout=15)
    assert first.status_code == 200
    second = api.post(f"{API}/proposals/{proposal_id}/cancel", headers=auth(worker_token), timeout=15)
    assert second.status_code == 400


def test_cannot_cancel_accepted_proposal(api, client_token, worker_token):
    order = make_order(api, client_token)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    proposal_id = prop.json()["id"]
    accept = api.post(f"{API}/proposals/{proposal_id}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text
    r = api.post(f"{API}/proposals/{proposal_id}/cancel", headers=auth(worker_token), timeout=15)
    assert r.status_code == 400


# ---------- report state machine ----------

def test_report_starts_open_uppercase(api, client_token, worker_id):
    r = api.post(f"{API}/reports", headers=auth(client_token),
                  json={"target_type": "user", "target_id": worker_id, "reason": "spam", "details": TAG}, timeout=15)
    assert r.status_code == 200 and r.json()["status"] == "OPEN"


def test_admin_can_transition_report_through_states(api, client_token, worker_id, admin_token):
    created = api.post(f"{API}/reports", headers=auth(client_token),
                        json={"target_type": "user", "target_id": worker_id, "reason": "spam", "details": TAG}, timeout=15)
    report_id = created.json()["id"]
    step1 = api.patch(f"{API}/admin/reports/{report_id}", headers=auth(admin_token),
                       json={"status": "UNDER_REVIEW", "resolution": ""}, timeout=15)
    assert step1.status_code == 200
    step2 = api.patch(f"{API}/admin/reports/{report_id}", headers=auth(admin_token),
                       json={"status": "REJECTED", "resolution": "sem evidencia"}, timeout=15)
    assert step2.status_code == 200


def test_admin_report_update_rejects_invalid_status(api, client_token, worker_id, admin_token):
    created = api.post(f"{API}/reports", headers=auth(client_token),
                        json={"target_type": "user", "target_id": worker_id, "reason": "spam", "details": TAG}, timeout=15)
    report_id = created.json()["id"]
    r = api.patch(f"{API}/admin/reports/{report_id}", headers=auth(admin_token),
                   json={"status": "made_up_status", "resolution": ""}, timeout=15)
    assert r.status_code == 400


def test_non_admin_cannot_update_report_status(api, client_token, worker_id, worker_token):
    created = api.post(f"{API}/reports", headers=auth(client_token),
                        json={"target_type": "user", "target_id": worker_id, "reason": "spam", "details": TAG}, timeout=15)
    report_id = created.json()["id"]
    r = api.patch(f"{API}/admin/reports/{report_id}", headers=auth(worker_token),
                   json={"status": "RESOLVED", "resolution": ""}, timeout=15)
    assert r.status_code in (401, 403)


# ---------- urgency / recurrence ----------

def test_urgent_and_recurrence_persist(api, client_token):
    order = make_order(api, client_token, urgent=True, recurrence="weekly")
    assert order["urgent"] is True
    assert order["recurrence"] == "weekly"
    fetched = api.get(f"{API}/orders/{order['id']}", timeout=15)
    assert fetched.json()["urgent"] is True
    assert fetched.json()["recurrence"] == "weekly"


def test_urgent_filter_excludes_non_urgent(api, client_token):
    urgent_order = make_order(api, client_token, urgent=True)
    normal_order = make_order(api, client_token, urgent=False)
    r = api.get(f"{API}/orders?city_id=city-parauapebas&status=published&urgent=true&limit=100", timeout=15)
    ids = [o["id"] for o in r.json()]
    assert urgent_order["id"] in ids
    assert normal_order["id"] not in ids


# ---------- completion-rate stats ----------

def test_stats_none_before_any_completed_or_cancelled_job(api, client_id):
    # client_id is never used as a worker_id anywhere in this file, so its
    # completion_rate (computed from orders where worker_id == this user) must be
    # None — reuses the existing fixture instead of burning another registration
    # against /auth/register's shared per-IP rate limit.
    r = api.get(f"{API}/users/{client_id}/stats", timeout=15)
    assert r.status_code == 200
    assert r.json()["completion_rate"] is None


def test_stats_reflect_completed_ratio(api, client_token, worker_token, worker_id):
    order = make_order(api, client_token, budget=25)
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": 25, "message": "", "eta": ""}, timeout=15)
    accept = api.post(f"{API}/proposals/{prop.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text
    start = api.post(f"{API}/orders/{order['id']}/start", headers=auth(worker_token), timeout=15)
    assert start.status_code == 200, start.text
    complete = api.post(f"{API}/orders/{order['id']}/complete", headers=auth(client_token), timeout=15)
    assert complete.status_code == 200, complete.text

    r = api.get(f"{API}/users/{worker_id}/stats", timeout=15)
    assert r.status_code == 200
    assert r.json()["completion_rate"] is not None
    assert 0.0 <= r.json()["completion_rate"] <= 1.0
