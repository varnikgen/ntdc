import os
import tempfile
import base64

os.environ["NCDC_ADMIN_USER"] = "admin"
os.environ["NCDC_ADMIN_PASS"] = "test-admin-pass-123"
os.environ["SECRET_KEY"] = "test-secret-key-16chars"
os.environ["PROVISION_AUTH_ENABLED"] = "true"
os.environ["PROVISION_USER"] = "provision"
os.environ["PROVISION_PASS"] = "test-prov-pass"
os.environ["PROVISION_BOOTSTRAP"] = "true"
os.environ["PHONE_WEB_PASSWORD"] = "PhoneWeb-Test-1"
os.environ["ACTION_URI_TOKEN"] = "test-token-123"
os.environ["AUTO_ENROLL"] = "true"
os.environ["DEBUG"] = "false"
os.environ["PUBLIC_BASE_URL"] = "https://ncdc.test"

_tmp = tempfile.NamedTemporaryFile(prefix="ncdc-test-", suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import AdminUser
from app.security import hash_password
from app.middleware.auth import invalidate_auth_cache


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_session(client):
    """Логин через форму → cookie сессии."""
    invalidate_auth_cache()
    r = client.post(
        "/login",
        data={"username": "admin", "password": "test-admin-pass-123", "next": "/"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), r.text
    # CSRF из cookie после GET
    client.get("/login")
    token = client.cookies.get("ncdc_csrf")
    headers = {}
    if token:
        headers["X-CSRF-Token"] = token
    return headers


@pytest.fixture
def operator_session(client):
    invalidate_auth_cache()
    db = SessionLocal()
    try:
        u = db.query(AdminUser).filter(AdminUser.username == "operator1").first()
        if not u:
            u = AdminUser(
                username="operator1",
                password_hash=hash_password("operator-pass-123"),
                role="operator",
                is_active=True,
            )
            db.add(u)
            db.commit()
    finally:
        db.close()
    invalidate_auth_cache()
    r = client.post(
        "/login",
        data={"username": "operator1", "password": "operator-pass-123", "next": "/"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), r.text
    client.get("/")
    token = client.cookies.get("ncdc_csrf")
    headers = {}
    if token:
        headers["X-CSRF-Token"] = token
    return headers


@pytest.fixture
def admin_headers(client, admin_session):
    """Сессия admin + CSRF (для POST)."""
    return admin_session
