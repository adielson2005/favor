"""fazum backend regression tests (iteration 6 — real auth).

Covers bootstrap, geo/catalog, orders (filters + CRUD), proposals lifecycle,
chat, favorites, reports, notifications, and admin endpoints (positive + 401/403),
all driven through real login (email/password -> Bearer token) instead of
trusting client-supplied ids.
"""
import os
import uuid
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values('/app/frontend/.env').get('EXPO_PUBLIC_BACKEND_URL')
            or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')

CLIENT_ID = "demo-client"
WORKER_ID = "demo-worker"
ADMIN_ID = "demo-admin"
CLIENT_EMAIL = "marina@fazum.demo"
WORKER_EMAIL = "joao@fazum.demo"
ADMIN_EMAIL = "admin@fazum.demo"
DEMO_PASSWORD = "faze2024"

TAG = f"TEST_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, email):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def client_token(api):
    return _login(api, CLIENT_EMAIL)


@pytest.fixture(scope="session")
def worker_token(api):
    return _login(api, WORKER_EMAIL)


@pytest.fixture(scope="session")
def admin_token(api):
    return _login(api, ADMIN_EMAIL)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- auth ----------

def test_login_wrong_password_rejected(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": CLIENT_EMAIL, "password": "wrong-password"}, timeout=10)
    assert r.status_code == 401


def test_register_and_me(api):
    email = f"{TAG.lower()}@fazum.demo"
    r = api.post(f"{BASE_URL}/api/auth/register", json={
        "name": "Teste Regressão", "email": email, "password": "senha1234", "city_id": "city-parauapebas",
    }, timeout=10)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    me = api.get(f"{BASE_URL}/api/auth/me", headers=auth(token), timeout=10)
    assert me.status_code == 200
    body = me.json()
    assert body["name"] == "Teste Regressão"
    assert "email" not in body  # public_user never leaks email


def test_me_requires_token(api):
    r = api.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert r.status_code == 401


# ---------- bootstrap / geo / categories ----------

def test_bootstrap(api):
    r = api.get(f"{BASE_URL}/api/bootstrap", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert len(d["users"]) >= 3
    assert len(d["categories"]) >= 5
    assert any(c["name"] == "Casa" for c in d["categories"])
    assert d["categories"][0].get("subcategories") is not None
    assert len(d["neighborhoods"]) >= 40
    assert any(c["id"] == "city-parauapebas" for c in d["cities"])


def test_geo_states_cities_neighborhoods(api):
    st = api.get(f"{BASE_URL}/api/geo/states", timeout=10).json()
    assert any(s["uf"] == "PA" for s in st)
    ct = api.get(f"{BASE_URL}/api/geo/cities", params={"state_id": "st-pa"}, timeout=10).json()
    assert any(c["id"] == "city-parauapebas" for c in ct)
    nb = api.get(f"{BASE_URL}/api/geo/neighborhoods", params={"city_id": "city-parauapebas"}, timeout=10).json()
    assert len(nb) >= 40


def test_categories(api):
    cats = api.get(f"{BASE_URL}/api/categories", timeout=10).json()
    assert len(cats) >= 5
    casa = next(c for c in cats if c["name"] == "Casa")
    assert any(s["name"] == "Montagem de móveis" for s in casa["subcategories"])


# ---------- orders filters ----------

def test_orders_default_returns_published(api):
    orders = api.get(f"{BASE_URL}/api/orders", timeout=15).json()
    assert len(orders) >= 5
    assert all(o["status"] == "published" for o in orders)
    assert orders[0].get("category", {}).get("name")


def test_orders_filter_by_category(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"category_id": "cat-pets"}, timeout=10).json()
    assert orders and all(o["category"]["id"] == "cat-pets" for o in orders)


def test_orders_filter_by_type(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"type": "servico"}, timeout=10).json()
    assert orders and all(o["type"] == "servico" for o in orders)


def test_orders_search_token(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"q": "guarda roupa"}, timeout=10).json()
    assert any("guarda" in o["title"].lower() for o in orders)


def test_orders_max_budget(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"max_budget": 30}, timeout=10).json()
    assert all(o["budget"] <= 30 for o in orders)


def test_orders_my_activity_requires_auth(api):
    r = api.get(f"{BASE_URL}/api/orders", params={"client_id": CLIENT_ID}, timeout=10)
    assert r.status_code == 401


def test_orders_client_all_statuses(api, client_token):
    orders = api.get(f"{BASE_URL}/api/orders", params={"client_id": CLIENT_ID}, headers=auth(client_token), timeout=10).json()
    assert all(o["client_id"] == CLIENT_ID for o in orders)


# ---------- order lifecycle ----------

@pytest.fixture(scope="session")
def created_order(api, client_token):
    payload = {
        "title": f"{TAG} pedido regressao",
        "description": "Automated regression order",
        "type": "favor",
        "category_id": "cat-entregas",
        "subcategory_id": "cat-entregas-s0",
        "city_id": "city-parauapebas",
        "neighborhood_id": "nb-1",
        "date_label": "Hoje",
        "time_label": "tarde",
        "budget": 42,
    }
    r = api.post(f"{BASE_URL}/api/orders", json=payload, headers=auth(client_token), timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "published"
    assert d["client_id"] == CLIENT_ID
    assert d["category"]["id"] == "cat-entregas"
    assert d["neighborhood"]  # enrichment
    return d


def test_create_order_requires_auth(api):
    r = api.post(f"{BASE_URL}/api/orders", json={
        "title": "no auth", "category_id": "cat-entregas", "city_id": "city-parauapebas",
    }, timeout=10)
    assert r.status_code == 401


def test_get_order_enriched(api, created_order):
    r = api.get(f"{BASE_URL}/api/orders/{created_order['id']}", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == created_order["id"]
    assert d["category"]["name"] == "Entregas"
    assert d["client"]["id"] == CLIENT_ID
    assert "proposals_count" in d


# ---------- proposals ----------

def test_proposal_owner_cannot_propose(api, created_order, client_token):
    r = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals",
                 json={"amount": 50, "message": "x"}, headers=auth(client_token), timeout=10)
    assert r.status_code == 400


def test_proposal_create_then_duplicate_rejected(api, created_order, worker_token):
    body = {"amount": 55, "message": f"{TAG} first", "eta": "Hoje"}
    r1 = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals", json=body, headers=auth(worker_token), timeout=10)
    assert r1.status_code == 200, r1.text
    prop = r1.json()
    assert prop["status"] == "pending"
    assert prop["worker_id"] == WORKER_ID
    r2 = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals", json=body, headers=auth(worker_token), timeout=10)
    assert r2.status_code == 400
    pytest.proposal_id = prop["id"]


def test_accept_proposal_only_owner(api, created_order, client_token, worker_token):
    # wrong user (the worker who made the proposal, not the order owner)
    r = api.post(f"{BASE_URL}/api/proposals/{pytest.proposal_id}/accept", headers=auth(worker_token), timeout=10)
    assert r.status_code == 403
    # correct owner
    r2 = api.post(f"{BASE_URL}/api/proposals/{pytest.proposal_id}/accept", headers=auth(client_token), timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "accepted"
    order = api.get(f"{BASE_URL}/api/orders/{created_order['id']}", timeout=10).json()
    assert order["status"] == "accepted"
    assert order["worker_id"] == WORKER_ID


def test_start_and_complete_permissions(api, created_order, client_token, worker_token):
    # start by worker OK
    r = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/start", headers=auth(worker_token), timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    # complete by worker forbidden
    rf = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/complete", headers=auth(worker_token), timeout=10)
    assert rf.status_code == 403
    # complete by client OK
    rc = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/complete", headers=auth(client_token), timeout=10)
    assert rc.status_code == 200 and rc.json()["status"] == "completed"


def test_reviews_mutual_and_duplicate_blocked(api, created_order, client_token, worker_token):
    # client -> worker
    r1 = api.post(f"{BASE_URL}/api/reviews",
                  json={"order_id": created_order["id"], "to_id": WORKER_ID, "stars": 5, "comment": f"{TAG} great"},
                  headers=auth(client_token), timeout=10)
    assert r1.status_code == 200
    # duplicate blocked
    r_dup = api.post(f"{BASE_URL}/api/reviews",
                     json={"order_id": created_order["id"], "to_id": WORKER_ID, "stars": 4},
                     headers=auth(client_token), timeout=10)
    assert r_dup.status_code == 400
    # worker -> client OK (mutual)
    r2 = api.post(f"{BASE_URL}/api/reviews",
                  json={"order_id": created_order["id"], "to_id": CLIENT_ID, "stars": 5},
                  headers=auth(worker_token), timeout=10)
    assert r2.status_code == 200


# ---------- chat ----------

def test_chat_only_participants(api, created_order, client_token, admin_token):
    # a logged-in stranger (admin account, not a participant) can't send or read
    r_bad = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/messages",
                     json={"text": f"{TAG} sneak"}, headers=auth(admin_token), timeout=10)
    assert r_bad.status_code == 403
    r_bad_read = api.get(f"{BASE_URL}/api/orders/{created_order['id']}/messages", headers=auth(admin_token), timeout=10)
    assert r_bad_read.status_code == 403
    r_ok = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/messages",
                    json={"text": f"{TAG} hello"}, headers=auth(client_token), timeout=10)
    assert r_ok.status_code == 200
    msgs = api.get(f"{BASE_URL}/api/orders/{created_order['id']}/messages", headers=auth(client_token), timeout=10).json()
    assert any(m["text"] == f"{TAG} hello" for m in msgs)


def test_conversations_list(api, client_token):
    convs = api.get(f"{BASE_URL}/api/conversations", headers=auth(client_token), timeout=10).json()
    assert isinstance(convs, list)
    assert convs and "order" in convs[0] and "other" in convs[0]


# ---------- favorites / reports / notifications ----------

def test_favorites_toggle_and_list(api, created_order, worker_token):
    r1 = api.post(f"{BASE_URL}/api/favorites/toggle", json={"order_id": created_order["id"]}, headers=auth(worker_token), timeout=10).json()
    assert r1["favorited"] is True
    fav = api.get(f"{BASE_URL}/api/favorites", headers=auth(worker_token), timeout=10).json()
    assert created_order["id"] in fav["order_ids"]
    r2 = api.post(f"{BASE_URL}/api/favorites/toggle", json={"order_id": created_order["id"]}, headers=auth(worker_token), timeout=10).json()
    assert r2["favorited"] is False


def test_report_create(api, created_order, client_token):
    r = api.post(f"{BASE_URL}/api/reports", json={
        "target_type": "order", "target_id": created_order["id"], "reason": "spam",
        "details": f"{TAG} regression report"}, headers=auth(client_token), timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "open"
    pytest.report_id = r.json()["id"]


def test_notifications_flow(api, worker_token):
    d = api.get(f"{BASE_URL}/api/notifications", headers=auth(worker_token), timeout=10).json()
    assert "items" in d and "unread" in d
    api.post(f"{BASE_URL}/api/notifications/read", headers=auth(worker_token), timeout=10)
    d2 = api.get(f"{BASE_URL}/api/notifications", headers=auth(worker_token), timeout=10).json()
    assert d2["unread"] == 0


# ---------- admin ----------

def test_admin_requires_admin_token(api, client_token):
    r = api.get(f"{BASE_URL}/api/admin/overview", headers=auth(client_token), timeout=10)
    assert r.status_code == 403


def test_admin_requires_any_token(api):
    r = api.get(f"{BASE_URL}/api/admin/overview", timeout=10)
    assert r.status_code == 401


def test_admin_overview(api, admin_token):
    r = api.get(f"{BASE_URL}/api/admin/overview", headers=auth(admin_token), timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["users"] >= 4 and d["orders"] >= 5


def test_admin_categories_toggle_and_subcategory_add(api, admin_token):
    cats = api.get(f"{BASE_URL}/api/admin/categories", headers=auth(admin_token), timeout=10).json()
    target = cats[-1]
    sub = api.post(f"{BASE_URL}/api/admin/subcategories",
                   json={"category_id": target["id"], "name": f"{TAG}-sub", "active": True}, headers=auth(admin_token), timeout=10)
    assert sub.status_code == 200
    r_off = api.patch(f"{BASE_URL}/api/admin/categories/{target['id']}",
                      json={"active": False}, headers=auth(admin_token), timeout=10)
    assert r_off.status_code == 200
    r_on = api.patch(f"{BASE_URL}/api/admin/categories/{target['id']}",
                     json={"active": True}, headers=auth(admin_token), timeout=10)
    assert r_on.status_code == 200


def test_admin_geo_toggle(api, admin_token):
    r = api.patch(f"{BASE_URL}/api/admin/geo/cities/city-canaa",
                  json={"active": True}, headers=auth(admin_token), timeout=10)
    assert r.status_code == 200
    r2 = api.patch(f"{BASE_URL}/api/admin/geo/cities/city-canaa",
                   json={"active": False}, headers=auth(admin_token), timeout=10)
    assert r2.status_code == 200


def test_admin_reports_resolve(api, admin_token):
    r = api.post(f"{BASE_URL}/api/admin/reports/{pytest.report_id}/resolve", headers=auth(admin_token), timeout=10)
    assert r.status_code == 200


def test_admin_audit_log_has_entries(api, admin_token):
    r = api.get(f"{BASE_URL}/api/admin/audit", headers=auth(admin_token), timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list) and len(r.json()) > 0


def test_admin_cancel_order(api, admin_token, client_token):
    payload = {"title": f"{TAG} cancel me", "description": "", "type": "favor",
               "category_id": "cat-entregas", "city_id": "city-parauapebas",
               "neighborhood_id": "nb-1", "budget": 10}
    o = api.post(f"{BASE_URL}/api/orders", json=payload, headers=auth(client_token), timeout=10).json()
    r = api.post(f"{BASE_URL}/api/admin/orders/{o['id']}/cancel", headers=auth(admin_token), timeout=10)
    assert r.status_code == 200
    got = api.get(f"{BASE_URL}/api/orders/{o['id']}", timeout=10).json()
    assert got["status"] == "cancelled"
