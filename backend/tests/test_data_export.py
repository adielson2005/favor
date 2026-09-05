"""Tests for GET /auth/me/export (backend/data_export.py) — LGPD Art. 18 right of
access. Uses fresh throwaway accounts per test, never the shared demo accounts,
since this endpoint returns literally everything tied to a user_id and any
cross-test data leakage would be immediately visible in the response.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
TAG = f"EXPORT_{uuid.uuid4().hex[:6]}"


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


def _export(api, token):
    r = api.get(f"{API}/auth/me/export", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_export_reflects_real_data_across_sections(api, admin_token):
    token, user_id = _register(api, "export_full")

    credit = api.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(admin_token),
                       json={"user_id": user_id, "amount": 50, "reason": TAG}, timeout=15)
    assert credit.status_code == 200, credit.text

    order = api.post(f"{API}/orders", headers=auth(token), json={
        "title": f"{TAG} order", "description": "export test", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 30, "photos": [], "fields": {},
    }, timeout=15)
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]

    report = api.post(f"{API}/reports", headers=auth(token),
                       json={"target_type": "order", "target_id": order_id, "reason": TAG, "details": "test"}, timeout=15)
    assert report.status_code == 200, report.text

    bank = api.post(f"{API}/bank-accounts", headers=auth(token), json={
        "holder_name": "Export Test", "document": "12345678900", "bank_code": "001",
        "agency": "0001", "account_number": "99998888", "account_type": "checking", "password": TEST_PASSWORD,
    }, timeout=15)
    assert bank.status_code == 200, bank.text

    data = _export(api, token)

    assert data["profile"]["id"] == user_id
    assert len(data["orders_as_client"]) == 1
    assert data["orders_as_client"][0]["id"] == order_id
    assert len(data["reports_filed"]) == 1
    assert data["reports_filed"][0]["reason"] == TAG
    assert data["wallet"]["available"] == 50.0
    assert len(data["wallet_transactions"]) == 1
    assert len(data["bank_accounts"]) == 1
    assert data["bank_accounts"][0]["account_number_masked"] == "****8888"
    # Never the plaintext document, only masked, and never the raw encrypted value either.
    assert "12345678900" not in str(data["bank_accounts"])
    assert "document" not in data["bank_accounts"][0]

    # Untouched sections still come back as valid empty lists, not missing/errored.
    assert data["favorites"] == []
    assert data["disputes"] == []
    assert data["support_tickets"] == []


def test_export_empty_account_returns_valid_empty_sections(api):
    token, _ = _register(api, "export_empty")
    data = _export(api, token)
    # security_events is deliberately excluded here: calling this very endpoint
    # logs a "data_export_requested" event (see routes/auth.py), so a truly empty
    # list is never observable through the endpoint that itself adds an entry.
    for key in ("orders_as_client", "orders_as_worker", "proposals_sent", "messages_sent",
                "reviews_given", "reviews_received", "reports_filed", "blocks", "favorites",
                "notifications", "wallet_transactions", "payments_as_client", "payments_as_worker",
                "withdrawals", "deposits", "bank_accounts", "disputes", "support_tickets"):
        assert data[key] == [], f"{key} should be an empty list for a brand-new account"
    assert data["wallet"]["available"] == 0.0
    assert any(e["event"] == "data_export_requested" for e in data["security_events"])


def test_export_requires_auth():
    r = requests.get(f"{API}/auth/me/export", timeout=15)
    assert r.status_code == 401


def test_export_rate_limited_after_five_requests(api):
    token, _ = _register(api, "export_ratelimit")
    for _ in range(5):
        r = api.get(f"{API}/auth/me/export", headers=auth(token), timeout=15)
        assert r.status_code == 200, r.text
    r = api.get(f"{API}/auth/me/export", headers=auth(token), timeout=15)
    assert r.status_code == 429, r.text
