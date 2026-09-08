"""Tests for compliance engine."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.compliance_engine import ComplianceEngine, CheckStatus


class TestComplianceEngine:
    """Test compliance engine."""

    @pytest.fixture
    def engine(self):
        """Create compliance engine instance."""
        return ComplianceEngine()

    def test_count_detected_fields(self, engine):
        """Test field counting."""
        fields = {
            "mrp": 120,
            "net_quantity_value": 500,
            "manufacturer_name": "Test Co",
            "extracted_at": "2024-01-01",
            "extraction_method": "regex",
        }

        count = engine._count_detected_fields(fields)
        assert count == 3

    def test_get_field_value_direct(self, engine):
        """Test getting direct field value."""
        fields = {"mrp": 120}
        value = engine._get_field_value("mrp", fields)
        assert value == 120

    def test_get_field_value_missing(self, engine):
        """Test getting missing field value."""
        fields = {"mrp": 120}
        value = engine._get_field_value("nonexistent", fields)
        assert value is None

    def test_get_field_detection_confidence(self, engine):
        """Test detection confidence estimation."""
        ocr_texts = [
            type("OcrTextItem", (), {
                "text": "MRP ₹120",
                "confidence": 0.95,
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
        ]

        confidence = engine._get_field_detection_confidence(
            "mrp", ocr_texts, None
        )

        assert confidence == 0.95

    def test_validate_format_mrp(self, engine):
        """Test MRP format validation."""
        assert engine._validate_format("mrp", 120) is True
        assert engine._validate_format("mrp", 0) is False
        assert engine._validate_format("mrp", -10) is False

    def test_validate_format_email(self, engine):
        """Test email format validation."""
        assert engine._validate_format("consumer_care_email", "test@example.com") is True
        assert engine._validate_format("consumer_care_email", "invalid") is False

    def test_validate_format_phone(self, engine):
        """Test phone format validation."""
        assert engine._validate_format("consumer_care_phone", "1234567890") is True
        assert engine._validate_format("consumer_care_phone", "123") is False

    def test_validate_range_mrp(self, engine):
        """Test MRP range validation."""
        assert engine._validate_range("mrp", 120) is True
        assert engine._validate_range("mrp", 0) is False
        assert engine._validate_range("mrp", 2000000) is False  # Too high

    def test_evaluate_rule_pass(self, engine):
        """Test rule evaluation with passing field."""
        # Create mock rule object
        class MockRule:
            rule_code = "TEST-001"
            rule_name = "Test Rule"
            field_name = "mrp"
            required = True
            validation_type = "required"
            severity = "HIGH"
            applicable_category = None

        rule = MockRule()
        fields = {"mrp": 120}
        ocr_texts = []

        result = engine._evaluate_rule(rule, fields, ocr_texts, None)

        assert result.status == CheckStatus.PASS
        assert "detected" in result.message.lower()

    def test_evaluate_rule_fail_missing_required(self, engine):
        """Test rule evaluation with missing required field."""
        class MockRule:
            rule_code = "TEST-001"
            rule_name = "Test Rule"
            field_name = "mrp"
            required = True
            validation_type = "required"
            severity = "HIGH"
            applicable_category = None

        rule = MockRule()
        fields = {}  # MRP missing
        ocr_texts = []

        result = engine._evaluate_rule(rule, fields, ocr_texts, None)

        assert result.status == CheckStatus.FAIL
        assert "not detected" in result.message.lower()

    def test_evaluate_rule_manual_review_low_confidence(self, engine):
        """Test rule evaluation with low confidence OCR."""
        class MockRule:
            rule_code = "TEST-001"
            rule_name = "Test Rule"
            field_name = "mrp"
            required = True
            validation_type = "required"
            severity = "HIGH"
            applicable_category = None

        rule = MockRule()
        fields = {}  # MRP not extracted
        ocr_texts = [
            type("OcrTextItem", (), {
                "text": "some text without mrp",
                "confidence": 0.4,  # Low confidence
                "bbox": None,
                "image_name": "front.jpg",
                "page_number": 1,
            })(),
        ]

        result = engine._evaluate_rule(rule, fields, ocr_texts, None)

        # With low confidence and insufficient other fields, should be manual review
        assert result.status in [CheckStatus.MANUAL_REVIEW, CheckStatus.NOT_VERIFIED]

    def test_determine_overall_status_compliant(self, engine):
        """Test overall status when all pass."""
        checks = [
            type("Check", (), {"status": CheckStatus.PASS})(),
            type("Check", (), {"status": CheckStatus.PASS})(),
        ]

        status = engine._determine_overall_status(checks, 100.0, {"mrp": 120})
        assert status == CheckStatus.COMPLIANT

    def test_determine_overall_status_non_compliant(self, engine):
        """Test overall status when some fail."""
        checks = [
            type("Check", (), {"status": CheckStatus.PASS})(),
            type("Check", (), {"status": CheckStatus.FAIL})(),
        ]

        status = engine._determine_overall_status(checks, 50.0, {"mrp": 120})
        assert status == CheckStatus.NON_COMPLIANT

    def test_determine_overall_status_manual_review(self, engine):
        """Test overall status when manual review needed."""
        checks = [
            type("Check", (), {"status": CheckStatus.PASS})(),
            type("Check", (), {"status": CheckStatus.MANUAL_REVIEW})(),
        ]

        status = engine._determine_overall_status(checks, 50.0, {"mrp": 120})
        assert status == CheckStatus.MANUAL_REVIEW

    def test_generate_summary_notes_with_failures(self, engine):
        """Test summary notes generation with failures."""
        checks = [
            type("Check", (), {
                "status": CheckStatus.FAIL,
                "rule_code": "LM-MRP-001",
                "message": "MRP not detected"
            })(),
        ]

        notes = engine._generate_summary_notes(checks, CheckStatus.NON_COMPLIANT)
        assert "violation" in notes.lower() or "LM-MRP-001" in notes

    def test_generate_summary_notes_all_pass(self, engine):
        """Test summary notes generation with all passing."""
        checks = [
            type("Check", (), {"status": CheckStatus.PASS})(),
            type("Check", (), {"status": CheckStatus.PASS})(),
        ]

        notes = engine._generate_summary_notes(checks, CheckStatus.COMPLIANT)
        assert "all checked" in notes.lower() or "present" in notes.lower()
