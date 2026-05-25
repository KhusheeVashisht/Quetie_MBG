"""
Tests for the health endpoint.
"""

from fastapi.testclient import TestClient

from quetie.db.database import Database
from quetie.web.app import app


class TestHealthEndpoint:
    @classmethod
    def setup_class(cls):
        Database.initialize("sqlite:///:memory:")

    def test_get_health_returns_json(self):
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert "status" in body
        assert "database" in body

    def test_head_health_returns_200_without_body(self):
        client = TestClient(app)

        response = client.head("/health")

        assert response.status_code == 200
        assert response.text == ""
        assert response.content == b""