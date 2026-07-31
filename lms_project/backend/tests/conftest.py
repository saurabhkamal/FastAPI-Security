import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app import config
from app.idempotency import reset_idempotency_cache
from app.limiter import limiter
from app.main import app
from app.store import reset_store

API_KEY = config.API_KEY
ADMIN_EMAIL = config.ADMIN_EMAIL
ADMIN_PASSWORD = config.ADMIN_PASSWORD
INSTRUCTOR_EMAIL = config.INSTRUCTOR_EMAIL
INSTRUCTOR_PASSWORD = config.INSTRUCTOR_PASSWORD


@pytest.fixture()
def client():
    reset_store()
    reset_idempotency_cache()
    limiter.reset()
    with TestClient(app) as c:
        yield c
    reset_store()
    reset_idempotency_cache()
    limiter.reset()


def api_headers(extra: dict | None = None) -> dict:
    headers = {"X-API-Key": API_KEY}
    if extra:
        headers.update(extra)
    return headers


def auth_headers(token: str, extra: dict | None = None) -> dict:
    headers = api_headers({"Authorization": f"Bearer {token}"})
    if extra:
        headers.update(extra)
    return headers


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", headers=api_headers(), json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def register_student(client: TestClient, name="Alice Student", email="alice@example.com", password="StrongPass123"):
    return client.post(
        "/students/register",
        headers=api_headers(),
        json={"name": name, "email": email, "password": password},
    )
