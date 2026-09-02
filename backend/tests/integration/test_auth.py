"""
Integration tests for the authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_login


class TestRegister:
    def test_register_success(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Acme Corp",
                "name": "Alice",
                "email": "alice@acme.com",
                "password": "strongpassword",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_duplicate_email_rejected(self, client: TestClient):
        payload = {
            "organization_name": "Acme Corp",
            "name": "Alice",
            "email": "alice@acme.com",
            "password": "strongpassword",
        }
        client.post("/api/v1/auth/register", json=payload)
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_invalid_email_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org",
                "name": "Bob",
                "email": "not-an-email",
                "password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_short_password_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org",
                "name": "Bob",
                "email": "bob@org.com",
                "password": "short",
            },
        )
        assert resp.status_code == 422

    def test_first_user_gets_admin_role(self, client: TestClient):
        headers = register_and_login(client, "admin@org.com")
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_second_user_same_org_gets_member_role(self, client: TestClient):
        # First user — admin
        client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "SharedOrg",
                "name": "Admin User",
                "email": "admin@shared.com",
                "password": "password123",
            },
        )
        # Second user — same org slug
        resp2 = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "SharedOrg",
                "name": "Member User",
                "email": "member@shared.com",
                "password": "password123",
            },
        )
        assert resp2.status_code == 201
        token = resp2.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["role"] == "member"


class TestLogin:
    def test_login_success(self, client: TestClient):
        client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org",
                "name": "Alice",
                "email": "alice@org.com",
                "password": "mypassword123",
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@org.com", "password": "mypassword123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_wrong_password_rejected(self, client: TestClient):
        client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org",
                "name": "Alice",
                "email": "alice@org.com",
                "password": "correctpassword",
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@org.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_unknown_email_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@nowhere.com", "password": "password"},
        )
        assert resp.status_code == 401


class TestMe:
    def test_me_returns_user(self, client: TestClient):
        headers = register_and_login(client, "me@test.com")
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert "id" in data
        assert "organization_id" in data
        assert "role" in data

    def test_me_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        # HTTPBearer returns 401 when no Authorization header is sent (FastAPI >= 0.100)
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
