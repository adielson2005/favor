"""Support/feedback ticket flow — user creates, only sees their own, admin (SUPPORT)
replies, user sees the reply and can re-open a resolved ticket by replying again.
MAINTENANCE-specific BUG-only scoping is covered in test_admin_panel.py alongside
the rest of the RBAC boundary tests.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TAG = f"TICKET_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "TestPass123!"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(api, tag):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    phone = "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": phone, "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": "nb-19", "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]["id"]


@pytest.fixture(scope="module")
def user_a(api):
    return _register(api, f"{TAG}_a")


@pytest.fixture(scope="module")
def user_b(api):
    return _register(api, f"{TAG}_b")


def test_create_ticket_requires_valid_category(api, user_a):
    token, _uid = user_a
    r = api.post(f"{API}/tickets", headers=auth(token), json={"category": "NOT_REAL", "subject": "assunto válido", "description": "y"}, timeout=15)
    assert r.status_code == 400, r.text


def test_create_and_list_own_ticket(api, user_a):
    token, _uid = user_a
    create = api.post(f"{API}/tickets", headers=auth(token),
                       json={"category": "RECLAMACAO", "subject": f"{TAG} problema", "description": "detalhes do problema"}, timeout=15)
    assert create.status_code == 200, create.text
    ticket = create.json()
    assert ticket["status"] == "OPEN"
    assert len(ticket["messages"]) == 1

    listed = api.get(f"{API}/tickets", headers=auth(token), timeout=15).json()
    assert any(t["id"] == ticket["id"] for t in listed)


def test_user_cannot_see_or_reply_to_someone_elses_ticket(api, user_a, user_b):
    token_a, _ = user_a
    token_b, _ = user_b
    create = api.post(f"{API}/tickets", headers=auth(token_a),
                       json={"category": "OUTRO", "subject": f"{TAG} privado", "description": "só eu devo ver isso"}, timeout=15)
    ticket_id = create.json()["id"]

    get_as_b = api.get(f"{API}/tickets/{ticket_id}", headers=auth(token_b), timeout=15)
    assert get_as_b.status_code == 404, get_as_b.text

    reply_as_b = api.post(f"{API}/tickets/{ticket_id}/messages", headers=auth(token_b), json={"text": "invasão"}, timeout=15)
    assert reply_as_b.status_code == 404, reply_as_b.text

    b_list = api.get(f"{API}/tickets", headers=auth(token_b), timeout=15).json()
    assert not any(t["id"] == ticket_id for t in b_list)


def test_admin_reply_notifies_user_and_user_can_reopen(api, user_a, admin_token):
    token, _uid = user_a
    create = api.post(f"{API}/tickets", headers=auth(token),
                       json={"category": "PAGAMENTO", "subject": f"{TAG} pagamento", "description": "dúvida sobre pagamento"}, timeout=15)
    ticket_id = create.json()["id"]

    reply = api.post(f"{API}/admin/tickets/{ticket_id}/messages", headers=auth(admin_token), json={"text": "Vamos verificar."}, timeout=15)
    assert reply.status_code == 200, reply.text

    after_reply = api.get(f"{API}/tickets/{ticket_id}", headers=auth(token), timeout=15).json()
    assert after_reply["status"] == "WAITING_USER"
    assert any(m["text"] == "Vamos verificar." and m["author_type"] == "admin" for m in after_reply["messages"])

    resolve = api.patch(f"{API}/admin/tickets/{ticket_id}", headers=auth(admin_token), json={"status": "RESOLVED"}, timeout=15)
    assert resolve.status_code == 200, resolve.text

    # User replying to a resolved ticket re-opens it instead of leaving it stuck.
    user_reply = api.post(f"{API}/tickets/{ticket_id}/messages", headers=auth(token), json={"text": "ainda não resolveu"}, timeout=15)
    assert user_reply.status_code == 200, user_reply.text
    reopened = api.get(f"{API}/tickets/{ticket_id}", headers=auth(token), timeout=15).json()
    assert reopened["status"] == "OPEN"


def test_admin_transfer_to_maintenance_sets_bug_category(api, user_a, admin_token):
    token, _uid = user_a
    create = api.post(f"{API}/tickets", headers=auth(token),
                       json={"category": "OUTRO", "subject": f"{TAG} transferir", "description": "algo técnico estranho"}, timeout=15)
    ticket_id = create.json()["id"]

    transfer = api.patch(f"{API}/admin/tickets/{ticket_id}", headers=auth(admin_token), json={"transfer_to_maintenance": True}, timeout=15)
    assert transfer.status_code == 200, transfer.text

    ticket = api.get(f"{API}/admin/tickets/{ticket_id}", headers=auth(admin_token), timeout=15).json()
    assert ticket["category"] == "BUG"
    assert ticket["assigned_to"] is None


def test_anonymous_cannot_create_or_list_tickets(api):
    r = api.post(f"{API}/tickets", json={"category": "BUG", "subject": "x", "description": "y"}, timeout=15)
    assert r.status_code == 401, r.text
    r2 = api.get(f"{API}/tickets", timeout=15)
    assert r2.status_code == 401, r2.text
