"""Tests for POST /webhooks/payment-provider's deposit reconciliation
(backend/routes/wallet.py). ASAAS only ever reaches this deposit path today —
AsaasProvider.create_pix_charge is deliberately still NotImplementedError (no real
sandbox credentials exist in this environment), so there is no HTTP-reachable way
to put a deposit into PROCESSING the way a real ASAAS charge would. This file is
the one exception in the suite to the "drive everything through HTTP" convention:
it seeds that one precondition directly via `database.db` (the same Mongo instance
the running server uses — confirmed via database.py's MONGO_URL/DB_NAME), because
that's exactly the gap a webhook test always has to bridge (the event-source side
isn't built yet, only the receiver is). Everything else — auth, wallet balance,
deposit status after the fact — goes through the real HTTP API.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

_backend_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
WEBHOOK_SECRET = _backend_env.get("ASAAS_WEBHOOK_SECRET") or os.environ.get("ASAAS_WEBHOOK_SECRET", "")
MONGO_URL = _backend_env.get("MONGO_URL") or os.environ.get("MONGO_URL", "")
DB_NAME = _backend_env.get("DB_NAME") or os.environ.get("DB_NAME", "")

TEST_PASSWORD = "TestPass123!"
TAG = f"PAYWH_{uuid.uuid4().hex[:6]}"

pytestmark = pytest.mark.skipif(not WEBHOOK_SECRET, reason="ASAAS_WEBHOOK_SECRET not configured in this environment")


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


def _seed_processing_deposit(user_id: str, amount: float, provider_transaction_id: str) -> str:
    # Simulates the row `POST /wallet/deposits` would leave behind after a real
    # `create_pix_charge` call — same shape, same collection, just written directly
    # since that call path isn't wired to a live gateway in this environment.
    # A throwaway Motor client, created and closed within this one asyncio.run()
    # call, avoids reusing a client across separate event loops (each asyncio.run()
    # spins up and tears down its own loop, and Motor's client isn't safe to reuse
    # across loops that way).
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _insert():
        client = AsyncIOMotorClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            deposit_id = str(uuid.uuid4())
            iso_now = datetime.now(timezone.utc).isoformat()
            await db.deposits.insert_one({
                "id": deposit_id, "user_id": user_id, "amount": amount, "method": "pix",
                "status": "PROCESSING", "provider": "asaas", "provider_transaction_id": provider_transaction_id,
                "created_at": iso_now, "updated_at": iso_now,
            })
            return deposit_id
        finally:
            client.close()

    return asyncio.run(_insert())


def _get_deposit(api, token, deposit_id):
    r = api.get(f"{API}/wallet/deposits/{deposit_id}", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _get_available_balance(api, token):
    r = api.get(f"{API}/wallet", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["available"]


def _send_webhook(event_id, event, payment, token=None):
    payload = {"id": event_id, "event": event, "payment": payment}
    headers = {"Content-Type": "application/json", "asaas-access-token": token if token is not None else WEBHOOK_SECRET}
    return requests.post(f"{API}/webhooks/payment-provider", json=payload, headers=headers, timeout=15)


def test_payment_received_credits_wallet_and_completes_deposit(api):
    client_token, client_id = _register(api, "paywh_recv")
    provider_txn_id = f"{TAG}-pay-{uuid.uuid4().hex[:8]}"
    deposit_id = _seed_processing_deposit(client_id, 55.0, provider_txn_id)
    before = _get_available_balance(api, client_token)

    r = _send_webhook(f"{TAG}-evt-recv", "PAYMENT_RECEIVED", {"id": provider_txn_id, "externalReference": deposit_id})
    assert r.status_code == 200, r.text
    assert r.json().get("duplicate") is not True

    after = _get_available_balance(api, client_token)
    assert after == pytest.approx(before + 55.0, abs=0.01)
    deposit = _get_deposit(api, client_token, deposit_id)
    assert deposit["status"] == "COMPLETED"


def test_duplicate_payment_received_does_not_double_credit(api):
    client_token, client_id = _register(api, "paywh_dup")
    provider_txn_id = f"{TAG}-pay-{uuid.uuid4().hex[:8]}"
    deposit_id = _seed_processing_deposit(client_id, 30.0, provider_txn_id)
    before = _get_available_balance(api, client_token)
    event_id = f"{TAG}-evt-dup"
    payment = {"id": provider_txn_id, "externalReference": deposit_id}

    r1 = _send_webhook(event_id, "PAYMENT_RECEIVED", payment)
    assert r1.status_code == 200, r1.text
    r2 = _send_webhook(event_id, "PAYMENT_RECEIVED", payment)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True

    after = _get_available_balance(api, client_token)
    assert after == pytest.approx(before + 30.0, abs=0.01)


def test_payment_overdue_marks_deposit_failed_without_touching_wallet(api):
    client_token, client_id = _register(api, "paywh_overdue")
    provider_txn_id = f"{TAG}-pay-{uuid.uuid4().hex[:8]}"
    deposit_id = _seed_processing_deposit(client_id, 20.0, provider_txn_id)
    before = _get_available_balance(api, client_token)

    r = _send_webhook(f"{TAG}-evt-overdue", "PAYMENT_OVERDUE", {"id": provider_txn_id, "externalReference": deposit_id})
    assert r.status_code == 200, r.text

    after = _get_available_balance(api, client_token)
    assert after == pytest.approx(before, abs=0.01)
    deposit = _get_deposit(api, client_token, deposit_id)
    assert deposit["status"] == "FAILED"


def test_wrong_access_token_rejected_and_deposit_untouched(api):
    client_token, client_id = _register(api, "paywh_badtoken")
    provider_txn_id = f"{TAG}-pay-{uuid.uuid4().hex[:8]}"
    deposit_id = _seed_processing_deposit(client_id, 15.0, provider_txn_id)

    r = _send_webhook(f"{TAG}-evt-badtoken", "PAYMENT_RECEIVED",
                       {"id": provider_txn_id, "externalReference": deposit_id}, token="not-the-real-token")
    assert r.status_code == 401

    deposit = _get_deposit(api, client_token, deposit_id)
    assert deposit["status"] == "PROCESSING"
