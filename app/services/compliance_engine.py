"""
Compliance Engine

Evaluates extracted fields against legal rules to determine compliance status.

Key principles:
- Missing OCR data does NOT always mean legal failure
- If confidence is too low or image/data is insufficient: MANUAL_REVIEW or NOT_VERIFIED
- Do NOT automatically declare illegal/non-compliant due only to OCR uncertainty
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from app.schemas.compliance import (
    ComplianceCheckResult,
    ComplianceAnalysis,
    CheckStatus,
    OverallStatus,
)
from app.schemas.ocr import OcrTextItem
from app.services.rule_engine import RuleEngine, get_applicable_rules
from app.services.field_extractor import FieldExtractorService


class ComplianceEngine:
    """
    Compliance engine for evaluating extracted fields against legal rules.

    Produces compliance check results with appropriate statuses based on:
    - Field presence
    - Field values
    - Detection confidence
    - Data sufficiency
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50

    # Minimum fields for auto-decision
    MIN_FIELDS_FOR_AUTO_DECISION = 3

    def __init__(self):
        """Initialize compliance engine."""
        self.field_extractor = FieldExtractorService()

    async def analyze_compliance(
        self,
        inspection_id: int,
        extracted_fields: Dict[str, Any],
        ocr_texts: List[OcrTextItem],
        product_category: Optional[str] = None,
        ruleset_version: str = "1.0.0",
        db: Any = None,
    ) -> ComplianceAnalysis:
        """
        Analyze compliance of extracted fields against applicable rules.

        Args:
            inspection_id: ID of the inspection
            extracted_fields: Dictionary of extracted fields
            ocr_texts: List of original OCR text items (for evidence)
            product_category: Category of the product (for rule filtering)
            ruleset_version: Version of the ruleset used
            db: Database session (for fetching rules if needed)

        Returns:
            Complete compliance analysis
        """
        # Get applicable rules
        applicable_rules = get_applicable_rules(
            db=db,
            category=product_category,
            ruleset_version=ruleset_version,
        )

        if not applicable_rules:
            # No rules found - return NOT_VERIFIED
            return ComplianceAnalysis(
                overall_status=CheckStatus.NOT_VERIFIED,
                checks=[],
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                manual_review_checks=0,
                not_applicable_checks=0,
                compliance_percentage=0.0,
                ruleset_version=ruleset_version,
                notes="No applicable rules found for this product category",
                analyzed_at=datetime.utcnow(),
            )

        # Evaluate each rule
        checks = []
        for rule in applicable_rules:
            check_result = self._evaluate_rule(
                rule=rule,
                extracted_fields=extracted_fields,
                ocr_texts=ocr_texts,
                field_extractor=self.field_extractor,
            )
            checks.append(check_result)

        # Calculate statistics
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks if c.status == CheckStatus.PASS)
        failed_checks = sum(1 for c in checks if c.status == CheckStatus.FAIL)
        manual_review_checks = sum(
            1 for c in checks if c.status == CheckStatus.MANUAL_REVIEW
        )
        not_applicable_checks = sum(
            1 for c in checks if c.status == CheckStatus.NOT_APPLICABLE
        )

        # Calculate compliance percentage
        if total_checks > 0:
            compliance_percentage = round(
                (passed_checks / total_checks) * 100, 2
            )
        else:
            compliance_percentage = 0.0

        # Determine overall status
        overall_status = self._determine_overall_status(
            checks=checks,
            compliance_percentage=compliance_percentage,
            extracted_fields=extracted_fields,
        )

        return ComplianceAnalysis(
            overall_status=overall_status,
            checks=checks,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            manual_review_checks=manual_review_checks,
            not_applicable_checks=not_applicable_checks,
            compliance_percentage=compliance_percentage,
            ruleset_version=ruleset_version,
            notes=self._generate_summary_notes(checks, overall_status),
            analyzed_at=datetime.utcnow(),
        )

    def _evaluate_rule(
        self,
        rule: Any,
        extracted_fields: Dict[str, Any],
        ocr_texts: List[OcrTextItem],
        field_extractor: FieldExtractorService,
    ) -> ComplianceCheckResult:
        """
        Evaluate a single rule against extracted fields.

        Args:
            rule: The rule to evaluate
            extracted_fields: Dictionary of extracted fields
            ocr_texts: List of OCR text items for evidence
            field_extractor: Field extractor service instance

        Returns:
            ComplianceCheckResult for the rule
        """
        field_name = rule.field_name
        validation_type = rule.validation_type
        required = rule.required
        severity = rule.severity

        # Get the field value
        field_value = self._get_field_value(field_name, extracted_fields)

        # Check if field is not applicable for this product
        if not self._is_field_applicable(field_name, extracted_fields, rule):
            return ComplianceCheckResult(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                field=field_name,
                status=CheckStatus.NOT_APPLICABLE,
                message=f"Field '{field_name}' is not applicable for this inspection",
                confidence=None,
                evidence=None,
            )

        # If field is required but missing
        if required and field_value is None:
            # Check if we have low confidence OCR (might be present but not detected)
            ocr_confidence = self._get_field_detection_confidence(
                field_name, ocr_texts, field_extractor
            )

            if ocr_confidence is not None and ocr_confidence < self.LOW_CONFIDENCE:
                # Low confidence detection - might be present but OCR couldn't read it
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.MANUAL_REVIEW,
                    message=f"Field '{field_name}' may be present but OCR confidence is too low to verify",
                    confidence=ocr_confidence,
                    evidence="Insufficient OCR confidence to confirm presence",
                )

            # Check if we have enough other fields for reasonable auto-decision
            detected_field_count = self._count_detected_fields(extracted_fields)
            if detected_field_count < self.MIN_FIELDS_FOR_AUTO_DECISION:
                # Not enough data for reasonable decision
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.MANUAL_REVIEW,
                    message=f"Insufficient data to determine presence of '{field_name}'",
                    confidence=None,
                    evidence="Insufficient OCR data for automated determination",
                )

            # Definitely missing
            return ComplianceCheckResult(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                field=field_name,
                status=CheckStatus.FAIL,
                message=f"Required field '{field_name}' not detected",
                confidence=None,
                evidence="Field not found in OCR output",
            )

        # Field present - validate it
        if field_value is not None:
            if validation_type == "required":
                # Just need to be present
                confidence = extracted_fields.get("confidence", 0.0)
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.PASS,
                    message=f"Required declaration '{field_name}' detected",
                    confidence=confidence,
                    evidence=str(field_value),
                )

            elif validation_type == "format":
                # Validate format
                format_valid = self._validate_format(field_name, field_value)
                if format_valid:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.PASS,
                        message=f"Field '{field_name}' format is valid",
                        confidence=0.9,
                        evidence=str(field_value),
                    )
                else:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.FAIL,
                        message=f"Field '{field_name}' has invalid format",
                        confidence=0.9,
                        evidence=str(field_value),
                    )

            elif validation_type == "range":
                # Validate range
                range_valid = self._validate_range(field_name, field_value)
                if range_valid:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.PASS,
                        message=f"Field '{field_name}' value is within acceptable range",
                        confidence=0.9,
                        evidence=str(field_value),
                    )
                else:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.FAIL,
                        message=f"Field '{field_name}' value is out of acceptable range",
                        confidence=0.9,
                        evidence=str(field_value),
                    )

            else:
                # Default: field is present, consider it a pass
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.PASS,
                    message=f"Field '{field_name}' declared",
                    confidence=0.9,
                    evidence=str(field_value),
                )

        # Should not reach here, but default to NOT_VERIFIED
        return ComplianceCheckResult(
            rule_code=rule.rule_code,
            rule_name=rule.rule_name,
            field=field_name,
            status=CheckStatus.NOT_VERIFIED,
            message="Unable to evaluate field",
            confidence=None,
            evidence=None,
        )

    def _get_field_value(self, field_name: str, extracted_fields: Dict) -> Any:
        """Get a field value from extracted fields, handling nested structures."""
        # Direct field lookup
        if field_name in extracted_fields:
            value = extracted_fields[field_name]
            if value is not None:
                return value

        # Handle compound fields
        field_mapping = {
            "consumer_care": ["consumer_care_phone", "consumer_care_email", "consumer_care_address"],
            "manufacturer": ["manufacturer_name", "manufacturer_address"],
            "date_information": ["manufacturing_date", "packing_date"],
        }

        if field_name in field_mapping:
            for subfield in field_mapping[field_name]:
                if extracted_fields.get(subfield):
                    return extracted_fields[subfield]

        return None

    def _get_field_detection_confidence(
        self,
        field_name: str,
        ocr_texts: List[OcrTextItem],
        field_extractor: FieldExtractorService,
    ) -> Optional[float]:
        """Estimate confidence that a field was detected in OCR."""
        # Look for related text in OCR
        field_keywords = {
            "mrp": ["mrp", "maximum retail price", "₹", "rs."],
            "net_quantity": ["net qty", "net quantity", "qty", "quantity"],
            "consumer_care": ["consumer care", "helpline", "customer care", "email"],
            "manufacturer": ["manufacturer", "mfg", "prepared by"],
            "manufacturing_date": ["mfg date", "month/year", "manufacturing date", "best before"],
            "country_of_origin": ["country of origin", "made in"],
        }

        keywords = field_keywords.get(field_name, [field_name.lower()])

        max_confidence = 0.0
        for item in ocr_texts:
            text_lower = item.text.lower()
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Field might be present, use OCR confidence
                    if item.confidence and item.confidence > max_confidence:
                        max_confidence = item.confidence

        return max_confidence if max_confidence > 0 else None

    def _count_detected_fields(self, extracted_fields: Dict) -> int:
        """Count how many fields were actually detected."""
        count = 0
        for key, value in extracted_fields.items():
            if key.startswith("extracted_fields") or key in ["extracted_at", "extraction_method"]:
                continue
            if value is not None and value != "":
                count += 1
        return count

    def _is_field_applicable(
        self,
        field_name: str,
        extracted_fields: Dict,
        rule: Any,
    ) -> bool:
        """Check if a field is applicable for this inspection."""
        # Check rule's applicable_category
        if rule.applicable_category:
            # If categories don't match, might not be applicable
            # For now, we consider all fields applicable unless specifically excluded
            pass

        # Some fields are always applicable
        always_applicable = [
            "mrp",
            "net_quantity",
            "manufacturer",
            "product_name",
        ]

        if field_name in always_applicable:
            return True

        # For optional fields, check if we have any indication they should exist
        return True

    def _validate_format(self, field_name: str, value: Any) -> bool:
        """Validate field format."""
        if value is None:
            return False

        if field_name == "mrp":
            return isinstance(value, (int, float)) and value > 0

        if field_name == "net_quantity_value":
            return isinstance(value, (int, float)) and value > 0

        if field_name in ["manufacturing_date", "packing_date"]:
            if isinstance(value, str):
                # Check for common date patterns
                return bool(
                    re.search(r'\d{4}', value) or
                    re.search(r'[a-zA-Z]{3,9}', value)
                )
            return True

        if field_name == "consumer_care_email":
            if isinstance(value, str):
                return '@' in value and '.' in value
            return False

        if field_name == "consumer_care_phone":
            if isinstance(value, str):
                digits = re.sub(r'\D', '', value)
                return len(digits) >= 10
            return False

        return True

    def _validate_range(self, field_name: str, value: Any) -> bool:
        """Validate field value range."""
        if value is None:
            return False

        if field_name == "mrp":
            # MRP should be reasonable (0 to 1000000 INR)
            return isinstance(value, (int, float)) and 0 < value < 1000000

        return True

    def _determine_overall_status(
        self,
        checks: List[ComplianceCheckResult],
        compliance_percentage: float,
        extracted_fields: Dict,
    ) -> OverallStatus:
        """Determine overall compliance status based on individual checks."""
        has_failures = any(c.status == CheckStatus.FAIL for c in checks)
        has_manual_review = any(c.status == CheckStatus.MANUAL_REVIEW for c in checks)
        has_not_verified = any(c.status == CheckStatus.NOT_VERIFIED for c in checks)
        all_passed = all(c.status == CheckStatus.PASS for c in checks)

        detected_field_count = self._count_detected_fields(extracted_fields)

        # If any critical failures
        if has_failures:
            # Check if failures are due to truly missing required fields
            missing_required = [
                c for c in checks
                if c.status == CheckStatus.FAIL and "not detected" in (c.message or "").lower()
            ]
            if missing_required:
                return OverallStatus.NON_COMPLIANT

        # If manual review needed
        if has_manual_review:
            return OverallStatus.MANUAL_REVIEW

        # If not verified
        if has_not_verified:
            if detected_field_count < self.MIN_FIELDS_FOR_AUTO_DECISION:
                return OverallStatus.MANUAL_REVIEW
            return OverallStatus.MANUAL_REVIEW

        # All passed
        if all_passed:
            return OverallStatus.COMPLIANT

        # Default
        if compliance_percentage >= 80:
            return OverallStatus.COMPLIANT
        elif compliance_percentage >= 50:
            return OverallStatus.MANUAL_REVIEW
        else:
            return OverallStatus.NON_COMPLIANT

    def _generate_summary_notes(
        self,
        checks: List[ComplianceCheckResult],
        overall_status: CheckStatus,
    ) -> str:
        """Generate summary notes for the analysis."""
        failed_checks = [c for c in checks if c.status == CheckStatus.FAIL]
        review_checks = [c for c in checks if c.status == CheckStatus.MANUAL_REVIEW]

        notes = []

        if failed_checks:
            notes.append(f"Found {len(failed_checks)} violation(s):")
            for check in failed_checks:
                notes.append(f"  - {check.rule_code}: {check.message}")

        if review_checks:
            notes.append(f"{len(review_checks)} field(s) require manual review.")

        if not notes:
            notes.append("All checked declarations are present and valid.")

        return " ".join(notes)


# Convenience function
async def analyze_compliance(
    inspection_id: int,
    extracted_fields: Dict[str, Any],
    ocr_texts: List[OcrTextItem],
    product_category: Optional[str] = None,
    ruleset_version: str = "1.0.0",
    db: Any = None,
) -> ComplianceAnalysis:
    """Convenience function for compliance analysis."""
    engine = ComplianceEngine()
    return await engine.analyze_compliance(
        inspection_id=inspection_id,
        extracted_fields=extracted_fields,
        ocr_texts=ocr_texts,
        product_category=product_category,
        ruleset_version=ruleset_version,
        db=db,
    )


# Import re for validation
import re
