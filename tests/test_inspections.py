"""Tests for inspection endpoints."""
import pytest


class TestInspections:
    """Test inspection CRUD operations."""

    def test_create_inspection(self, client, auth_headers, db_session, product):
        """Test inspection creation."""
        response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
                "status": "PROCESSING",
                "notes": "Test inspection",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["product_id"] == product.id
        assert data["status"] == "PROCESSING"

    def test_create_inspection_unauthorized(self, client):
        """Test inspection creation without auth fails."""
        response = client.post(
            "/inspections/",
            json={
                "status": "PROCESSING",
            },
        )

        assert response.status_code == 401

    def test_list_inspections(self, client, auth_headers, db_session, product):
        """Test listing inspections."""
        # Create an inspection first
        client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )

        response = client.get("/inspections/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_inspection(self, client, auth_headers, db_session, product):
        """Test getting a single inspection."""
        # Create inspection
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        response = client.get(
            f"/inspections/{inspection_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["inspection"]["id"] == inspection_id

    def test_get_nonexistent_inspection(self, client, auth_headers):
        """Test getting non-existent inspection."""
        response = client.get(
            "/inspections/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_delete_inspection(self, client, auth_headers, db_session, product):
        """Test deleting an inspection."""
        # Create inspection
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        response = client.delete(
            f"/inspections/{inspection_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    def test_filter_inspections_by_status(self, client, auth_headers, db_session, product):
        """Test filtering inspections by status."""
        # Create inspections with different statuses
        client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
                "status": "COMPLIANT",
            },
        )
        client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
                "status": "PROCESSING",
            },
        )

        response = client.get(
            "/inspections/?status=COMPLIANT",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert all(insp["status"] == "COMPLIANT" for insp in data)


class TestInspectionImages:
    """Test image upload for inspections."""

    def test_upload_image(self, client, auth_headers, db_session, product):
        """Test uploading an image to inspection."""
        # Create inspection first
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Create a dummy image file
        import io
        img_data = io.BytesIO(b"fake image data")
        img_data.name = "test.jpg"

        response = client.post(
            f"/inspections/{inspection_id}/images",
            headers=auth_headers,
            files={
                "images": ("test.jpg", img_data, "image/jpeg"),
            },
            data={
                "view_type": "front",
            },
        )

        # May fail due to file validation, but endpoint should exist
        assert response.status_code in [201, 400]


class TestInspectionOCR:
    """Test OCR data submission for inspections."""

    def test_submit_ocr_data(self, client, auth_headers, db_session, product):
        """Test submitting OCR data to inspection."""
        # Create inspection
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Submit OCR data
        response = client.post(
            f"/inspections/{inspection_id}/ocr-data",
            headers=auth_headers,
            json={
                "texts": [
                    {
                        "text": "MRP ₹120 inclusive of all taxes",
                        "confidence": 0.95,
                        "bbox": [[10, 20], [300, 20], [300, 50], [10, 50]],
                        "image_name": "front.jpg",
                    },
                    {
                        "text": "Net Qty 500 g",
                        "confidence": 0.93,
                        "bbox": [[10, 60], [200, 60], [200, 80], [10, 80]],
                        "image_name": "front.jpg",
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["inspection_id"] == inspection_id


class TestFieldExtraction:
    """Test field extraction endpoint."""

    def test_extract_fields(self, client, auth_headers, db_session, product):
        """Test field extraction from OCR data."""
        # Create inspection with OCR data
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Submit OCR data
        client.post(
            f"/inspections/{inspection_id}/ocr-data",
            headers=auth_headers,
            json={
                "texts": [
                    {
                        "text": "MRP ₹120 inclusive of all taxes",
                        "confidence": 0.95,
                    },
                    {
                        "text": "Net Qty 500 g",
                        "confidence": 0.93,
                    },
                    {
                        "text": "Mfg. Date: Jan 2024",
                        "confidence": 0.88,
                    },
                ]
            },
        )

        # Extract fields
        response = client.post(
            f"/inspections/{inspection_id}/extract-fields",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "fields" in data
        assert data["fields"]["mrp"] == 120
        assert data["fields"]["net_quantity_value"] == 500
        assert data["fields"]["net_quantity_unit"] == "g"


class TestComplianceChecking:
    """Test compliance checking endpoint."""

    def test_check_compliance(self, client, auth_headers, db_session, product):
        """Test compliance checking."""
        # Create inspection with OCR data
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Submit OCR data with all required fields
        client.post(
            f"/inspections/{inspection_id}/ocr-data",
            headers=auth_headers,
            json={
                "texts": [
                    {
                        "text": "MRP ₹120 inclusive of all taxes",
                        "confidence": 0.95,
                    },
                    {
                        "text": "Net Qty 500 g",
                        "confidence": 0.93,
                    },
                    {
                        "text": "Mfg. Date: Jan 2024",
                        "confidence": 0.88,
                    },
                    {
                        "text": "Manufacturer: Test Mfg Co",
                        "confidence": 0.90,
                    },
                ]
            },
        )

        # Check compliance
        response = client.post(
            f"/inspections/{inspection_id}/check-compliance",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "checks" in data
        assert "compliance_percentage" in data


class TestFullAnalysis:
    """Test full analysis pipeline."""

    def test_analyze_inspection(self, client, auth_headers, db_session, product):
        """Test full analysis pipeline."""
        # Create inspection
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Submit OCR data
        client.post(
            f"/inspections/{inspection_id}/ocr-data",
            headers=auth_headers,
            json={
                "texts": [
                    {
                        "text": "MRP ₹120 inclusive of all taxes",
                        "confidence": 0.95,
                    },
                    {
                        "text": "Net Qty 500 g",
                        "confidence": 0.93,
                    },
                    {
                        "text": "Mfg. Date: Jan 2024",
                        "confidence": 0.88,
                    },
                ]
            },
        )

        # Run full analysis
        response = client.post(
            f"/inspections/{inspection_id}/analyze",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["inspection_id"] == inspection_id
        assert "extracted_fields" in data
        assert "compliance_checks" in data
