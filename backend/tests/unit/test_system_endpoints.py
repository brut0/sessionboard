"""Unit tests for system endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_version() -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "env" in data
    assert "X-Trace-Id" in response.headers
    assert len(response.headers["X-Trace-Id"]) == 32


def test_api_health_healthy() -> None:
    with patch("app.main.check_db_health", return_value=True):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "ok"}
        assert "X-Trace-Id" in response.headers


def test_api_health_unhealthy() -> None:
    with patch("app.main.check_db_health", return_value=False):
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "error"}
        assert "X-Trace-Id" in response.headers
