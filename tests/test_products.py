"""Tests for product endpoints."""
import pytest


class TestProducts:
    """Test product CRUD operations."""

    def test_create_product(self, client, auth_headers):
        """Test product creation."""
        response = client.post(
            "/products/",
            headers=auth_headers,
            json={
                "product_name": "Test Product",
                "brand": "Test Brand",
                "category": "Test Category",
                "manufacturer": "Test Manufacturer",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["product_name"] == "Test Product"
        assert data["brand"] == "Test Brand"
        assert data["category"] == "Test Category"

    def test_create_product_unauthorized(self, client):
        """Test product creation without auth fails."""
        response = client.post(
            "/products/",
            json={
                "product_name": "Test Product",
            },
        )

        assert response.status_code == 401

    def test_create_product_viewer_forbidden(self, client, db_session, viewer_user):
        """Test product creation with VIEWER role fails."""
        # Login as viewer
        login_response = client.post(
            "/auth/login/json",
            json={
                "email": "viewer@test.com",
                "password": "viewer123",
            },
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/products/",
            headers=headers,
            json={
                "product_name": "Test Product",
            },
        )

        assert response.status_code == 403

    def test_list_products(self, client, auth_headers, db_session, product):
        """Test listing products."""
        response = client.get("/products/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert data["total"] >= 1

    def test_get_product(self, client, auth_headers, db_session, product):
        """Test getting a single product."""
        response = client.get(
            f"/products/{product.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == product.id
        assert data["product_name"] == product.product_name

    def test_get_nonexistent_product(self, client, auth_headers):
        """Test getting non-existent product."""
        response = client.get(
            "/products/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_search_products(self, client, auth_headers, db_session, product):
        """Test product search."""
        response = client.get(
            "/products/search?q=Test",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) >= 1
        assert any(p["product_name"].startswith("Test") for p in data["products"])

    def test_update_product(self, client, auth_headers, db_session, product):
        """Test updating a product."""
        response = client.put(
            f"/products/{product.id}",
            headers=auth_headers,
            json={
                "brand": "Updated Brand",
                "notes": "Updated notes",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brand"] == "Updated Brand"
        assert data["notes"] == "Updated notes"

    def test_delete_product(self, client, auth_headers, db_session, another_product):
        """Test deleting a product."""
        response = client.delete(
            f"/products/{another_product.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    def test_delete_product_with_inspections(self, client, auth_headers, db_session, product):
        """Test deleting product with inspections fails."""
        from app.models import Inspection

        # Create inspection for product
        inspection = Inspection(
            product_id=product.id,
            status="PROCESSING",
        )
        db_session.add(inspection)
        db_session.commit()

        response = client.delete(
            f"/products/{product.id}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "associated" in response.json()["detail"].lower()

    def test_create_product_with_barcode(self, client, auth_headers, db_session):
        """Test creating product with unique barcode."""
        response = client.post(
            "/products/",
            headers=auth_headers,
            json={
                "product_name": "Product with Barcode",
                "barcode": "1234567890123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["barcode"] == "1234567890123"

    def test_create_product_duplicate_barcode(self, client, auth_headers, db_session):
        """Test creating product with duplicate barcode fails."""
        # First product
        client.post(
            "/products/",
            headers=auth_headers,
            json={
                "product_name": "First Product",
                "barcode": "1234567890123",
            },
        )

        # Second product with same barcode
        response = client.post(
            "/products/",
            headers=auth_headers,
            json={
                "product_name": "Second Product",
                "barcode": "1234567890123",
            },
        )

        assert response.status_code == 400
        assert "barcode already exists" in response.json()["detail"].lower()
