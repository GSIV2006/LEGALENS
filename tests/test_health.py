"""Tests for health endpoint."""
import pytest


class TestHealth:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns ok status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert "database" in data
        assert "ocr" in data
        assert data["ocr"] == "mock"

    def test_health_check_structure(self, client):
        """Test health endpoint response structure."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Check all expected fields
        assert isinstance(data, dict)
        assert "status" in data
        assert "database" in data
        assert "ocr" in data
        assert "storage_mode" in data
        assert "environment" in data

    def test_health_check_database_status(self, client):
        """Test database status in health."""
        response = client.get("/health")
        data = response.json()

        # Database should be connected in test environment
        assert data["database"] in ["connected", "disconnected"]
