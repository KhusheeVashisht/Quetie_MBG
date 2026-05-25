"""
Tests for dashboard admin / moderator management
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from quetie.db.database import Database
from quetie.web.app import app
from quetie.web.auth import SecurityManager


class TestAdminManagement:
    @classmethod
    def setup_class(cls):
        Database.initialize("sqlite:///:memory:")
        SecurityManager.init_default_admin()

    def _auth_headers(self):
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        token = response.json()["token"]
        return client, {"Authorization": f"Bearer {token}"}

    def test_super_admin_can_create_and_disable_member(self):
        client, headers = self._auth_headers()
        username = f"mod_{uuid4().hex[:8]}"

        create_response = client.post(
            "/api/admins",
            json={
                "username": username,
                "password": "modpass123",
                "email": f"{username}@example.com",
                "is_super_admin": False,
            },
            headers=headers,
        )
        assert create_response.status_code == 200
        assert create_response.json()["admin"]["username"] == username
        assert create_response.json()["admin"]["role"] == "moderator"

        list_response = client.get("/api/admins", headers=headers)
        assert list_response.status_code == 200
        admins = list_response.json()["admins"]
        created_admin = next((item for item in admins if item["username"] == username), None)
        assert created_admin is not None
        assert created_admin["is_active"] is True

        update_response = client.patch(
            f"/api/admins/{created_admin['id']}",
            json={"is_active": False},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["admin"]["is_active"] is False

    def test_duplicate_admin_username_is_rejected(self):
        client, headers = self._auth_headers()

        response = client.post(
            "/api/admins",
            json={
                "username": "admin",
                "password": "anotherpass123",
                "email": "duplicate@example.com",
                "is_super_admin": False,
            },
            headers=headers,
        )
        assert response.status_code == 400
