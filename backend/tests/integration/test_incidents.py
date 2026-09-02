"""
Integration tests for the incidents endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def _create_incident(client, headers, **overrides):
    payload = {
        "title": "Database connection pool exhausted",
        "description": "P95 latency exceeded 5 seconds for 15 minutes on the API.",
        "severity": "High",
        "service": "payment-api",
        **overrides,
    }
    return client.post("/api/v1/incidents", json=payload, headers=headers)


class TestCreateIncident:
    def test_create_success(self, client: TestClient):
        headers = register_and_login(client)
        resp = _create_incident(client, headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Database connection pool exhausted"
        assert data["severity"] == "High"
        assert data["status"] == "Open"
        assert "id" in data
        assert "created_at" in data

    def test_requires_auth(self, client: TestClient):
        # HTTPBearer returns 401 when no Authorization header is sent
        resp = _create_incident(client, {})
        assert resp.status_code == 401

    def test_invalid_severity_rejected(self, client: TestClient):
        headers = register_and_login(client)
        resp = _create_incident(client, headers, severity="potato")
        assert resp.status_code == 422

    def test_all_valid_severities(self, client: TestClient):
        headers = register_and_login(client)
        for sev in ("Critical", "High", "Medium", "Low"):
            resp = _create_incident(client, headers, severity=sev)
            assert resp.status_code == 201, f"Failed for severity: {sev}"

    def test_short_title_rejected(self, client: TestClient):
        headers = register_and_login(client)
        resp = _create_incident(client, headers, title="AB")
        assert resp.status_code == 422

    def test_short_description_rejected(self, client: TestClient):
        headers = register_and_login(client)
        resp = _create_incident(client, headers, description="too short")
        assert resp.status_code == 422


class TestListIncidents:
    def test_empty_list(self, client: TestClient):
        headers = register_and_login(client)
        resp = client.get("/api/v1/incidents", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_own_incidents(self, client: TestClient):
        headers = register_and_login(client)
        _create_incident(client, headers)
        _create_incident(client, headers, title="Second incident that is descriptive")
        resp = client.get("/api/v1/incidents", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_org_isolation(self, client: TestClient):
        """User from org A cannot see incidents from org B."""
        # Use distinct org names so they get separate organizations
        resp_a = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Alpha",
            "name": "User A", "email": "a@orga.com", "password": "password123",
        })
        headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

        resp_b = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Beta",
            "name": "User B", "email": "b@orgb.com", "password": "password123",
        })
        headers_b = {"Authorization": f"Bearer {resp_b.json()['access_token']}"}

        _create_incident(client, headers_a)

        resp_b_list = client.get("/api/v1/incidents", headers=headers_b)
        assert resp_b_list.json() == []

    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/incidents")
        assert resp.status_code == 401


class TestGetIncident:
    def test_get_own_incident(self, client: TestClient):
        headers = register_and_login(client)
        created = _create_incident(client, headers).json()
        resp = client.get(f"/api/v1/incidents/{created['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_cannot_get_other_orgs_incident(self, client: TestClient):
        resp_a = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Alpha", "name": "User A",
            "email": "a@orga.com", "password": "password123",
        })
        headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

        resp_b = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Beta", "name": "User B",
            "email": "b@orgb.com", "password": "password123",
        })
        headers_b = {"Authorization": f"Bearer {resp_b.json()['access_token']}"}

        incident_a = _create_incident(client, headers_a).json()

        resp = client.get(f"/api/v1/incidents/{incident_a['id']}", headers=headers_b)
        assert resp.status_code == 404

    def test_nonexistent_incident(self, client: TestClient):
        headers = register_and_login(client)
        resp = client.get("/api/v1/incidents/999999", headers=headers)
        assert resp.status_code == 404


class TestUpdateIncident:
    def test_update_status(self, client: TestClient):
        headers = register_and_login(client)
        incident = _create_incident(client, headers).json()
        resp = client.patch(
            f"/api/v1/incidents/{incident['id']}",
            json={"status": "Resolved"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Resolved"

    def test_update_severity(self, client: TestClient):
        headers = register_and_login(client)
        incident = _create_incident(client, headers).json()
        resp = client.patch(
            f"/api/v1/incidents/{incident['id']}",
            json={"severity": "Critical"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["severity"] == "Critical"

    def test_cannot_update_other_orgs_incident(self, client: TestClient):
        resp_a = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Alpha", "name": "User A",
            "email": "a@orga.com", "password": "password123",
        })
        headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

        resp_b = client.post("/api/v1/auth/register", json={
            "organization_name": "Org Beta", "name": "User B",
            "email": "b@orgb.com", "password": "password123",
        })
        headers_b = {"Authorization": f"Bearer {resp_b.json()['access_token']}"}

        incident_a = _create_incident(client, headers_a).json()

        resp = client.patch(
            f"/api/v1/incidents/{incident_a['id']}",
            json={"status": "Resolved"},
            headers=headers_b,
        )
        assert resp.status_code == 404

    def test_invalid_status_rejected(self, client: TestClient):
        headers = register_and_login(client)
        incident = _create_incident(client, headers).json()
        resp = client.patch(
            f"/api/v1/incidents/{incident['id']}",
            json={"status": "InvalidStatus"},
            headers=headers,
        )
        assert resp.status_code == 422
