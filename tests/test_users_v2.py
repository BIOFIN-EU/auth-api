"""
Accounts: lower-case emails, display names, the default "user" role and
granting admin, and the user lookups physical-api uses.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app

PASSWORD = "Test-pass-1234!"
GATEWAY = {"X-Client-ID": settings.GATEWAY_AUTH_CLIENT_ID, "X-Client-Secret": settings.GATEWAY_AUTH_CLIENT_SECRET}
PHYSICAL = {"X-Client-ID": settings.PHYSICAL_AUTH_CLIENT_ID, "X-Client-Secret": settings.PHYSICAL_AUTH_CLIENT_SECRET}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs startup: tables and seed
        yield c


def _email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@Example.ORG"


def _register(client, email, **extra):
    return client.post("/api/auth/register", json={"email": email, "password": PASSWORD, **extra}, headers=GATEWAY)


def _login(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers=GATEWAY)
    assert response.status_code == 200, response.text
    return response.json()


def _claims(token: str) -> dict:
    from jose import jwt
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def _bearer(token: str) -> dict:
    return {**GATEWAY, "Authorization": f"Bearer {token}"}


def test_emails_ignore_capitals(client):
    email = _email()
    created = _register(client, email)
    assert created.status_code == 201
    assert created.json()["email"] == email.lower()
    assert _register(client, email.lower()).status_code == 409
    assert _login(client, email.upper())["access_token"]


def test_new_accounts_get_the_user_role_and_an_optional_name(client):
    email = _email()
    assert _register(client, email, display_name="  Jane   Smith ").json()["display_name"] == "Jane Smith"
    claims = _claims(_login(client, email)["access_token"])
    assert claims["roles"] == ["user"]
    assert _register(client, _email()).json()["display_name"] is None


def test_users_can_change_their_name(client):
    email = _email()
    _register(client, email)
    token = _login(client, email)["access_token"]
    named = client.patch("/api/auth/me", json={"display_name": "Sam Lee"}, headers=_bearer(token))
    assert named.status_code == 200 and named.json()["display_name"] == "Sam Lee"
    assert client.get("/api/auth/me", headers=_bearer(token)).json()["display_name"] == "Sam Lee"
    cleared = client.patch("/api/auth/me", json={"display_name": " "}, headers=_bearer(token))
    assert cleared.json()["display_name"] is None


def test_a_closed_accounts_email_cannot_register_again(client):
    email = _email()
    _register(client, email)
    token = _login(client, email)["access_token"]
    assert client.post("/api/auth/close-account", headers=_bearer(token)).status_code == 204
    assert _register(client, email).status_code == 409


def test_lookups_are_for_physical_api_only(client):
    named, other, closed = _email(), _email(), _email()
    ids = {}
    for email, name in ((named, "Ana Ruiz"), (other, None), (closed, None)):
        ids[email] = _register(client, email, display_name=name).json()["id"]
    token = _login(client, closed)["access_token"]
    client.post("/api/auth/close-account", headers=_bearer(token))

    body = {"ids": list(ids.values()) + [str(uuid.uuid4())]}
    assert client.post("/api/auth/users/lookup", json=body, headers=GATEWAY).status_code == 403
    found = client.post("/api/auth/users/lookup", json=body, headers=PHYSICAL).json()
    assert {u["email"]: u["display_name"] for u in found} == {named.lower(): "Ana Ruiz", other.lower(): None}

    assert client.get("/api/auth/users/by-email", params={"email": named}, headers=GATEWAY).status_code == 403
    by_email = client.get("/api/auth/users/by-email", params={"email": named.upper()}, headers=PHYSICAL)
    assert by_email.status_code == 200 and by_email.json()["id"] == ids[named]
    assert client.get("/api/auth/users/by-email", params={"email": closed}, headers=PHYSICAL).status_code == 404


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "app.cli", *args], capture_output=True, text=True, env=os.environ)


def test_admin_is_granted_from_the_command_line(client):
    email = _email("admin")
    _register(client, email)
    granted = _cli("grant-role", email.upper(), "admin")
    assert granted.returncode == 0, granted.stderr
    claims = _claims(_login(client, email)["access_token"])
    assert claims["roles"] == ["admin", "user"]
    assert "users:write" in claims["permissions"]

    assert _cli("revoke-role", email, "admin").returncode == 0
    assert _claims(_login(client, email)["access_token"])["roles"] == ["user"]
    assert _cli("grant-role", email, "borrower").returncode == 1  # retired
    assert _cli("grant-role", "nobody@example.org", "admin").returncode == 1
