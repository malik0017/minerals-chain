"""
tests/conftest.py — in-process integration tests (FastAPI TestClient)
Pre-reqs (same as check_routes.py):
    alembic upgrade head
    python scripts/seed_test_data.py
    pytest tests/ -q
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.base import SessionLocal
from app.main import app

PASSWORD = "admin123"


class Client:

    def __init__(self, email: str | None = None):
        self.c = TestClient(app)
        self.c.get("/login")
        if email:
            r = self.post("/login", {"email": email, "password": PASSWORD})
            assert r.status_code in (302, 303), f"login failed for {email}"

    def post(self, url, data=None, files=None, **kw):
        data = dict(data or {})
        data["csrf_token"] = self.c.cookies.get("mc_csrf")
        return self.c.post(url, data=data, files=files, follow_redirects=False, **kw)

    def get(self, url, **kw):
        return self.c.get(url, follow_redirects=False, **kw)


@pytest.fixture
def admin():
    return Client("admin@mineralstest.com")


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def uniq():
    return uuid.uuid4().hex[:6].upper()
