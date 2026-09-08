"""Tests for authentication endpoints."""
import pytest


class TestAuthentication:
    """Test authentication functionality."""

    def test_register_new_user(self, client, db_session):
        """Test user registration."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@test.com",
                "username": "newuser",
                "password": "password123",
                "full_name": "New User",
                "role": "VIEWER",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["username"] == "newuser"
        assert data["role"] == "VIEWER"

    def test_register_duplicate_email(self, client, db_session, admin_user):
        """Test registration with duplicate email fails."""
        response = client.post(
            "/auth/register",
            json={
                "email": "admin@test.com",
                "username": "anotheruser",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_duplicate_username(self, client, db_session, admin_user):
        """Test registration with duplicate username fails."""
        response = client.post(
            "/auth/register",
            json={
                "email": "another@test.com",
                "username": "admin_test",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "already taken" in response.json()["detail"].lower()

    def test_login_success(self, client, db_session, admin_user):
        """Test successful login."""
        response = client.post(
            "/auth/login/json",
            json={
                "email": "admin@test.com",
                "password": "admin123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db_session, admin_user):
        """Test login with wrong password fails."""
        response = client.post(
            "/auth/login/json",
            json={
                "email": "admin@test.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user fails."""
        response = client.post(
            "/auth/login/json",
            json={
                "email": "nonexistent@test.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401

    def test_me_unauthorized(self, client):
        """Test /auth/me without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_authorized(self, client, auth_headers):
        """Test /auth/me with valid authentication."""
        response = client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "ADMIN"

    def test_invalid_role_on_register(self, client):
        """Test registration with invalid role fails."""
        response = client.post(
            "/auth/register",
            json={
                "email": "invalidrole@test.com",
                "username": "invalidrole",
                "password": "password123",
                "role": "SUPERADMIN",
            },
        )

        assert response.status_code == 400
        assert "invalid role" in response.json()["detail"].lower()
