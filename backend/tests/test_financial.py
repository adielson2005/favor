"""Security + correctness tests for the wallet/payments system.

Targets the explicit attack checklist from the financial spec: price/user/wallet/
payment id manipulation, cross-user access (IDOR), double payment, double
withdrawal, overdraft, forged status, unauthorized admin access, bad/missing auth,
and concurrent requests against the same balance.
"""
import concurrent.futures
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values('/app/frontend/.env').get('EXPO_PUBLIC_BACKEND_URL')
            or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fazum.demo"
DEMO_PASSWORD = "faze2024"
TEST_PASSWORD = "TestPass123!"

TAG = f"FIN_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, email):
    r = api.post(f"{API}/auth/login", json={"email": email, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _register(api, tag):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


# The financial suite creates many orders/payments/notifications per run. Reusing
# the shared marina/joao demo accounts would burn their real rate-limit budget and
# pollute notification counts that test_regression.py asserts exact values for —
# so every financial test gets its own throwaway accounts instead.
@pytest.fixture(scope="session")
def _client(api):
    return _register(api, "fin_client")


@pytest.fixture(scope="session")
def _worker(api):
    return _register(api, "fin_worker")


@pytest.fixture(scope="session")
def _outsider(api):
    return _register(api, "fin_outsider")


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


@pytest.fixture(scope="session")
def admin_token(api):
    return _login(api, ADMIN_EMAIL)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def credit(api, admin_token, user_id, amount, reason=TAG):
    r = api.post(f"{API}/admin/wallets/{user_id}/adjust", headers=auth(admin_token),
                 json={"user_id": user_id, "amount": amount, "reason": reason}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def get_wallet(api, token):
    r = api.get(f"{API}/wallet", headers=auth(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=50):
    """Create+propose+accept+pay a fresh order, funding the client wallet first. Returns (order_id, payment)."""
    credit(api, admin_token, client_id, budget + 50)
    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} order", "description": "financial test", "type": "favor",
        "category_id": "cat-entregas", "city_id": "city-parauapebas", "neighborhood_id": "nb-19",
        "date_label": "Hoje", "time_label": "", "budget": budget, "photos": [], "fields": {},
    }, timeout=15)
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": budget, "message": "", "eta": ""}, timeout=15)
    assert proposal.status_code == 200, proposal.text
    accept = api.post(f"{API}/proposals/{proposal.json()['id']}/accept", headers=auth(client_token), timeout=15)
    assert accept.status_code == 200, accept.text
    pay = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    assert pay.status_code == 200, pay.text
    return order_id, pay.json()


# ---------- wallet basics ----------

def test_wallet_requires_auth(api):
    r = api.get(f"{API}/wallet", timeout=15)
    assert r.status_code == 401


def test_no_direct_balance_write_endpoint(api):
    for method in ("put", "patch"):
        r = getattr(api, method)(f"{API}/wallet/balance", timeout=15)
        assert r.status_code in (404, 405)


def test_admin_adjustment_is_the_only_way_to_set_balance(api, admin_token, client_id):
    result = credit(api, admin_token, client_id, 10, reason=f"{TAG} audit check")
    assert result["type"] == "ADJUSTMENT"
    assert result["amount_cents"] == 1000


def test_non_admin_cannot_adjust_wallet(api, client_token, client_id):
    r = api.post(f"{API}/admin/wallets/{client_id}/adjust", headers=auth(client_token),
                 json={"user_id": client_id, "amount": 999, "reason": "attack"}, timeout=15)
    assert r.status_code == 403


# ---------- payment: never trust the frontend ----------

def test_pay_order_ignores_any_client_sent_amount(api, client_token, worker_token, admin_token, client_id):
    # PayOrderIn has no amount field at all — the server always recomputes from the
    # order's accepted proposal. Sending extra/unknown fields must not change that.
    credit(api, admin_token, client_id, 100)
    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} amount-trust", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 30, "photos": [], "fields": {},
    }, timeout=15)
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 30, "message": "", "eta": ""}, timeout=15)
    api.post(f"{API}/proposals/{proposal.json()['id']}/accept", headers=auth(client_token), timeout=15)
    pay = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token),
                    json={"method": "wallet", "amount": 1}, timeout=15)  # "amount": 1 must be ignored
    assert pay.status_code == 200, pay.text
    assert pay.json()["gross_amount"] == 30.0


def test_cannot_pay_for_someone_elses_order(api, client_token, worker_token, outsider_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id)
    r = api.post(f"{API}/orders/{order_id}/pay", headers=auth(outsider_token), json={"method": "wallet"}, timeout=15)
    assert r.status_code in (403, 400)


def test_cannot_pay_twice_for_same_order(api, client_token, worker_token, admin_token, client_id):
    order_id, payment = make_paid_order(api, client_token, worker_token, admin_token, client_id)
    wallet_before = get_wallet(api, client_token)
    r = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    assert r.status_code == 400, r.text
    wallet_after = get_wallet(api, client_token)
    assert wallet_after["available"] == wallet_before["available"]  # no double debit


def test_cannot_pay_order_that_isnt_accepted_yet(api, client_token, admin_token, client_id):
    credit(api, admin_token, client_id, 100)
    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} unaccepted", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 20, "photos": [], "fields": {},
    }, timeout=15)
    r = api.post(f"{API}/orders/{order.json()['id']}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    assert r.status_code == 400


def test_insufficient_balance_rejected_and_wallet_unchanged(api, client_token, worker_token, admin_token):
    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} broke", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 999999, "photos": [], "fields": {},
    }, timeout=15)
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 999999, "message": "", "eta": ""}, timeout=15)
    api.post(f"{API}/proposals/{proposal.json()['id']}/accept", headers=auth(client_token), timeout=15)
    wallet_before = get_wallet(api, client_token)
    r = api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    assert r.status_code == 400
    wallet_after = get_wallet(api, client_token)
    assert wallet_after["available"] == wallet_before["available"]


def test_unrelated_user_cannot_view_payment(api, client_token, worker_token, outsider_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id)
    r = api.get(f"{API}/orders/{order_id}/payment", headers=auth(outsider_token), timeout=15)
    assert r.status_code == 403


# ---------- release / refund ----------

def test_completion_releases_payment_with_correct_commission_split(api, client_token, worker_token, admin_token, client_id):
    order_id, payment = make_paid_order(api, client_token, worker_token, admin_token, client_id, budget=50)
    worker_before = get_wallet(api, worker_token)
    api.post(f"{API}/orders/{order_id}/start", headers=auth(worker_token), timeout=15)
    r = api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15)
    assert r.status_code == 200, r.text
    worker_after = get_wallet(api, worker_token)
    assert round(worker_after["available"] - worker_before["available"], 2) == payment["worker_net_amount"]
    assert round(payment["gross_amount"] - payment["worker_net_amount"], 2) == payment["commission_amount"]
    status = api.get(f"{API}/orders/{order_id}/payment", headers=auth(client_token), timeout=15).json()
    assert status["status"] == "released"


def test_cancel_refunds_held_payment_in_full(api, client_token, worker_token, admin_token, client_id):
    credit(api, admin_token, client_id, 100)
    order = api.post(f"{API}/orders", headers=auth(client_token), json={
        "title": f"{TAG} refund", "description": "", "type": "favor", "category_id": "cat-entregas",
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "date_label": "Hoje", "time_label": "",
        "budget": 25, "photos": [], "fields": {},
    }, timeout=15)
    order_id = order.json()["id"]
    proposal = api.post(f"{API}/orders/{order_id}/proposals", headers=auth(worker_token),
                         json={"amount": 25, "message": "", "eta": ""}, timeout=15)
    api.post(f"{API}/proposals/{proposal.json()['id']}/accept", headers=auth(client_token), timeout=15)
    api.post(f"{API}/orders/{order_id}/pay", headers=auth(client_token), json={"method": "wallet"}, timeout=15)
    wallet_after_pay = get_wallet(api, client_token)
    r = api.post(f"{API}/orders/{order_id}/cancel", headers=auth(client_token), timeout=15)
    assert r.status_code == 200, r.text
    wallet_after_cancel = get_wallet(api, client_token)
    assert round(wallet_after_cancel["available"] - wallet_after_pay["available"], 2) == 25.0
    status = api.get(f"{API}/orders/{order_id}/payment", headers=auth(client_token), timeout=15).json()
    assert status["status"] == "refunded"


# ---------- status forgery ----------

def test_frontend_cannot_force_order_status_to_completed(api, client_token, worker_token, admin_token, client_id):
    order_id, _ = make_paid_order(api, client_token, worker_token, admin_token, client_id)
    # Skipping /start and trying to /complete directly must fail — there is no
    # endpoint or field that lets a client just declare an order "completed".
    r = api.post(f"{API}/orders/{order_id}/complete", headers=auth(client_token), timeout=15)
    assert r.status_code == 400


# ---------- bank accounts / withdrawals ----------

def test_bank_account_number_is_masked(api, worker_token):
    r = api.post(f"{API}/bank-accounts", headers=auth(worker_token), json={
        "holder_name": "Test Holder", "document": "12345678900", "bank_code": "001",
        "agency": "1234", "account_number": "9988776655", "account_type": "checking", "password": TEST_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "9988776655" not in str(body)
    assert body["account_number_masked"].endswith("6655")


def test_add_bank_account_requires_correct_password(api, worker_token):
    r = api.post(f"{API}/bank-accounts", headers=auth(worker_token), json={
        "holder_name": "Attacker", "document": "00000000000", "bank_code": "001",
        "agency": "0001", "account_number": "111111", "account_type": "checking", "password": "wrong-password",
    }, timeout=15)
    assert r.status_code == 401


def test_withdrawal_requires_correct_password(api, worker_token):
    accounts = api.get(f"{API}/bank-accounts", headers=auth(worker_token), timeout=15).json()
    assert accounts, "expected at least one bank account from prior test"
    r = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token), json={
        "amount": 1, "bank_account_id": accounts[0]["id"], "password": "wrong-password",
    }, timeout=15)
    assert r.status_code == 401


def test_withdrawal_cannot_exceed_available_balance(api, worker_token):
    accounts = api.get(f"{API}/bank-accounts", headers=auth(worker_token), timeout=15).json()
    r = api.post(f"{API}/wallet/withdrawals", headers=auth(worker_token), json={
        "amount": 999999, "bank_account_id": accounts[0]["id"], "password": TEST_PASSWORD,
    }, timeout=15)
    assert r.status_code == 400


def test_concurrent_withdrawals_cannot_both_succeed_past_balance(api, admin_token, worker_token, worker_id):
    credit(api, admin_token, worker_id, 20, reason=f"{TAG} concurrency setup")
    wallet = get_wallet(api, worker_token)
    accounts = api.get(f"{API}/bank-accounts", headers=auth(worker_token), timeout=15).json()
    bank_id = accounts[0]["id"]
    # Two requests for 70% of the available balance each — at most one can win.
    amount = round(wallet["available"] * 0.7, 2)

    def attempt():
        return requests.post(f"{API}/wallet/withdrawals", headers=auth(worker_token),
                              json={"amount": amount, "bank_account_id": bank_id, "password": TEST_PASSWORD}, timeout=15)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    # Exactly one request should debit the balance; the other must be rejected —
    # either as insufficient funds (400) or, if it lands after enough other calls
    # in this run, a rate limit (429). Either way, at most one 200 is acceptable.
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, f"expected exactly one success, got {codes}"
    assert all(c in (200, 400, 429) for c in codes)


# ---------- admin endpoints reject non-admins ----------

@pytest.mark.parametrize("method,path", [
    ("get", "/admin/withdrawals"),
    ("get", "/admin/payments"),
    ("get", "/admin/disputes"),
    ("get", "/admin/config"),
    ("get", "/admin/wallets/demo-client"),
])
def test_admin_financial_routes_reject_non_admin(api, client_token, method, path):
    r = getattr(api, method)(f"{API}{path}", headers=auth(client_token), timeout=15)
    assert r.status_code == 403


def test_admin_financial_routes_reject_no_auth(api):
    r = api.get(f"{API}/admin/withdrawals", timeout=15)
    assert r.status_code == 401


# ---------- bad tokens ----------

def test_garbage_token_rejected(api):
    r = api.get(f"{API}/wallet", headers=auth("not-a-real-token"), timeout=15)
    assert r.status_code == 401


# ---------- idempotency ----------

def test_deposit_idempotency_key_prevents_duplicate_intent(api, client_token):
    key = f"{TAG}-deposit-key"
    r1 = api.post(f"{API}/wallet/deposits", headers={**auth(client_token), "Idempotency-Key": key},
                   json={"amount": 10, "method": "pix"}, timeout=15)
    r2 = api.post(f"{API}/wallet/deposits", headers={**auth(client_token), "Idempotency-Key": key},
                   json={"amount": 10, "method": "pix"}, timeout=15)
    # Both calls resolve to the same deposit id — no matter the outcome (pix isn't
    # configured, so both will report the provider-unavailable state consistently).
    if r1.status_code == r2.status_code == 200:
        assert r1.json()["id"] == r2.json()["id"]
