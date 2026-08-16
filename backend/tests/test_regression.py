"""FAZÊ backend regression tests (iteration 5).

Covers bootstrap, geo/catalog, orders (filters + CRUD), proposals lifecycle,
chat, favorites, reports, notifications, and admin endpoints (positive + 403).
"""
import os
import uuid
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = (dotenv_values('/app/frontend/.env').get('EXPO_PUBLIC_BACKEND_URL')
            or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')

CLIENT = "demo-client"
WORKER = "demo-worker"
ADMIN = "demo-admin"
BAD_ADMIN = "demo-client"  # not admin

TAG = f"TEST_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


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
    # "guarda roupa" -> tokens >=3 -> "guarda", "roupa" should hit order-2
    orders = api.get(f"{BASE_URL}/api/orders", params={"q": "guarda roupa"}, timeout=10).json()
    assert any("guarda" in o["title"].lower() for o in orders)


def test_orders_max_budget(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"max_budget": 30}, timeout=10).json()
    assert all(o["budget"] <= 30 for o in orders)


def test_orders_client_all_statuses(api):
    orders = api.get(f"{BASE_URL}/api/orders", params={"client_id": CLIENT}, timeout=10).json()
    assert all(o["client_id"] == CLIENT for o in orders)


# ---------- order lifecycle ----------

@pytest.fixture(scope="session")
def created_order(api):
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
        "client_id": CLIENT,
    }
    r = api.post(f"{BASE_URL}/api/orders", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "published"
    assert d["client_id"] == CLIENT
    assert d["category"]["id"] == "cat-entregas"
    assert d["neighborhood"]  # enrichment
    return d


def test_get_order_enriched(api, created_order):
    r = api.get(f"{BASE_URL}/api/orders/{created_order['id']}", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == created_order["id"]
    assert d["category"]["name"] == "Entregas"
    assert d["client"]["id"] == CLIENT
    assert "proposals_count" in d


# ---------- proposals ----------

def test_proposal_owner_cannot_propose(api, created_order):
    r = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals",
                 json={"worker_id": CLIENT, "amount": 50, "message": "x"}, timeout=10)
    assert r.status_code == 400


def test_proposal_create_then_duplicate_rejected(api, created_order):
    body = {"worker_id": WORKER, "amount": 55, "message": f"{TAG} first", "eta": "Hoje"}
    r1 = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals", json=body, timeout=10)
    assert r1.status_code == 200, r1.text
    prop = r1.json()
    assert prop["status"] == "pending"
    r2 = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/proposals", json=body, timeout=10)
    assert r2.status_code == 400
    pytest.proposal_id = prop["id"]


def test_accept_proposal_only_owner(api, created_order):
    # wrong user
    r = api.post(f"{BASE_URL}/api/proposals/{pytest.proposal_id}/accept",
                 params={"user_id": WORKER}, timeout=10)
    assert r.status_code == 403
    # correct owner
    r2 = api.post(f"{BASE_URL}/api/proposals/{pytest.proposal_id}/accept",
                  params={"user_id": CLIENT}, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "accepted"
    order = api.get(f"{BASE_URL}/api/orders/{created_order['id']}", timeout=10).json()
    assert order["status"] == "accepted"
    assert order["worker_id"] == WORKER


def test_start_and_complete_permissions(api, created_order):
    # start by worker OK
    r = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/start",
                 params={"user_id": WORKER}, timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    # complete by worker forbidden
    rf = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/complete",
                  params={"user_id": WORKER}, timeout=10)
    assert rf.status_code == 403
    # complete by client OK
    rc = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/complete",
                  params={"user_id": CLIENT}, timeout=10)
    assert rc.status_code == 200 and rc.json()["status"] == "completed"


def test_reviews_mutual_and_duplicate_blocked(api, created_order):
    # client -> worker
    r1 = api.post(f"{BASE_URL}/api/reviews",
                  json={"order_id": created_order["id"], "from_id": CLIENT,
                        "to_id": WORKER, "stars": 5, "comment": f"{TAG} great"}, timeout=10)
    assert r1.status_code == 200
    # duplicate blocked
    r_dup = api.post(f"{BASE_URL}/api/reviews",
                     json={"order_id": created_order["id"], "from_id": CLIENT,
                           "to_id": WORKER, "stars": 4}, timeout=10)
    assert r_dup.status_code == 400
    # worker -> client OK (mutual)
    r2 = api.post(f"{BASE_URL}/api/reviews",
                  json={"order_id": created_order["id"], "from_id": WORKER,
                        "to_id": CLIENT, "stars": 5}, timeout=10)
    assert r2.status_code == 200


# ---------- chat ----------

def test_chat_only_participants(api, created_order):
    # stranger can't send
    r_bad = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/messages",
                     json={"sender_id": "worker-ana", "text": f"{TAG} sneak"}, timeout=10)
    assert r_bad.status_code == 403
    r_ok = api.post(f"{BASE_URL}/api/orders/{created_order['id']}/messages",
                    json={"sender_id": CLIENT, "text": f"{TAG} hello"}, timeout=10)
    assert r_ok.status_code == 200
    msgs = api.get(f"{BASE_URL}/api/orders/{created_order['id']}/messages", timeout=10).json()
    assert any(m["text"] == f"{TAG} hello" for m in msgs)


def test_conversations_list(api):
    convs = api.get(f"{BASE_URL}/api/conversations", params={"user_id": CLIENT}, timeout=10).json()
    assert isinstance(convs, list)
    assert convs and "order" in convs[0] and "other" in convs[0]


# ---------- favorites / reports / notifications ----------

def test_favorites_toggle_and_list(api, created_order):
    r1 = api.post(f"{BASE_URL}/api/favorites/toggle",
                  json={"user_id": WORKER, "order_id": created_order["id"]}, timeout=10).json()
    assert r1["favorited"] is True
    fav = api.get(f"{BASE_URL}/api/favorites", params={"user_id": WORKER}, timeout=10).json()
    assert created_order["id"] in fav["order_ids"]
    r2 = api.post(f"{BASE_URL}/api/favorites/toggle",
                  json={"user_id": WORKER, "order_id": created_order["id"]}, timeout=10).json()
    assert r2["favorited"] is False


def test_report_create(api, created_order):
    r = api.post(f"{BASE_URL}/api/reports", json={
        "reporter_id": CLIENT, "target_type": "order",
        "target_id": created_order["id"], "reason": "spam",
        "details": f"{TAG} regression report"}, timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "open"
    pytest.report_id = r.json()["id"]


def test_notifications_flow(api):
    d = api.get(f"{BASE_URL}/api/notifications", params={"user_id": WORKER}, timeout=10).json()
    assert "items" in d and "unread" in d
    api.post(f"{BASE_URL}/api/notifications/read", params={"user_id": WORKER}, timeout=10)
    d2 = api.get(f"{BASE_URL}/api/notifications", params={"user_id": WORKER}, timeout=10).json()
    assert d2["unread"] == 0


# ---------- admin ----------

def test_admin_requires_admin_id(api):
    r = api.get(f"{BASE_URL}/api/admin/overview", params={"admin_id": BAD_ADMIN}, timeout=10)
    assert r.status_code == 403


def test_admin_overview(api):
    r = api.get(f"{BASE_URL}/api/admin/overview", params={"admin_id": ADMIN}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["users"] >= 4 and d["orders"] >= 5


def test_admin_categories_toggle_and_subcategory_add(api):
    cats = api.get(f"{BASE_URL}/api/admin/categories", params={"admin_id": ADMIN}, timeout=10).json()
    target = cats[-1]
    # add sub
    sub = api.post(f"{BASE_URL}/api/admin/subcategories", params={"admin_id": ADMIN},
                   json={"category_id": target["id"], "name": f"{TAG}-sub", "active": True}, timeout=10)
    assert sub.status_code == 200
    # toggle inactive then back
    r_off = api.patch(f"{BASE_URL}/api/admin/categories/{target['id']}",
                      params={"admin_id": ADMIN}, json={"active": False}, timeout=10)
    assert r_off.status_code == 200
    r_on = api.patch(f"{BASE_URL}/api/admin/categories/{target['id']}",
                     params={"admin_id": ADMIN}, json={"active": True}, timeout=10)
    assert r_on.status_code == 200


def test_admin_geo_toggle(api):
    # Toggle an inactive city off/on
    r = api.patch(f"{BASE_URL}/api/admin/geo/cities/city-canaa",
                  params={"admin_id": ADMIN}, json={"active": True}, timeout=10)
    assert r.status_code == 200
    r2 = api.patch(f"{BASE_URL}/api/admin/geo/cities/city-canaa",
                   params={"admin_id": ADMIN}, json={"active": False}, timeout=10)
    assert r2.status_code == 200


def test_admin_reports_resolve(api):
    r = api.post(f"{BASE_URL}/api/admin/reports/{pytest.report_id}/resolve",
                 params={"admin_id": ADMIN}, timeout=10)
    assert r.status_code == 200


def test_admin_cancel_order(api):
    # create a throwaway order and cancel
    payload = {"title": f"{TAG} cancel me", "description": "", "type": "favor",
               "category_id": "cat-entregas", "city_id": "city-parauapebas",
               "neighborhood_id": "nb-1", "budget": 10, "client_id": CLIENT}
    o = api.post(f"{BASE_URL}/api/orders", json=payload, timeout=10).json()
    r = api.post(f"{BASE_URL}/api/admin/orders/{o['id']}/cancel",
                 params={"admin_id": ADMIN}, timeout=10)
    assert r.status_code == 200
    got = api.get(f"{BASE_URL}/api/orders/{o['id']}", timeout=10).json()
    assert got["status"] == "cancelled"
