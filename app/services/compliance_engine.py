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
import re

from app.schemas.compliance import (
    ComplianceCheckResult,
    ComplianceAnalysis,
    CheckStatus,
    OverallStatus,
)
from app.schemas.ocr import OcrTextItem
from app.services.rule_engine import get_applicable_rules
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
        """

        applicable_rules = get_applicable_rules(
            db=db,
            category=product_category,
            ruleset_version=ruleset_version,
        )

        if not applicable_rules:
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

        passed_checks = sum(
            1 for c in checks
            if c.status == CheckStatus.PASS
        )

        failed_checks = sum(
            1 for c in checks
            if c.status == CheckStatus.FAIL
        )

        manual_review_checks = sum(
            1 for c in checks
            if c.status == CheckStatus.MANUAL_REVIEW
        )

        not_applicable_checks = sum(
            1 for c in checks
            if c.status == CheckStatus.NOT_APPLICABLE
        )

        # Calculate compliance percentage.
        # IMPORTANT:
        # Manual review and not-applicable checks are excluded from the
        # denominator so that missing OCR evidence does not artificially
        # lower the compliance percentage.
        evaluated_checks = (
            passed_checks
            + failed_checks
        )

        if evaluated_checks > 0:
            compliance_percentage = round(
                (passed_checks / evaluated_checks) * 100,
                2,
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
            notes=self._generate_summary_notes(
                checks,
                overall_status,
            ),
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
        """

        field_name = rule.field_name
        validation_type = rule.validation_type
        required = rule.required

        # Get field value
        field_value = self._get_field_value(
            field_name,
            extracted_fields,
        )

        # Check whether field is applicable
        if not self._is_field_applicable(
            field_name,
            extracted_fields,
            rule,
        ):
            return ComplianceCheckResult(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                field=field_name,
                status=CheckStatus.NOT_APPLICABLE,
                message=(
                    f"Field '{field_name}' is not applicable "
                    "for this inspection"
                ),
                confidence=None,
                evidence=None,
            )

        # Required field is missing
        if required and field_value is None:

            # Check related OCR confidence first
            ocr_confidence = self._get_field_detection_confidence(
                field_name,
                ocr_texts,
                field_extractor,
            )

            if (
                ocr_confidence is not None
                and ocr_confidence < self.LOW_CONFIDENCE
            ):
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.MANUAL_REVIEW,
                    message=(
                        f"Field '{field_name}' may be present but "
                        "OCR confidence is too low to verify"
                    ),
                    confidence=ocr_confidence,
                    evidence=(
                        "Insufficient OCR confidence "
                        "to confirm presence"
                    ),
                )

            # Determine how much usable information was detected
            detected_field_count = self._count_detected_fields(
                extracted_fields
            )

            if detected_field_count < self.MIN_FIELDS_FOR_AUTO_DECISION:
                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.MANUAL_REVIEW,
                    message=(
                        f"Insufficient data to determine presence "
                        f"of '{field_name}'"
                    ),
                    confidence=None,
                    evidence=(
                        "Insufficient OCR data for "
                        "automated determination"
                    ),
                )

            # IMPORTANT:
            # A field not found in one supplied image is NOT proof
            # that the package is legally non-compliant.
            return ComplianceCheckResult(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                field=field_name,
                status=CheckStatus.MANUAL_REVIEW,
                message=(
                    f"Required field '{field_name}' was not detected "
                    "in the supplied image; inspect other package "
                    "views or verify manually."
                ),
                confidence=None,
                evidence=(
                    "Field not found in supplied OCR output"
                ),
            )

        # Field is present
        if field_value is not None:

            # Required declaration
            if validation_type == "required":
                confidence = extracted_fields.get(
                    "confidence",
                    0.0,
                )

                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.PASS,
                    message=(
                        f"Required declaration "
                        f"'{field_name}' detected"
                    ),
                    confidence=confidence,
                    evidence=str(field_value),
                )

            # Format validation
            elif validation_type == "format":

                format_valid = self._validate_format(
                    field_name,
                    field_value,
                )

                if format_valid:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.PASS,
                        message=(
                            f"Field '{field_name}' "
                            "format is valid"
                        ),
                        confidence=0.9,
                        evidence=str(field_value),
                    )

                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.FAIL,
                    message=(
                        f"Field '{field_name}' "
                        "has invalid format"
                    ),
                    confidence=0.9,
                    evidence=str(field_value),
                )

            # Range validation
            elif validation_type == "range":

                range_valid = self._validate_range(
                    field_name,
                    field_value,
                )

                if range_valid:
                    return ComplianceCheckResult(
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        field=field_name,
                        status=CheckStatus.PASS,
                        message=(
                            f"Field '{field_name}' value "
                            "is within acceptable range"
                        ),
                        confidence=0.9,
                        evidence=str(field_value),
                    )

                return ComplianceCheckResult(
                    rule_code=rule.rule_code,
                    rule_name=rule.rule_name,
                    field=field_name,
                    status=CheckStatus.FAIL,
                    message=(
                        f"Field '{field_name}' value "
                        "is out of acceptable range"
                    ),
                    confidence=0.9,
                    evidence=str(field_value),
                )

            # Unknown validation type
            return ComplianceCheckResult(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                field=field_name,
                status=CheckStatus.PASS,
                message=f"Field '{field_name}' declared",
                confidence=0.9,
                evidence=str(field_value),
            )

        # Fallback
        return ComplianceCheckResult(
            rule_code=rule.rule_code,
            rule_name=rule.rule_name,
            field=field_name,
            status=CheckStatus.NOT_VERIFIED,
            message="Unable to evaluate field",
            confidence=None,
            evidence=None,
        )

    def _get_field_value(
        self,
        field_name: str,
        extracted_fields: Dict,
    ) -> Any:
        """Get a field value, including compound fields."""

        # Direct field lookup
        if field_name in extracted_fields:
            value = extracted_fields[field_name]

            if value is not None:
                return value

        # Compound fields
        field_mapping = {
            "consumer_care": [
                "consumer_care_phone",
                "consumer_care_email",
                "consumer_care_address",
            ],
            "manufacturer": [
                "manufacturer_name",
                "manufacturer_address",
            ],
            "date_information": [
                "manufacturing_date",
                "packing_date",
            ],
        }

        if field_name in field_mapping:
            for subfield in field_mapping[field_name]:
                value = extracted_fields.get(subfield)

                if value:
                    return value

        return None

    def _get_field_detection_confidence(
        self,
        field_name: str,
        ocr_texts: List[OcrTextItem],
        field_extractor: FieldExtractorService,
    ) -> Optional[float]:
        """Estimate OCR confidence related to a field."""

        field_keywords = {
            "mrp": [
                "mrp",
                "maximum retail price",
                "₹",
                "rs.",
            ],
            "net_quantity": [
                "net qty",
                "net quantity",
                "qty",
                "quantity",
            ],
            "net_quantity_value": [
                "net qty",
                "net quantity",
                "qty",
                "quantity",
            ],
            "consumer_care": [
                "consumer care",
                "helpline",
                "customer care",
                "email",
            ],
            "consumer_care_phone": [
                "consumer care",
                "helpline",
                "customer care",
                "phone",
                "contact",
            ],
            "consumer_care_email": [
                "consumer care",
                "customer care",
                "email",
                "@",
            ],
            "manufacturer": [
                "manufacturer",
                "mfg",
                "prepared by",
                "manufactured by",
            ],
            "manufacturer_address": [
                "manufacturer",
                "manufactured by",
                "address",
            ],
            "manufacturing_date": [
                "mfg date",
                "month/year",
                "manufacturing date",
                "date of manufacture",
            ],
            "country_of_origin": [
                "country of origin",
                "made in",
            ],
            "product_name": [
                "product name",
                "name of product",
                "commodity",
            ],
        }

        keywords = field_keywords.get(
            field_name,
            [field_name.lower()],
        )

        max_confidence = 0.0

        for item in ocr_texts:
            text_lower = item.text.lower()

            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if (
                        item.confidence is not None
                        and item.confidence > max_confidence
                    ):
                        max_confidence = item.confidence

        return (
            max_confidence
            if max_confidence > 0
            else None
        )

    def _count_detected_fields(
        self,
        extracted_fields: Dict,
    ) -> int:
        """Count actually detected fields."""

        count = 0

        ignored_keys = {
            "extracted_fields",
            "extracted_at",
            "extraction_method",
        }

        for key, value in extracted_fields.items():

            if key in ignored_keys:
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
        """Check whether a field is applicable."""

        # Product category logic can be extended later.
        # For now, explicitly required package declarations
        # remain applicable.

        always_applicable = [
            "mrp",
            "net_quantity",
            "net_quantity_value",
            "manufacturer",
            "manufacturer_address",
            "product_name",
        ]

        if field_name in always_applicable:
            return True

        return True

    def _validate_format(
        self,
        field_name: str,
        value: Any,
    ) -> bool:
        """Validate field format."""

        if value is None:
            return False

        if field_name == "mrp":
            return (
                isinstance(value, (int, float))
                and value > 0
            )

        if field_name == "net_quantity_value":
            return (
                isinstance(value, (int, float))
                and value > 0
            )

        if field_name in [
            "manufacturing_date",
            "packing_date",
            "use_by",
            "expiry_date",
        ]:
            if isinstance(value, str):
                return bool(
                    re.search(r"\d{4}", value)
                    or re.search(
                        r"[a-zA-Z]{3,9}",
                        value,
                    )
                )

            return True

        if field_name == "consumer_care_email":
            if isinstance(value, str):
                return (
                    "@" in value
                    and "." in value
                )

            return False

        if field_name == "consumer_care_phone":
            if isinstance(value, str):
                digits = re.sub(
                    r"\D",
                    "",
                    value,
                )
                return len(digits) >= 10

            return False

        return True

    def _validate_range(
        self,
        field_name: str,
        value: Any,
    ) -> bool:
        """Validate field range."""

        if value is None:
            return False

        if field_name == "mrp":
            return (
                isinstance(value, (int, float))
                and 0 < value < 1000000
            )

        if field_name == "net_quantity_value":
            return (
                isinstance(value, (int, float))
                and value > 0
            )

        return True

    def _determine_overall_status(
        self,
        checks: List[ComplianceCheckResult],
        compliance_percentage: float,
        extracted_fields: Dict,
    ) -> OverallStatus:
        """Determine the overall compliance status."""

        has_failures = any(
            c.status == CheckStatus.FAIL
            for c in checks
        )

        has_manual_review = any(
            c.status == CheckStatus.MANUAL_REVIEW
            for c in checks
        )

        has_not_verified = any(
            c.status == CheckStatus.NOT_VERIFIED
            for c in checks
        )

        all_passed = all(
            c.status in {
                CheckStatus.PASS,
                CheckStatus.NOT_APPLICABLE,
            }
            for c in checks
        )

        # Confirmed rule failures remain non-compliant.
        if has_failures:
            return OverallStatus.NON_COMPLIANT

        # Missing/insufficient evidence requires human review.
        if has_manual_review:
            return OverallStatus.MANUAL_REVIEW

        if has_not_verified:
            return OverallStatus.MANUAL_REVIEW

        if all_passed:
            return OverallStatus.COMPLIANT

        if compliance_percentage >= 80:
            return OverallStatus.COMPLIANT

        if compliance_percentage >= 50:
            return OverallStatus.MANUAL_REVIEW

        return OverallStatus.NON_COMPLIANT

    def _generate_summary_notes(
        self,
        checks: List[ComplianceCheckResult],
        overall_status: CheckStatus,
    ) -> str:
        """Generate summary notes."""

        failed_checks = [
            c for c in checks
            if c.status == CheckStatus.FAIL
        ]

        review_checks = [
            c for c in checks
            if c.status == CheckStatus.MANUAL_REVIEW
        ]

        notes = []

        if failed_checks:
            notes.append(
                f"Found {len(failed_checks)} confirmed "
                "compliance issue(s):"
            )

            for check in failed_checks:
                notes.append(
                    f"  - {check.rule_code}: "
                    f"{check.message}"
                )

        if review_checks:
            notes.append(
                f"{len(review_checks)} field(s) "
                "require manual review."
            )

        if not notes:
            notes.append(
                "All evaluated declarations are "
                "present and valid."
            )

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