"""Tests for the geography/catalog proof-of-concept cutover slice
(backend/geo_catalog_repo.py) — the one part of the app that reads/writes real
PostgreSQL today, gated by GEO_CATALOG_BACKEND and only enabled in the isolated
environment (backend/.env.isolated, port 8001, see backend/backups/README.md).
These tests talk to port 8001, never port 8000 — the main dev app never touches
Postgres and these tests must never be able to affect it.
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

# Deliberately hardcoded, not derived from EXPO_PUBLIC_BACKEND_URL: this suite's
# whole point is to exercise a DIFFERENT port than the rest of the tests use, per
# backend/backups/README.md's documented `favor-backend-isolated` config.
ISOLATED_API = "http://localhost:8001/api"

_isolated_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env.isolated"))
_backend_selected = (_isolated_env.get("GEO_CATALOG_BACKEND") or os.environ.get("GEO_CATALOG_BACKEND", "")) == "postgres"

try:
    _reachable = requests.get(f"{ISOLATED_API}/feature-flags", timeout=3).status_code == 200
except requests.exceptions.RequestException:
    _reachable = False

pytestmark = pytest.mark.skipif(
    not (_backend_selected and _reachable),
    reason="Ambiente isolado (porta 8001) não está no ar ou GEO_CATALOG_BACKEND != 'postgres'",
)

ADMIN_EMAIL = "admin@fazum.demo"
ADMIN_PASSWORD = "faze2024"
TAG = f"GEOPG_{uuid.uuid4().hex[:6]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{ISOLATED_API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_bootstrap_returns_real_migrated_geography_and_catalog():
    r = requests.get(f"{ISOLATED_API}/bootstrap", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(s["id"] == "st-pa" and s["uf"] == "PA" for s in body["states"])
    assert any(c["id"] == "city-parauapebas" for c in body["cities"])
    assert len(body["neighborhoods"]) > 0
    cat_ids = {c["id"] for c in body["categories"]}
    assert "cat-entregas" in cat_ids


def test_geo_endpoints_filter_correctly():
    r = requests.get(f"{ISOLATED_API}/geo/neighborhoods", params={"city_id": "city-parauapebas"}, timeout=15)
    assert r.status_code == 200, r.text
    hoods = r.json()
    assert len(hoods) > 0
    assert all(h["city_id"] == "city-parauapebas" for h in hoods)


def test_categories_endpoint_includes_subcategories():
    r = requests.get(f"{ISOLATED_API}/categories", timeout=15)
    assert r.status_code == 200, r.text
    cats = r.json()
    entregas = next((c for c in cats if c["id"] == "cat-entregas"), None)
    assert entregas is not None
    assert len(entregas["subcategories"]) > 0


def test_admin_create_category_is_immediately_readable(admin_token):
    name = f"{TAG} categoria"
    r = requests.post(f"{ISOLATED_API}/admin/categories", headers=auth(admin_token),
                       json={"name": name, "icon": "flask-outline", "active": True}, timeout=15)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == name

    r2 = requests.get(f"{ISOLATED_API}/categories", timeout=15)
    assert r2.status_code == 200, r2.text
    match = next((c for c in r2.json() if c["id"] == created["id"]), None)
    assert match is not None, "categoria criada via Postgres não apareceu na leitura imediatamente seguinte"
    assert match["name"] == name


def test_admin_patch_category_persists(admin_token):
    name = f"{TAG} patch alvo"
    created = requests.post(f"{ISOLATED_API}/admin/categories", headers=auth(admin_token),
                             json={"name": name, "icon": "flask-outline", "active": True}, timeout=15).json()

    r = requests.patch(f"{ISOLATED_API}/admin/categories/{created['id']}", headers=auth(admin_token),
                        json={"active": False}, timeout=15)
    assert r.status_code == 200, r.text

    admin_cats = requests.get(f"{ISOLATED_API}/admin/categories", headers=auth(admin_token), timeout=15).json()
    match = next((c for c in admin_cats if c["id"] == created["id"]), None)
    assert match is not None and match["active"] is False


def test_duplicate_uf_returns_clean_400_not_500(admin_token):
    r = requests.post(f"{ISOLATED_API}/admin/geo/states", headers=auth(admin_token),
                       json={"name": f"{TAG} estado duplicado", "uf": "PA", "active": True}, timeout=15)
    assert r.status_code == 400, r.text


def test_patch_geo_invalid_kind_rejected(admin_token):
    r = requests.patch(f"{ISOLATED_API}/admin/geo/not-a-real-kind/some-id", headers=auth(admin_token),
                        json={"active": False}, timeout=15)
    assert r.status_code == 400, r.text


def test_main_dev_environment_still_defaults_to_mongo():
    # Sanity check for the whole slice's core safety property: the MAIN dev env
    # (port 8000) was never given GEO_CATALOG_BACKEND, so it must still be "mongo".
    main_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    assert main_env.get("GEO_CATALOG_BACKEND") is None
