"""Tests for the zone-based "opportunities near you" soft ranking in GET /orders
(see routes/public.py's list_orders). Every order created here is tagged with a
unique title so the assertions only ever look at this test's own orders, never
at whatever else has accumulated in the dev database from other test runs.

Neighborhood ids used (seed.py's fixed demo geography, city-parauapebas):
nb-19 = Altamira (Zona Norte), nb-15 = Beira Rio (Zona Norte, different bairro,
same zone as nb-19), nb-1 = Cidade Nova (Zona Central, same city, different zone).
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

TEST_PASSWORD = "TestPass123!"
TAG = f"ZONE_{uuid.uuid4().hex[:8]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _random_phone():
    return "94" + "9" + f"{uuid.uuid4().int % 10**8:08d}"


def _register(api, tag, neighborhood_id="nb-19"):
    email = f"{tag}_{uuid.uuid4().hex[:8]}@example.com"
    r = api.post(f"{API}/auth/register", json={
        "name": f"Test {tag}", "email": email, "phone": _random_phone(), "password": TEST_PASSWORD,
        "city_id": "city-parauapebas", "neighborhood_id": neighborhood_id, "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    token, user_id = body["token"], body["user"]["id"]
    hdrs = auth(token)
    api.post(f"{API}/auth/verify-email", headers=hdrs, json={"code": body["dev_code_email"]}, timeout=15)
    api.post(f"{API}/auth/verify-phone", headers=hdrs, json={"code": body["dev_code_phone"]}, timeout=15)
    return token, user_id


def make_order(api, token, title_suffix, city_id="city-parauapebas", neighborhood_id=None):
    r = api.post(f"{API}/orders", headers=auth(token), json={
        "title": f"{TAG} {title_suffix}", "description": "zone ranking test", "type": "favor",
        "category_id": "cat-entregas", "city_id": city_id, "neighborhood_id": neighborhood_id,
        "date_label": "Hoje", "time_label": "", "budget": 30, "photos": [], "fields": {},
        "urgent": False, "recurrence": "none",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def zone_scenario(api):
    caller_token, _ = _register(api, "zone_caller")  # neighborhood_id=nb-19 (Altamira, Zona Norte)
    poster_token, _ = _register(api, "zone_poster")
    same_hood = make_order(api, poster_token, "same-hood", neighborhood_id="nb-19")
    same_zone = make_order(api, poster_token, "same-zone", neighborhood_id="nb-15")
    same_city = make_order(api, poster_token, "same-city", neighborhood_id="nb-1")
    other_city = make_order(api, poster_token, "other-city", city_id="city-canaa", neighborhood_id=None)
    return {
        "caller_token": caller_token,
        "expected_order": [same_hood["id"], same_zone["id"], same_city["id"], other_city["id"]],
        "same_hood_id": same_hood["id"],
        "same_zone_id": same_zone["id"],
    }


def test_orders_ranked_same_neighborhood_zone_city_then_rest(api, zone_scenario):
    r = api.get(f"{API}/orders", headers=auth(zone_scenario["caller_token"]),
                params={"q": TAG, "limit": 50}, timeout=15)
    assert r.status_code == 200, r.text
    ids_seen = [o["id"] for o in r.json()]
    expected = zone_scenario["expected_order"]
    actual_relative_order = [i for i in ids_seen if i in expected]
    assert actual_relative_order == expected, f"expected tier order {expected}, got {actual_relative_order}"


def test_explicit_neighborhood_filter_bypasses_zone_ranking(api, zone_scenario):
    # An explicit neighborhood_id must still behave as an exact filter — the zone
    # order-mate (nb-15) must NOT leak in just because it shares a zone.
    r = api.get(f"{API}/orders", headers=auth(zone_scenario["caller_token"]),
                params={"q": TAG, "neighborhood_id": "nb-19", "limit": 50}, timeout=15)
    assert r.status_code == 200, r.text
    ids_seen = {o["id"] for o in r.json()}
    assert zone_scenario["same_hood_id"] in ids_seen
    assert zone_scenario["same_zone_id"] not in ids_seen


def test_anonymous_request_falls_back_to_plain_sort(zone_scenario):
    s = requests.Session()
    r = s.get(f"{API}/orders", params={"q": TAG, "limit": 50}, timeout=15)
    assert r.status_code == 200, r.text
    ids_seen = {o["id"] for o in r.json()}
    for order_id in zone_scenario["expected_order"]:
        assert order_id in ids_seen
