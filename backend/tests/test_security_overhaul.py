"""Security/antifraude/financial-protection overhaul tests.

Covers the explicit scenario list from the security spec: full happy path,
differentiated cancellation, both-sided disputes (refund + release-to-worker +
rejection), duplicate payment/webhook/withdrawal, tampering (value/user/status),
cross-user access denial, chat external-payment detection escalation, risk-engine
password reauth (MEDIUM) and hard block (CRITICAL), and admin race conditions.

Follows the exact fixture/helper pattern already established in test_financial.py —
throwaway `_register()` accounts per session, never the shared demo accounts.
"""
import concurrent.futures
import json
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

# The server process loads backend/.env itself (database.py), but this pytest
# process doesn't — read it directly so the webhook tests can compute a valid
# signature instead of skipping just because os.environ wasn't populated for us.
_backend_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
WEBHOOK_SECRET = _backend_env.get("ASAAS_WEBHOOK_SECRET") or os.environ.get("ASAAS_WEBHOOK_SECRET", "")

ADMIN_EMAIL = "admin@fazum.demo"
DEMO_PASSWORD = "faze2024"
TEST_PASSWORD = "TestPass123!"

TAG = f"SEC_{uuid.uuid4().hex[:6]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _login(api, email, password=DEMO_PASSWORD):
    r = api.post(f"{API}/auth/login", json={"identifier": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _random_phone():
    return "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"


def _register(api, tag, activate=True):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    token, user_id = body["token"], body["user"]["id"]
    if activate:
        hdrs = auth(token)
        api.post(f"{API}/auth/verify-email", headers=hdrs, json={"code": body["dev_code_email"]}, timeout=15)
        api.post(f"{API}/auth/verify-phone", headers=hdrs, json={"code": body["dev_code_phone"]}, timeout=15)
    return token, user_id


@pytest.fixture(scope="session")
def _client(api):
    return _register(api, "sec_client")


@pytest.fixture(scope="session")
def _worker(api):
    return _register(api, "sec_worker")


@pytest.fixture(scope="session")
def _outsider(api):
    return _register(api, "sec_outsider")


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


@pytest.fixture(scope="session")
def outsider_token(_outsider):
    return _outsider[0]


def credit(api, admin_token, user_id, amount, reason=None):
    r = api.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(admin_token),
                 json={"user_id": user_id, "amount": amount, "reason": reason or TAG}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def credit_large(api, admin_token, user_id, amount, reason=None):
    # admin_token (demo OWNER) has no 2FA enabled, so a single credit at/above
    # admin_reauth_threshold (routes/admin.py's step-up check) would now be
    # blocked — chunk into sub-threshold pieces purely for test setup purposes.
    CHUNK = 900
    remaining = amount
    while remaining > 0:
        piece = min(CHUNK, remaining)
        credit(api, admin_token, user_id, piece, reason=reason)
        remaining -= piece


def get_wallet(api, token):
    r = api.get(f"{API}/wallet", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def make_order(api, client_token, budget=50, title_suffix="order"):
    r = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} {title_suffix}", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": budget, "photos": [], "fields": {},
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def propose_and_accept(api, client_token, worker_token, order_id, amount):
    p = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                 json={"amount": amount, "message": "", "eta": ""}, timeout=15)
    assert p.status_code == 200, p.text
    a = api.post(f"{API}/proposals/{p.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert a.status_code == 200, a.text
    return p.json()["id"]


def pay(api, client_token, order_id, password=None):
    body = {"method": "wallet"}
    if password:
        body["password"] = password
    return api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json=body, timeout=15)


def make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=50):
    # Always send the password: the shared client fixture accumulates real risk
    # signals across this file (cancellations, disputes), which can legitimately
    # push it into fraud.py's MEDIUM tier and require reauth — that's the risk
    # engine working correctly, not something these unrelated tests should trip on.
    credit(api, admin_token, client_id, budget + 50)
    order_id = make_order(api, client_token, budget, "paid")
    propose_and_accept(api, client_token, worker_token, order_id, budget)
    r = pay(api, client_token, order_id, password=TEST_PASSWORD)
    assert r.status_code == 200, r.text
    return order_id, r.json()


def add_bank_account(api, token, suffix, password=TEST_PASSWORD):
    r = api.post(f"{API}/bank-accounts", headers=auth(token), json={
        "holder_name": f"Test {suffix}", "document": "12345678900", "bank_code": "001",
        "agency": "0001", "account_number": f"{suffix}0000", "account_type": "checking", "password": password,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------- 1. full happy path ----------

def test_happy_path_end_to_end(api, client_token, worker_token, admin_token, client_id, worker_id):
    budget = 60
    credit(api, admin_token, client_id, budget + 50)
    order_id = make_order(api, client_token, budget, "happy")
    propose_and_accept(api, client_token, worker_token, order_id, budget)
    pay_r = pay(api, client_token, order_id)
    assert pay_r.status_code == 200, pay_r.text

    worker_before = get_wallet(api, worker_token)
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    req = api.post(f"{API}/orders/{order_id}/request-completion", headers=auth(worker_token), timeout=15)
    assert req.status_code == 200, req.text
    assert req.json()["status"] == "completion_requested"
    order_mid = api.get(f"{API}/orders/{order_id}", timeout=15).json()
    assert order_mid["status"] == "completion_requested"

    complete = api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15)
    assert complete.status_code == 200, complete.text
    worker_after = get_wallet(api, worker_token)
    assert worker_after["available"] > worker_before["available"]

    bank_id = add_bank_account(api, worker_token, "happy")
    wd = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token),
                  json={"amount": 20, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert wd.status_code == 200, wd.text


def test_request_completion_requires_worker_role_and_in_progress_state(api, client_token, worker_token, outsider_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=15)
    # not started yet — still "accepted", not "in_progress"
    r = api.post(f"{API}/orders/{order_id}/request-completion", headers=auth(worker_token), timeout=15)
    assert r.status_code == 400
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    r2 = api.post(f"{API}/orders/{order_id}/request-completion", headers=auth(outsider_token), timeout=15)
    assert r2.status_code == 403
    r3 = api.post(f"{API}/orders/{order_id}/request-completion", headers=auth(worker_token), timeout=15)
    assert r3.status_code == 200, r3.text


# ---------- 2. differentiated cancellations ----------

def test_cancel_before_payment_needs_no_refund(api, client_token, worker_token):
    order_id = make_order(api, client_token, 20, "cancel-before-pay")
    propose_and_accept(api, client_token, worker_token, order_id, 20)
    r = api.post(f"{API}/orders/{order_id}/cancel", headers=auth(client_token), timeout=15)
    assert r.status_code == 200, r.text


def test_cancel_after_payment_refunds_in_full(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=15)
    before = get_wallet(api, client_token)
    r = api.post(f"{API}/orders/{order_id}/cancel", headers=auth(client_token), timeout=15)
    assert r.status_code == 200, r.text
    after = get_wallet(api, client_token)
    assert round(after["available"] - before["available"], 2) == 15.0


def test_client_cannot_cancel_mid_execution_but_admin_can(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=15)
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    blocked = api.post(f"{API}/orders/{order_id}/cancel", headers=auth(client_token), timeout=15)
    assert blocked.status_code == 400
    before = get_wallet(api, client_token)
    admin_cancel = api.post(f"{API}/admin/orders/{order_id}/cancel", headers=auth(admin_token), timeout=15)
    assert admin_cancel.status_code == 200, admin_cancel.text
    after = get_wallet(api, client_token)
    assert round(after["available"] - before["available"], 2) == 15.0


def test_admin_cancel_race_only_one_wins(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=12)

    def attempt():
        return requests.post(f"{API}/admin/orders/{order_id}/cancel", headers=auth(admin_token), timeout=15)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, f"expected exactly one success, got {codes}"


# ---------- 3. disputes, both sides ----------

def test_dispute_locks_order_and_refund_resolution_pays_client(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=30)
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    d = api.post(f"{API}/disputes", headers=auth(client_token), json={
        "target_type": "service", "order_id": order_id, "reason": "Serviço não foi realizado", "description": "test",
    }, timeout=15)
    assert d.status_code == 200, d.text
    dispute_id = d.json()["id"]

    # locked — none of the normal transitions can run while disputed
    assert api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15).status_code == 400
    assert api.post(f"{API}/orders/{order_id}/cancel", headers=auth(client_token), timeout=15).status_code == 400
    assert api.get(f"{API}/orders/{order_id}", timeout=15).json()["status"] == "disputed"

    before = get_wallet(api, client_token)
    resolve = api.patch(f"{API}/admin/disputes/{dispute_id}", headers=auth(admin_token), json={
        "status": "RESOLVED", "resolution": "ok", "resolution_action": "refund_client",
    }, timeout=15)
    assert resolve.status_code == 200, resolve.text
    after = get_wallet(api, client_token)
    assert round(after["available"] - before["available"], 2) == 30.0
    assert api.get(f"{API}/orders/{order_id}", timeout=15).json()["status"] == "cancelled"


def test_dispute_release_to_worker_resolution_pays_worker(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=30)
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    d = api.post(f"{API}/disputes", headers=auth(worker_token), json={
        "target_type": "client", "order_id": order_id, "reason": "Cobrança incorreta", "description": "test",
    }, timeout=15)
    assert d.status_code == 200, d.text
    dispute_id = d.json()["id"]

    before = get_wallet(api, worker_token)
    resolve = api.patch(f"{API}/admin/disputes/{dispute_id}", headers=auth(admin_token), json={
        "status": "RESOLVED", "resolution": "ok", "resolution_action": "release_worker",
    }, timeout=15)
    assert resolve.status_code == 200, resolve.text
    after = get_wallet(api, worker_token)
    assert after["available"] > before["available"]
    assert api.get(f"{API}/orders/{order_id}", timeout=15).json()["status"] == "completed"


def test_dispute_rejected_reverts_order_to_prior_status(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=15)
    assert api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15).status_code == 200
    d = api.post(f"{API}/disputes", headers=auth(client_token), json={
        "target_type": "service", "order_id": order_id, "reason": "Outro", "description": "test",
    }, timeout=15)
    dispute_id = d.json()["id"]
    resolve = api.patch(f"{API}/admin/disputes/{dispute_id}", headers=auth(admin_token), json={
        "status": "REJECTED", "resolution": "sem evidencia",
    }, timeout=15)
    assert resolve.status_code == 200, resolve.text
    assert api.get(f"{API}/orders/{order_id}", timeout=15).json()["status"] == "in_progress"
    # order resumes normal life — client can still complete it directly
    assert api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15).status_code == 200


def test_non_admin_cannot_resolve_dispute(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=10)
    d = api.post(f"{API}/disputes", headers=auth(client_token), json={
        "target_type": "service", "order_id": order_id, "reason": "Outro", "description": "test",
    }, timeout=15)
    # Admin sessions are a separate identity system — a consumer token is 401 here,
    # not merely a 403 "admin without permission".
    r = api.patch(f"{API}/admin/disputes/{d.json()['id']}", headers=auth(client_token),
                  json={"status": "RESOLVED", "resolution_action": "refund_client"}, timeout=15)
    assert r.status_code == 401


# ---------- 4/5/6. duplicate payment / webhook / withdrawal ----------

def test_concurrent_payment_only_one_succeeds(api, client_token, worker_token, admin_token, client_id):
    credit(api, admin_token, client_id, 100)
    order_id = make_order(api, client_token, 40, "dup-pay")
    propose_and_accept(api, client_token, worker_token, order_id, 40)

    def attempt():
        return requests.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token),
                              json={"method": "wallet", "password": TEST_PASSWORD}, timeout=15)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, f"expected exactly one success, got {codes}"


def test_duplicate_webhook_does_not_double_process():
    if not WEBHOOK_SECRET:
        pytest.skip("ASAAS_WEBHOOK_SECRET not configured in this environment")
    # ASAAS doesn't sign the body — it echoes back a static access token on every
    # call, compared directly. See backend/routes/wallet.py's payment_webhook.
    payload = {"id": f"{TAG}-evt-1", "event": "PAYMENT_RECEIVED", "payment": {"id": "fake"}}
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "asaas-access-token": WEBHOOK_SECRET}
    r1 = requests.post(f"{API}/webhooks/payment-provider", data=body, headers=headers, timeout=15)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("duplicate") is not True
    r2 = requests.post(f"{API}/webhooks/payment-provider", data=body, headers=headers, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True


def test_webhook_rejects_bad_signature():
    if not WEBHOOK_SECRET:
        pytest.skip("ASAAS_WEBHOOK_SECRET not configured in this environment")
    payload = {"id": f"{TAG}-evt-bad-sig", "event": "PAYMENT_RECEIVED"}
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "asaas-access-token": "not-the-real-token"}
    r = requests.post(f"{API}/webhooks/payment-provider", data=body, headers=headers, timeout=15)
    assert r.status_code == 401


def test_withdrawal_idempotency_key_prevents_double_hold(api, admin_token, worker_token, worker_id):
    credit(api, admin_token, worker_id, 50, reason=f"{TAG} withdrawal-idem")
    bank_id = add_bank_account(api, worker_token, "idem")
    key = f"{TAG}-wd-key"
    before = get_wallet(api, worker_token)
    r1 = api.post(f"{API}/wallet/withdrawals", headers={**auth(worker_token), "Idempotency-Key": key},
                  json={"amount": 25, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert r1.status_code == 200, r1.text
    r2 = api.post(f"{API}/wallet/withdrawals", headers={**auth(worker_token), "Idempotency-Key": key},
                  json={"amount": 25, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
    after = get_wallet(api, worker_token)
    assert round(before["available"] - after["available"], 2) == 25.0  # held exactly once


def test_admin_withdrawal_approve_race_only_one_wins(api, admin_token, worker_token, worker_id):
    credit(api, admin_token, worker_id, 50, reason=f"{TAG} approve-race")
    bank_id = add_bank_account(api, worker_token, "race")
    wd = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token),
                  json={"amount": 25, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)
    assert wd.status_code == 200, wd.text
    wd_id = wd.json()["id"]

    def attempt():
        return requests.post(f"{API}/admin/withdrawals/{wd_id}/approve", headers=auth(admin_token), timeout=15)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, f"expected exactly one success, got {codes}"


# ---------- 7. tampering ----------

def test_pay_order_ignores_client_sent_amount_and_status(api, client_token, worker_token, admin_token, client_id):
    credit(api, admin_token, client_id, 100)
    order_id = make_order(api, client_token, 20, "tamper-amount")
    propose_and_accept(api, client_token, worker_token, order_id, 20)
    r = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token),
                 json={"method": "wallet", "amount": 999999, "status": "released", "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["gross_amount"] == 20.0


def test_update_order_cannot_inject_worker_id_or_status(api, client_token, worker_id):
    order_id = make_order(api, client_token, 20, "tamper-fields")
    r = api.patch(f"{API}/orders/{order_id}", headers=auth(client_token), json={
        "worker_id": worker_id, "status": "completed", "client_id": "someone-else",
    }, timeout=15)
    assert r.status_code == 200, r.text  # extra/unknown fields are silently dropped by the model
    check = api.get(f"{API}/orders/{order_id}", timeout=15).json()
    assert check["status"] == "published"
    assert check["worker_id"] is None


def test_admin_wallet_adjustment_idempotency_key_prevents_double_credit(api, admin_token, client_id):
    key = f"{TAG}-adjust-key"
    headers = {**auth(admin_token), "Content-Type": "application/json", "Idempotency-Key": key}
    body = json.dumps({"user_id": client_id, "amount": 7, "reason": f"{TAG} idem"})
    r1 = requests.post(f"{API}/admin/wallets/{client_id}/adjust", headers=headers, data=body, timeout=15)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{API}/admin/wallets/{client_id}/adjust", headers=headers, data=body, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]


# ---------- 8. cross-user access denial ----------

def test_outsider_cannot_view_others_payment(api, client_token, worker_token, outsider_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=10)
    r = api.get(f"{API}/orders/{order_id}/payment", headers=auth(outsider_token), timeout=15)
    assert r.status_code == 403


def test_outsider_cannot_read_others_chat(api, client_token, worker_token, outsider_token):
    order_id = make_order(api, client_token, 20, "chat-privacy")
    propose_and_accept(api, client_token, worker_token, order_id, 20)
    r = api.get(f"{API}/orders/{order_id}/messages", headers=auth(outsider_token), timeout=15)
    assert r.status_code == 403


def test_wallet_endpoint_ignores_foreign_user_id_query(api, outsider_token, client_id):
    mine = get_wallet(api, outsider_token)
    r = api.get(f"{API}/wallet?user_id={client_id}", headers=auth(outsider_token), timeout=15)
    assert r.status_code == 200
    assert r.json() == mine  # query param has no effect — always scoped to the JWT


# ---------- 9. chat external-payment detection ----------

def test_chat_external_payment_detection_escalates_and_restricts(api, client_token, worker_token, admin_token, client_id):
    credit(api, admin_token, client_id, 100)
    order_id = make_order(api, client_token, 20, "chat-fraud")
    propose_and_accept(api, client_token, worker_token, order_id, 20)
    text = "pague por fora, me chama no zap 11 98765-4321"

    m1 = api.post(f"{API}/orders/{order_id}/messages", headers=auth(client_token), json={"text": text}, timeout=15)
    assert m1.status_code == 200, m1.text
    assert m1.json().get("warning")

    for _ in range(5):
        r = api.post(f"{API}/orders/{order_id}/messages", headers=auth(client_token), json={"text": text}, timeout=15)
        assert r.status_code in (200, 429), r.text

    order_check = api.get(f"{API}/orders/{order_id}", timeout=15).json()
    assert order_check.get("external_payment_restricted") is True

    blocked = pay(api, client_token, order_id)
    assert blocked.status_code == 403, blocked.text


def test_clean_message_gets_no_warning(api, client_token, worker_token):
    order_id = make_order(api, client_token, 20, "chat-clean")
    propose_and_accept(api, client_token, worker_token, order_id, 20)
    m = api.post(f"{API}/orders/{order_id}/messages", headers=auth(client_token), json={"text": "Oi, tudo bem? Vou chegar às 15h."}, timeout=15)
    assert m.status_code == 200, m.text
    assert not m.json().get("warning")


# ---------- risk engine: MEDIUM reauth + CRITICAL block ----------

def test_large_payment_requires_password_reauth(api, worker_token, admin_token):
    risk_client_token, risk_client_id = _register(api, "risk_medium")
    budget = 1500  # >= R$1000 -> at least a "large_amount" signal
    credit_large(api, admin_token, risk_client_id, budget + 100)
    order_id = make_order(api, risk_client_token, budget, "risk-medium")
    propose_and_accept(api, risk_client_token, worker_token, order_id, budget)

    r = pay(api, risk_client_token, order_id)
    assert r.status_code == 401, r.text
    r2 = pay(api, risk_client_token, order_id, password=TEST_PASSWORD)
    assert r2.status_code == 200, r2.text


def test_critical_risk_payment_is_blocked_and_flagged(api, worker_token, admin_token):
    risk_client_token, risk_client_id = _register(api, "risk_critical")
    budget = 6000  # >= R$5000 -> "very_large_amount", combined with fresh account + a chat flag
    credit_large(api, admin_token, risk_client_id, budget + 100)
    order_id = make_order(api, risk_client_token, budget, "risk-critical")
    propose_and_accept(api, risk_client_token, worker_token, order_id, budget)
    api.post(f"{API}/orders/{order_id}/messages", headers=auth(risk_client_token), json={"text": "pague por fora"}, timeout=15)

    before = get_wallet(api, risk_client_token)
    r = pay(api, risk_client_token, order_id)
    assert r.status_code == 403, r.text
    after = get_wallet(api, risk_client_token)
    assert after["available"] == before["available"]

    flags = api.get(f"{API}/admin/risk-flags", headers=auth(admin_token), timeout=15).json()
    matching = [f for f in flags if f["user_id"] == risk_client_id and f["level"] == "CRITICAL"]
    assert matching, "expected a CRITICAL risk flag for this payment attempt"
    resolve = api.patch(f"{API}/admin/risk-flags/{matching[0]['id']}", headers=auth(admin_token), json={"status": "RESOLVED"}, timeout=15)
    assert resolve.status_code == 200, resolve.text


def test_non_admin_cannot_access_risk_flags(api, client_token):
    r = api.get(f"{API}/admin/risk-flags", headers=auth(client_token), timeout=15)
    assert r.status_code == 401


# ---------- 10. compromised account / audit trail ----------

def test_repeated_failed_logins_get_rate_limited():
    # The login rate limit is keyed by ip:email and checked before any user lookup,
    # so this doesn't need a real registered account — a nonexistent email exercises
    # the exact same limiter without spending any of the register budget.
    email = f"{TAG}_lockout@example.com"
    codes = []
    for _ in range(12):
        r = requests.post(f"{API}/auth/login", json={"identifier": email, "password": "wrong-password"}, timeout=15)
        codes.append(r.status_code)
    assert 429 in codes, f"expected a 429 after repeated failed logins, got {codes}"


def test_bank_account_changes_create_security_events(api, admin_token):
    token, user_id = _register(api, "secevt")
    add_bank_account(api, token, "secevt")
    events = api.get(f"{API}/admin/security-events?user_id={user_id}", headers=auth(admin_token), timeout=15).json()
    assert any(e["event"] == "bank_account_added" for e in events)


def test_login_creates_security_event(api, admin_token):
    email = f"{TAG}_login_evt@example.com"
    reg = api.post(f"{API}/auth/register", json={
        "name": "Login Event Test", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user"]["id"]
    login = api.post(f"{API}/auth/login", json={"identifier": email, "password": TEST_PASSWORD}, timeout=15)
    assert login.status_code == 200, login.text
    events = api.get(f"{API}/admin/security-events?user_id={user_id}", headers=auth(admin_token), timeout=15).json()
    assert any(e["event"] == "login" for e in events)


def test_non_admin_cannot_access_security_events(api, client_token):
    r = api.get(f"{API}/admin/security-events", headers=auth(client_token), timeout=15)
    assert r.status_code == 401


# ---------- 11. session revocation (token_version) ----------

def test_password_change_invalidates_old_token(api):
    token, user_id = _register(api, "revoke_pwd")
    me = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert me.status_code == 200, me.text

    changed = api.post(f"{API}/auth/change-password", headers=auth(token),
                        json={"current_password": TEST_PASSWORD, "new_password": "NewPass456!"}, timeout=15)
    assert changed.status_code == 200, changed.text

    stale = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert stale.status_code == 401, stale.text


def test_reset_password_invalidates_old_token(api):
    email = f"{TAG}_revoke_reset_{uuid.uuid4().hex[:8]}@example.com"
    reg = api.post(f"{API}/auth/register", json={
        "name": "Revoke Reset Test", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert reg.status_code == 200, reg.text
    old_token = reg.json()["token"]

    forgot = api.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)
    assert forgot.status_code == 200, forgot.text
    code = forgot.json().get("dev_code")
    assert code, "expected dev_code in response (EMAIL_DELIVERY_ENABLED not set in this env)"

    reset = api.post(f"{API}/auth/reset-password", json={"email": email, "code": code, "password": "NewPass789!"}, timeout=15)
    assert reset.status_code == 200, reset.text

    stale = api.get(f"{API}/auth/me", headers=auth(old_token), timeout=15)
    assert stale.status_code == 401, stale.text

    fresh_login = api.post(f"{API}/auth/login", json={"identifier": email, "password": "NewPass789!"}, timeout=15)
    assert fresh_login.status_code == 200, fresh_login.text
    new_me = api.get(f"{API}/auth/me", headers=auth(fresh_login.json()["token"]), timeout=15)
    assert new_me.status_code == 200, new_me.text


def test_admin_revoke_sessions_invalidates_token(api, admin_token):
    token, user_id = _register(api, "revoke_admin")
    me = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert me.status_code == 200, me.text

    revoked = api.post(f"{API}/admin/users/{user_id}/revoke-sessions", headers=auth(admin_token), timeout=15)
    assert revoked.status_code == 200, revoked.text

    stale = api.get(f"{API}/auth/me", headers=auth(token), timeout=15)
    assert stale.status_code == 401, stale.text


def test_non_admin_cannot_revoke_sessions(api, client_token, worker_id):
    r = api.post(f"{API}/admin/users/{worker_id}/revoke-sessions", headers=auth(client_token), timeout=15)
    assert r.status_code == 401
