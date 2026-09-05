"""Shared fixtures for the whole test suite.

`api` and `admin_token` used to be redefined identically in every test file. Under
pytest-xdist (`-n2 --dist loadscope`), each file's own session-scoped fixture ran its
own independent admin login, so a single full run could fire off one admin login per
file — and two consecutive runs (the project's standard verification step) could push
the shared "login:{ip}:admin@fazum.demo" rate-limit bucket past its cap and cascade
failures into unrelated tests. Defining them once here means every file in a given
xdist worker process shares the SAME cached login for the whole session.

`admin_token` logs in through the admin panel's own auth (`/admin/auth/login`,
db.admin_users) rather than the consumer `/auth/login` — admin sessions are a
completely separate identity system now (see admin_auth.py), and every test file
that depends on this fixture only ever uses the token against `/admin/*` endpoints,
so this single swap is enough to keep the whole suite working without touching
the other files.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@fazum.demo"
ADMIN_PASSWORD = "faze2024"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]
