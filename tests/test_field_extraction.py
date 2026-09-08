"""Tests for field extraction service."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.field_extractor import FieldExtractorService


class TestFieldExtractor:
    """Test field extraction service."""

    @pytest.fixture
    def extractor(self):
        """Create field extractor instance."""
        return FieldExtractorService()

    def test_extract_mrp(self, extractor):
        """Test MRP extraction."""
        text = "MRP ₹120 inclusive of all taxes"
        result = extractor._extract_mrp(text, [])

        assert result is not None
        assert result["value"] == 120.0
        assert result["currency"] == "INR"

    def test_extract_mrp_variants(self, extractor):
        """Test MRP extraction with various formats."""
        test_cases = [
            ("MRP Rs. 120", 120.0),
            ("MRP INR 120.50", 120.50),
            ("Maximum Retail Price: ₹150", 150.0),
        ]

        for text, expected_value in test_cases:
            result = extractor._extract_mrp(text, [])
            if result:
                assert result["value"] == expected_value

    def test_extract_net_quantity(self, extractor):
        """Test net quantity extraction."""
        text = "Net Qty 500 g"
        result = extractor._extract_net_quantity(text, [])

        assert result is not None
        assert result["value"] == 500.0
        assert result["unit"] == "g"

    def test_extract_net_quantity_kg(self, extractor):
        """Test net quantity extraction with kg."""
        text = "Net Quantity: 1 kg"
        result = extractor._extract_net_quantity(text, [])

        assert result is not None
        assert result["value"] == 1.0
        assert result["unit"] == "kg"

    def test_extract_net_quantity_ml(self, extractor):
        """Test net quantity extraction with ml."""
        text = "Net Qty 250 ml"
        result = extractor._extract_net_quantity(text, [])

        assert result is not None
        assert result["value"] == 250.0
        assert result["unit"] == "ml"

    def test_extract_manufacturer(self, extractor):
        """Test manufacturer extraction."""
        text = "Manufactured by: Test Company Pvt Ltd"
        result = extractor._extract_manufacturer(text)

        assert result is not None
        assert "Test Company" in result["name"]

    def test_extract_date_month_year(self, extractor):
        """Test date extraction in month year format."""
        text = "Mfg. Date: Jan 2024"
        result = extractor._extract_date(text, "manufacturing_date")

        assert result is not None
        assert "Jan" in result.get("month", "")
        assert result.get("year") == 2024

    def test_extract_date_dd_mm_yyyy(self, extractor):
        """Test date extraction in DD/MM/YYYY format."""
        text = "Packing Date: 15/01/2024"
        result = extractor._extract_date(text, "packing_date")

        assert result is not None
        assert result.get("day") == 15
        assert result.get("month_number") == 1
        assert result.get("year") == 2024

    def test_extract_consumer_care_phone(self, extractor):
        """Test consumer care phone extraction."""
        text = "Consumer Care: 18001234567"
        result = extractor._extract_consumer_care(text)

        assert result is not None
        assert result["phone"] == "18001234567"

    def test_extract_consumer_care_email(self, extractor):
        """Test consumer care email extraction."""
        text = "Email: support@testcompany.com"
        result = extractor._extract_consumer_care(text)

        assert result is not None
        assert result["email"] == "support@testcompany.com"

    def test_extract_country_of_origin(self, extractor):
        """Test country of origin extraction."""
        text = "Country of Origin: India"
        result = extractor._extract_country_of_origin(text)

        assert result is not None
        assert result == "India"

    def test_extract_country_of_origin_variants(self, extractor):
        """Test country of origin with different formats."""
        test_cases = [
            ("Made in India", "India"),
            ("Country of manufacture: China", "China"),
        ]

        for text, expected in test_cases:
            result = extractor._extract_country_of_origin(text)
            assert result == expected

    def test_extract_barcode(self, extractor):
        """Test barcode extraction."""
        text = "Barcode: 8901234567890"
        result = extractor._extract_barcode(text)

        assert result is not None
        assert len(result) == 13

    def test_extract_fssai_license(self, extractor):
        """Test FSSAI license extraction."""
        text = "FSSAI License: ABC1234DEF5678G"
        result = extractor._extract_fssai_license(text)

        assert result is not None
        assert len(result) == 14

    def test_normalize_unit(self, extractor):
        """Test unit normalization."""
        test_cases = [
            ("g", "g"),
            ("gm", "g"),
            ("grams", "g"),
            ("kg", "kg"),
            ("KG", "kg"),
            ("ml", "ml"),
            ("mL", "ml"),
            ("L", "L"),
            ("liter", "L"),
            ("litre", "L"),
        ]

        for input_unit, expected in test_cases:
            result = extractor._normalize_unit(input_unit)
            assert result == expected

    def test_extract_all_fields(self, extractor):
        """Test complete field extraction from sample text."""
        ocr_texts = [
            type("OcrTextItem", (), {
                "text": "MRP ₹120 inclusive of all taxes",
                "confidence": 0.95,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
            type("OcrTextItem", (), {
                "text": "Net Qty 500 g",
                "confidence": 0.93,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
            type("OcrTextItem", (), {
                "text": "Manufactured by: Test Company, Mumbai",
                "confidence": 0.88,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
            type("OcrTextItem", (), {
                "text": "Mfg. Date: Jan 2024",
                "confidence": 0.85,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
            type("OcrTextItem", (), {
                "text": "Country of Origin: India",
                "confidence": 0.91,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
        ]

        result = extractor.extract_fields(ocr_texts)

        assert result["mrp"] == 120.0
        assert result["net_quantity_value"] == 500.0
        assert result["net_quantity_unit"] == "g"
        assert result["manufacturer_name"] is not None
        assert result["country_of_origin"] == "India"
