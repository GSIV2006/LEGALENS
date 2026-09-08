"""Tests for OCR-related functionality."""
import pytest


class TestOcrDataSubmission:
    """Test OCR data submission."""

    def test_ocr_data_format(self, client, auth_headers, db_session, product):
        """Test OCR data with expected format."""
        # Create inspection
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        # Submit OCR data in expected format
        response = client.post(
            f"/inspections/{inspection_id}/ocr-data",
            headers=auth_headers,
            json={
                "texts": [
                    {
                        "text": "MRP ₹120",
                        "confidence": 0.95,
                        "bbox": [[10, 20], [300, 20], [300, 50], [10, 50]],
                        "image_name": "front.jpg",
                        "page_number": 1,
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


class TestOcrRunMock:
    """Test mock OCR running."""

    def test_run_ocr_no_images(self, client, auth_headers, db_session, product):
        """Test running OCR with no images."""
        # Create inspection without images
        create_response = client.post(
            "/inspections/",
            headers=auth_headers,
            json={
                "product_id": product.id,
            },
        )
        inspection_id = create_response.json()["id"]

        response = client.post(
            f"/inspections/{inspection_id}/run-ocr",
            headers=auth_headers,
        )

        # Should fail because no images
        assert response.status_code == 400
        assert "no images" in response.json()["detail"].lower()
