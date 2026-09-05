"""Tests for the real ASAAS integration (backend/asaas_customers.py,
AsaasProvider.create_pix_charge in backend/payments.py) — hits the REAL ASAAS
sandbox API, not a mock, the same way test_geo_catalog_postgres.py hits a real
Postgres instead of mocking SQLAlchemy. Only runs against the isolated
environment (backend/.env.isolated, port 8001), and only when the configured
key has the aact_hmlg_ (sandbox) prefix — this is the one safety net standing
between this file and accidentally firing at ASAAS production, so it re-checks
the prefix itself instead of trusting .env.isolated was set correctly.

Uses ASAAS's own documented fictitious sandbox CPFs (99991111140 etc.) — never
a real CPF, and never a value invented by this test suite.
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

ISOLATED_API = "http://localhost:8001/api"

_isolated_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env.isolated"))
_provider = _isolated_env.get("PAYMENT_PROVIDER") or os.environ.get("PAYMENT_PROVIDER", "")
_api_key = _isolated_env.get("ASAAS_API_KEY") or os.environ.get("ASAAS_API_KEY", "")
_sandbox_configured = _provider == "asaas" and _api_key.startswith("$aact_hmlg_")

try:
    _reachable = requests.get(f"{ISOLATED_API}/feature-flags", timeout=3).status_code == 200
except requests.exceptions.RequestException:
    _reachable = False

pytestmark = pytest.mark.skipif(
    not (_sandbox_configured and _reachable),
    reason="Ambiente isolado (porta 8001) não está no ar ou PAYMENT_PROVIDER/ASAAS_API_KEY não apontam para o sandbox ASAAS",
)

TEST_PASSWORD = "TestPass123!"
TAG = f"ASAASLIVE_{uuid.uuid4().hex[:6]}"

# Documented by ASAAS itself for sandbox testing — never a real person's CPF.
FICTITIOUS_CPFS = ["99991111140", "99992222263", "99993333387", "99994444409"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _random_phone():
    return "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"


def _register_and_login():
    email = f"{TAG}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{ISOLATED_API}/auth/register", json={
        "name": f"Test {TAG}", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_first_deposit_without_cpf_asks_for_document():
    token = _register_and_login()
    r = requests.post(f"{ISOLATED_API}/wallet/deposits", json={"amount": 20.0, "method": "pix"},
                       headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex}, timeout=20)
    assert r.status_code == 400, r.text
    assert "cpf" in r.json()["detail"].lower()


def test_deposit_with_cpf_creates_real_pix_charge_with_qr_code():
    token = _register_and_login()
    r = requests.post(
        f"{ISOLATED_API}/wallet/deposits",
        json={"amount": 20.0, "method": "pix", "document": FICTITIOUS_CPFS[0]},
        headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex}, timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PROCESSING"
    assert body["qr_code_image"]
    assert body["qr_code_payload"]


def test_second_deposit_reuses_asaas_customer_without_asking_for_cpf_again():
    token = _register_and_login()
    r1 = requests.post(
        f"{ISOLATED_API}/wallet/deposits",
        json={"amount": 15.0, "method": "pix", "document": FICTITIOUS_CPFS[1]},
        headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex}, timeout=20,
    )
    assert r1.status_code == 200, r1.text

    r2 = requests.post(
        f"{ISOLATED_API}/wallet/deposits",
        json={"amount": 25.0, "method": "pix"},
        headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex}, timeout=20,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["qr_code_payload"]


def test_invalid_cpf_returns_clear_error_not_a_crash():
    token = _register_and_login()
    r = requests.post(
        f"{ISOLATED_API}/wallet/deposits",
        json={"amount": 20.0, "method": "pix", "document": "11111111111"},
        headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex}, timeout=20,
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]
