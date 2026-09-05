"""Tests for the expanded GET /users/{id}/stats reputation payload (public profile
feature). Every test uses fresh throwaway accounts per test — count-sensitive
assertions would be order-dependent and flaky under `pytest -n2 --dist loadscope`
if they shared fixtures whose completed/cancelled counts other tests could bump.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
TAG = f"PROF_{uuid.uuid4().hex[:6]}"

STATS_KEYS = {
    "completion_rate", "completed_count", "cancelled_count", "cancellation_rate_as_worker",
    "client_completed_count", "client_cancelled_count", "cancellation_rate_as_client",
    "repeat_client_rate", "avg_response_hours",
}


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


def make_order(api, client_token, budget=40):
    r = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} order", "description": "public profile test", "type": "favor",
        "category_id": "cat-entregas", "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
        "date_label": "Hoje", "time_label": "", "budget": budget, "photos": [], "fields": {},
        "urgent": False, "recurrence": "none",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def propose_and_accept(api, client_token, worker_token, order, amount=25):
    prop = api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
                     json={"amount": amount, "message": "", "eta": ""}, timeout=15)
    assert prop.status_code == 200, prop.text
    accept = api.post(f"{API}/proposals/{prop.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text
    return prop.json()


def complete_order(api, client_token, worker_token, order_id):
    start = api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15)
    assert start.status_code == 200, start.text
    complete = api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15)
    assert complete.status_code == 200, complete.text


def get_stats(api, user_id):
    r = api.get(f"{API}/users/{user_id}/stats", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_stats_shape_for_fresh_user_has_all_keys_and_nulls(api):
    _, user_id = _register(api, "prof_fresh")
    stats = get_stats(api, user_id)
    assert set(stats.keys()) == STATS_KEYS
    assert stats["completed_count"] == 0
    assert stats["cancelled_count"] == 0
    assert stats["client_completed_count"] == 0
    assert stats["client_cancelled_count"] == 0
    for key in ("completion_rate", "cancellation_rate_as_worker", "cancellation_rate_as_client",
                "repeat_client_rate", "avg_response_hours"):
        assert stats[key] is None, f"{key} should be None for a fresh account, got {stats[key]}"


def test_completion_and_worker_cancellation_are_complements(api):
    client_token, _ = _register(api, "prof_client_a")
    worker_token, worker_id = _register(api, "prof_worker_a")
    order = make_order(api, client_token)
    propose_and_accept(api, client_token, worker_token, order)
    complete_order(api, client_token, worker_token, order["id"])

    stats = get_stats(api, worker_id)
    assert stats["completed_count"] == 1
    assert stats["cancelled_count"] == 0
    assert stats["completion_rate"] == 1.0
    assert stats["cancellation_rate_as_worker"] == 0.0
    assert stats["completion_rate"] + stats["cancellation_rate_as_worker"] == 1.0


def test_cancellation_rate_as_client_reflects_cancelled_order(api):
    client_token, client_id = _register(api, "prof_client_b")
    order = make_order(api, client_token)
    cancel = api.post(f"{API}/orders/{order['id']}/cancel", headers=auth(client_token), timeout=15)
    assert cancel.status_code == 200, cancel.text

    stats = get_stats(api, client_id)
    assert stats["client_completed_count"] == 0
    assert stats["client_cancelled_count"] == 1
    assert stats["cancellation_rate_as_client"] == 1.0


def test_repeat_client_rate_detects_repeat_engagement(api):
    worker_token, worker_id = _register(api, "prof_worker_b")
    client_a_token, _ = _register(api, "prof_client_c")
    client_b_token, _ = _register(api, "prof_client_d")

    order1 = make_order(api, client_a_token)
    propose_and_accept(api, client_a_token, worker_token, order1)
    order2 = make_order(api, client_a_token)
    propose_and_accept(api, client_a_token, worker_token, order2)
    order3 = make_order(api, client_b_token)
    propose_and_accept(api, client_b_token, worker_token, order3)

    stats = get_stats(api, worker_id)
    assert stats["repeat_client_rate"] == 0.5


def test_avg_response_hours_present_after_proposal(api):
    client_token, _ = _register(api, "prof_client_e")
    worker_token, worker_id = _register(api, "prof_worker_c")
    order = make_order(api, client_token)
    api.post(f"{API}/orders/{order['id']}/proposals", headers=auth(worker_token),
              json={"amount": 25, "message": "", "eta": ""}, timeout=15)

    stats = get_stats(api, worker_id)
    assert stats["avg_response_hours"] is not None
    assert stats["avg_response_hours"] >= 0
