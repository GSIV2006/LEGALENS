"""
LEGALENS Verification Service

Generic semantic verification layer for OCR-extracted package fields.

Purpose:
- Validate whether an OCR candidate actually belongs to the requested field.
- Use surrounding OCR text, spatial proximity, units, labels and field semantics.
- Reject obvious false associations.
- Preserve uncertainty instead of inventing values.
- Provide explainable verification evidence.

This service is intentionally deterministic for the current prototype.
A learned/LLM verifier can be added later without changing its interface.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class VerificationService:

    # ============================================================
    # Public API
    # ============================================================

    def verify_field(
        self,
        field: str,
        candidate: Optional[Dict[str, Any]],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:
        """
        Verify one extracted field against the complete OCR evidence.

        Returns:
            {
                "field": ...,
                "value": ...,
                "verified": bool,
                "decision": "VERIFIED" | "REVIEW" | "REJECT",
                "confidence": float,
                "reason": ...,
                "evidence": [...],
            }
        """

        if not candidate:
            return {
                "field": field,
                "value": None,
                "verified": False,
                "decision": "REVIEW",
                "confidence": 0.0,
                "reason": "No OCR candidate was supplied.",
                "evidence": [],
            }

        value = self._candidate_value(candidate)

        if not value:
            return {
                "field": field,
                "value": None,
                "verified": False,
                "decision": "REVIEW",
                "confidence": 0.0,
                "reason": "OCR candidate contained no usable value.",
                "evidence": [],
            }

        normalized_field = self._normalize_field(field)

        if normalized_field == "mrp":
            return self._verify_mrp(
                candidate,
                ocr_items,
            )

        if normalized_field in {
            "net_quantity",
            "net_quantity_value",
        }:
            return self._verify_quantity(
                candidate,
                ocr_items,
            )

        if normalized_field in {
            "manufacturing_date",
            "packing_date",
            "use_by",
            "expiry_date",
            "best_before",
        }:
            return self._verify_date(
                normalized_field,
                candidate,
                ocr_items,
            )

        if normalized_field in {
            "manufacturer",
            "manufacturer_name",
            "packer",
            "importer",
        }:
            return self._verify_party(
                normalized_field,
                candidate,
                ocr_items,
            )

        if normalized_field == "consumer_care_phone":
            return self._verify_phone(
                candidate,
                ocr_items,
            )

        if normalized_field == "consumer_care_email":
            return self._verify_email(
                candidate,
                ocr_items,
            )

        if normalized_field == "barcode":
            return self._verify_barcode(
                candidate,
            )

        if normalized_field == "fssai_license":
            return self._verify_license(
                normalized_field,
                candidate,
                ocr_items,
            )

        if normalized_field == "manufacturing_license":
            return self._verify_license(
                normalized_field,
                candidate,
                ocr_items,
            )

        if normalized_field == "country_of_origin":
            return self._verify_country(
                candidate,
                ocr_items,
            )

        if normalized_field == "product_name":
            return self._verify_product_name(
                candidate,
                ocr_items,
            )

        # Generic fallback.
        confidence = float(
            candidate.get("confidence", 0.0)
        )

        if confidence >= 0.90:
            decision = "VERIFIED"
            verified = True
        elif confidence >= 0.70:
            decision = "REVIEW"
            verified = False
        else:
            decision = "REVIEW"
            verified = False

        return {
            "field": field,
            "value": value,
            "verified": verified,
            "decision": decision,
            "confidence": round(
                confidence,
                3,
            ),
            "reason": (
                "Candidate accepted by confidence-based "
                "generic verification."
            ),
            "evidence": [],
        }

    def verify_all(
        self,
        extracted_fields: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:
        """
        Verify all extracted field candidates.

        Does not destroy the original candidate data.
        Results are placed under 'verification'.
        """

        verification = {}

        for field, candidate in (
            extracted_fields or {}
        ).items():

            # Skip non-field metadata.
            if field in {
                "confidence",
                "extraction_method",
                "extracted_at",
            }:
                continue

            if not isinstance(candidate, dict):
                continue

            verification[field] = self.verify_field(
                field,
                candidate,
                ocr_items,
            )

        return verification

    # ============================================================
    # MRP
    # ============================================================

    def _verify_mrp(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)
        text = str(value)

        # MRP should represent money, not weight/count.
        if re.search(
            r"(?:kg|kgs|g|gm|gms|mg|ml|l|ltr|litre|liter)\b",
            text,
            re.IGNORECASE,
        ):
            return self._reject(
                "mrp",
                value,
                "Candidate contains a quantity unit, so it is not a valid MRP value.",
                candidate,
            )

        # Generic monetary patterns.
        money_match = re.search(
            r"(?:₹|rs\.?|inr)?\s*"
            r"(\d{1,7}(?:[.,]\d{1,2})?)",
            text,
            re.IGNORECASE,
        )

        if not money_match:
            return self._review(
                "mrp",
                value,
                "Candidate does not contain a clear monetary amount.",
                candidate,
            )

        amount = self._to_float(
            money_match.group(1)
        )

        if amount is None or amount <= 0:
            return self._reject(
                "mrp",
                value,
                "MRP amount is not a valid positive monetary value.",
                candidate,
            )

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=220,
        )

        mrp_label = self._find_nearby_label(
            nearby,
            [
                "mrp",
                "m.r.p",
                "maximum retail price",
                "retail price",
            ],
        )

        nutrition_context = self._has_nearby_context(
            nearby,
            [
                "carbohydrate",
                "protein",
                "energy",
                "fat",
                "sugar",
                "sodium",
                "nutrition",
                "nutritional information",
            ],
        )

        if nutrition_context and not mrp_label:
            return self._reject(
                "mrp",
                value,
                "Candidate is associated with a nutrition declaration rather than an MRP declaration.",
                candidate,
            )

        confidence = float(
            candidate.get("confidence", 0.0)
        )

        if mrp_label:
            confidence = min(
                0.99,
                confidence + 0.10,
            )

            return {
                "field": "mrp",
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    confidence,
                    3,
                ),
                "reason": (
                    "Candidate is a valid monetary amount "
                    "and is spatially associated with an MRP label."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                    if self._contains_any(
                        self._item_text(x),
                        [
                            "mrp",
                            "m.r.p",
                            "maximum retail price",
                            "retail price",
                        ],
                    )
                ],
            }

        if confidence >= 0.95:
            return self._review(
                "mrp",
                value,
                "Monetary candidate is plausible, but no nearby MRP label was confidently identified.",
                candidate,
            )

        return self._review(
            "mrp",
            value,
            "MRP candidate lacks sufficient semantic evidence.",
            candidate,
        )

    # ============================================================
    # Quantity
    # ============================================================

    def _verify_quantity(
        self,
        candidate: Dict[str, Any],
        context: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Verify net quantity using the human-readable display value,
        while retaining numeric value/unit separately.
        """

        context = context or []

        # IMPORTANT:
        # Field extractor stores:
        #   value   -> 80.0
        #   unit    -> "g"
        #   display -> "80 g"
        #
        # Verification must inspect display, not only numeric value.

        display = str(
            candidate.get("display")
            or candidate.get("raw_text")
            or ""
        ).strip()

        numeric_value = candidate.get("value")
        unit = str(candidate.get("unit") or "").strip().lower()

        # If display is missing, reconstruct it.
        if not display and numeric_value is not None and unit:
            display = f"{numeric_value} {unit}"

        quantity_pattern = re.compile(
            r"(?<!\d)"
            r"(\d+(?:[.,]\d+)?)"
            r"\s*"
            r"(kg|kgs|g|gm|gms|mg|ml|l|ltr|litre|litres|cl|"
            r"pcs?|pieces?|units?|items?|counts?|"
            r"condoms?|tablets?|capsules?|bottles?|packs?|"
            r"boxes?|sachets?|pouches?|strips?|rolls?)"
            r"\b",
            re.IGNORECASE,
        )

        match = quantity_pattern.search(display)

        if not match:
            return {
                "field": "net_quantity",
                "value": numeric_value,
                "verified": False,
                "decision": "REVIEW",
                "confidence": float(
                    candidate.get("confidence") or 0.0
                ),
                "reason": (
                    "Candidate does not contain a recognizable "
                    "weight or volume unit."
                ),
                "evidence": [],
            }

        extracted_value = float(
            match.group(1).replace(",", ".")
        )

        extracted_unit = match.group(2).lower()

        unit_map = {
            "kgs": "kg",
            "gm": "g",
            "gms": "g",
            "ltr": "l",
            "litre": "l",
            "litres": "l",
        }

        extracted_unit = unit_map.get(
            extracted_unit,
            extracted_unit,
        )

        # Find nearby NETWT / NET QTY evidence.
        label_pattern = re.compile(
            r"\bnet\s*(?:wt\.?|weight|qty\.?|quantity)\b",
            re.IGNORECASE,
        )

        evidence = []

        for item in context:
            item_text = str(
                getattr(item, "text", "") or ""
            ).strip()

            if label_pattern.search(item_text):
                evidence.append(
                    {
                        "text": item_text,
                        "confidence": float(
                            getattr(
                                item,
                                "confidence",
                                None,
                            )
                            or 0.0
                        ),
                    }
                )

        confidence = float(
            candidate.get("confidence") or 0.0
        )

        if evidence:
            confidence = min(
                0.99,
                max(confidence, 0.95),
            )

            return {
                "field": "net_quantity",
                "value": extracted_value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": confidence,
                "reason": (
                    f"Quantity '{display}' contains a valid "
                    "weight/volume unit and is supported by "
                    "a nearby net-quantity declaration."
                ),
                "evidence": evidence,
            }

        # A valid quantity without an explicit NETWT label is still
        # plausible, but should remain reviewable.
        return {
            "field": "net_quantity",
            "value": extracted_value,
            "verified": False,
            "decision": "REVIEW",
            "confidence": confidence,
            "reason": (
                f"Quantity '{display}' has a valid unit, "
                "but no nearby net-quantity declaration label "
                "was detected."
            ),
            "evidence": [],
        }


    def _verify_date(
        self,
        field: str,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=240,
        )

        label_map = {
            "manufacturing_date": [
                "mfg",
                "mfd",
                "manufactured",
                "manufacturing",
                "date of manufacture",
                "mfg date",
                "mfg. date",
            ],
            "packing_date": [
                "pkd",
                "packed on",
                "packing",
                "date of packing",
                "date of pack",
            ],
            "use_by": [
                "use by",
                "use-by",
                "expiry",
                "expires",
            ],
            "expiry_date": [
                "expiry",
                "expires",
                "use by",
            ],
            "best_before": [
                "best before",
                "best-before",
            ],
        }

        labels = label_map.get(
            field,
            [],
        )

        label_found = self._find_nearby_label(
            nearby,
            labels,
        )

        duration_text = None

        if field == "best_before":
            duration_text = self._find_best_before_duration(
                nearby
            )

            if duration_text:
                return {
                    "field": field,
                    "value": value,
                    "verified": True,
                    "decision": "VERIFIED",
                    "confidence": round(
                        min(
                            0.99,
                            float(
                                candidate.get(
                                    "confidence",
                                    0.0,
                                )
                            )
                            + 0.08,
                        ),
                        3,
                    ),
                    "reason": (
                        "Best-before declaration is associated "
                        "with a recognized duration expression."
                    ),
                    "duration_expression": duration_text,
                    "evidence": [
                        self._evidence_text(x)
                        for x in nearby
                    ],
                }

        confidence = float(
            candidate.get("confidence", 0.0)
        )

        if label_found:
            confidence = min(
                0.99,
                confidence + 0.10,
            )

            return {
                "field": field,
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    confidence,
                    3,
                ),
                "reason": (
                    "Date candidate is associated with "
                    "the corresponding package-date declaration."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                ],
            }

        if confidence >= 0.90:
            return self._review(
                field,
                value,
                "Date candidate is plausible but the expected declaration label was not confidently found nearby.",
                candidate,
            )

        return self._review(
            field,
            value,
            "Date candidate lacks sufficient semantic evidence.",
            candidate,
        )

    # ============================================================
    # Manufacturer / Packer / Importer
    # ============================================================

    def _verify_party(
        self,
        field: str,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=280,
        )

        label_map = {
            "manufacturer": [
                "manufacturer",
                "manufactured by",
                "manufactured for",
                "mfg",
                "made by",
                "prepared by",
            ],
            "manufacturer_name": [
                "manufacturer",
                "manufactured by",
                "manufactured for",
                "mfg",
                "made by",
                "prepared by",
            ],
            "packer": [
                "packer",
                "packed by",
                "packaged by",
            ],
            "importer": [
                "importer",
                "imported by",
                "imported for",
            ],
        }

        labels = label_map.get(
            field,
            [],
        )

        label_found = self._find_nearby_label(
            nearby,
            labels,
        )

        if not label_found:
            return self._review(
                field,
                value,
                "Party name candidate has no sufficiently strong nearby party declaration label.",
                candidate,
            )

        confidence = min(
            0.99,
            float(
                candidate.get(
                    "confidence",
                    0.0,
                )
            )
            + 0.10,
        )

        return {
            "field": field,
            "value": value,
            "verified": True,
            "decision": "VERIFIED",
            "confidence": round(
                confidence,
                3,
            ),
            "reason": (
                "Party name is associated with the expected "
                "manufacturer/packer/importer declaration."
            ),
            "evidence": [
                self._evidence_text(x)
                for x in nearby
            ],
        }

    # ============================================================
    # Consumer care
    # ============================================================

    def _verify_phone(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        if len(digits) < 7 or len(digits) > 15:
            return self._reject(
                "consumer_care_phone",
                value,
                "Candidate is not a plausible telephone number.",
                candidate,
            )

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=260,
        )

        context = self._has_nearby_context(
            nearby,
            [
                "customer care",
                "consumer care",
                "contact",
                "helpline",
                "phone",
                "tel",
            ],
        )

        if context:
            return {
                "field": "consumer_care_phone",
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    min(
                        0.99,
                        float(
                            candidate.get(
                                "confidence",
                                0.0,
                            )
                        )
                        + 0.08,
                    ),
                    3,
                ),
                "reason": (
                    "Phone number is plausible and appears "
                    "in consumer-care/contact context."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                ],
            }

        return self._review(
            "consumer_care_phone",
            value,
            "Phone number is valid-looking but consumer-care context was not confidently established.",
            candidate,
        )

    def _verify_email(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        if not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            str(value),
        ):
            return self._reject(
                "consumer_care_email",
                value,
                "Candidate is not a valid-looking email address.",
                candidate,
            )

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=260,
        )

        context = self._has_nearby_context(
            nearby,
            [
                "customer care",
                "consumer care",
                "email",
                "contact",
            ],
        )

        if context:
            return {
                "field": "consumer_care_email",
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    min(
                        0.99,
                        float(
                            candidate.get(
                                "confidence",
                                0.0,
                            )
                        )
                        + 0.08,
                    ),
                    3,
                ),
                "reason": (
                    "Email is syntactically valid and appears "
                    "in consumer-care/contact context."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                ],
            }

        return self._review(
            "consumer_care_email",
            value,
            "Email is valid-looking but consumer-care context was not confidently established.",
            candidate,
        )

    # ============================================================
    # Barcode
    # ============================================================

    def _verify_barcode(
        self,
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        valid_lengths = {
            8,
            12,
            13,
            14,
        }

        if len(digits) not in valid_lengths:
            return self._review(
                "barcode",
                value,
                "Barcode candidate has an unusual digit length.",
                candidate,
            )

        confidence = float(
            candidate.get(
                "confidence",
                0.0,
            )
        )

        if confidence >= 0.85:
            return {
                "field": "barcode",
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    confidence,
                    3,
                ),
                "reason": (
                    "Barcode candidate has a recognized "
                    "numeric barcode length."
                ),
                "evidence": [],
            }

        return self._review(
            "barcode",
            value,
            "Barcode format is plausible but OCR confidence is insufficient.",
            candidate,
        )

    # ============================================================
    # Licenses
    # ============================================================

    def _verify_license(
        self,
        field: str,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        compact = re.sub(
            r"[^A-Za-z0-9]",
            "",
            str(value),
        )

        if len(compact) < 6:
            return self._review(
                field,
                value,
                "License candidate is too short to verify reliably.",
                candidate,
            )

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=260,
        )

        label_found = self._has_nearby_context(
            nearby,
            [
                "lic no",
                "license",
                "licence",
                "lic.",
                "fssai",
            ],
        )

        if label_found:
            return {
                "field": field,
                "value": value,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    min(
                        0.99,
                        float(
                            candidate.get(
                                "confidence",
                                0.0,
                            )
                        )
                        + 0.08,
                    ),
                    3,
                ),
                "reason": (
                    "License candidate is associated with "
                    "an explicit license/FSSAI context."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                ],
            }

        return self._review(
            field,
            value,
            "License candidate lacks a sufficiently strong nearby license label.",
            candidate,
        )

    # ============================================================
    # Country
    # ============================================================

    def _verify_country(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)

        text = str(value).strip()

        country_match = bool(
            re.search(
                r"\bindia\b",
                text,
                re.IGNORECASE,
            )
        )

        nearby = self._nearby_items(
            candidate,
            ocr_items,
            radius=280,
        )

        context = self._has_nearby_context(
            nearby,
            [
                "product of",
                "made in",
                "country of origin",
                "origin",
                "manufactured in",
            ],
        )

        if country_match and context:
            return {
                "field": "country_of_origin",
                "value": "India",
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    min(
                        0.99,
                        float(
                            candidate.get(
                                "confidence",
                                0.0,
                            )
                        )
                        + 0.08,
                    ),
                    3,
                ),
                "reason": (
                    "Country value is explicitly associated "
                    "with an origin declaration."
                ),
                "evidence": [
                    self._evidence_text(x)
                    for x in nearby
                ],
            }

        return self._review(
            "country_of_origin",
            value,
            "Country candidate lacks sufficient explicit origin evidence.",
            candidate,
        )

    # ============================================================
    # Product name
    # ============================================================

    def _verify_product_name(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
    ) -> Dict[str, Any]:

        value = self._candidate_value(candidate)
        text = str(value).strip()

        # Strong rejection of obvious non-product text.
        bad_terms = [
            "ingredients",
            "net wt",
            "net weight",
            "batch",
            "mrp",
            "fssai",
            "customer care",
            "consumer care",
            "email",
            "phone",
            "packed by",
            "packaged by",
            "manufactured by",
            "manufactured for",
            "best before",
            "use by",
            "lic no",
            "license",
            "road",
            "cross road",
            "estate",
            "nagar",
            "mumbai",
            "maharashtra",
            "karnataka",
            "@",
        ]

        lower = text.lower()

        if any(
            term in lower
            for term in bad_terms
        ):
            return self._reject(
                "product_name",
                value,
                "Candidate resembles a declaration, address, contact field or other non-product text.",
                candidate,
            )

        width, height = self._bbox_dimensions(
            candidate.get("bbox")
        )

        # Reject strongly vertical OCR artifacts.
        if (
            width > 0
            and height > 0
            and height > width * 2.5
        ):
            return self._reject(
                "product_name",
                value,
                "Candidate is strongly vertically oriented and is likely a rotated OCR artifact.",
                candidate,
            )

        word_count = len(text.split())

        if word_count == 0:
            return self._review(
                "product_name",
                value,
                "No usable product-name text.",
                candidate,
            )

        if len(text) > 80:
            return self._reject(
                "product_name",
                value,
                "Candidate is too long to be a credible product title.",
                candidate,
            )

        # Product name should usually be near a title/logo region.
        _, _, cx, cy, _ = self._bbox_geometry(
            candidate.get("bbox")
        )

        confidence = float(
            candidate.get(
                "confidence",
                0.0,
            )
        )

        score = confidence

        if cy < 120:
            score += 0.10
        elif cy < 250:
            score += 0.05

        if 1 <= word_count <= 7:
            score += 0.05

        if any(ch.isdigit() for ch in text):
            score += 0.02

        # Slightly penalize suspicious OCR fragments.
        if len(text) <= 4:
            score -= 0.12

        if score >= 1.00:
            score = 0.99

        if score >= 0.90:
            return {
                "field": "product_name",
                "value": text,
                "verified": True,
                "decision": "VERIFIED",
                "confidence": round(
                    score,
                    3,
                ),
                "reason": (
                    "Candidate is consistent with a "
                    "title-like product name and does not "
                    "match common declaration/address patterns."
                ),
                "evidence": [],
            }

        if score >= 0.72:
            return self._review(
                "product_name",
                value,
                "Candidate may be a product name but evidence is not strong enough for automatic verification.",
                candidate,
            )

        return self._review(
            "product_name",
            value,
            "Product-name evidence is insufficient.",
            candidate,
        )

    # ============================================================
    # Helpers
    # ============================================================

    @staticmethod
    def _normalize_field(field: str) -> str:
        return re.sub(
            r"[^a-z0-9_]",
            "",
            str(field).lower(),
        )

    @staticmethod
    def _candidate_value(
        candidate: Dict[str, Any],
    ) -> Any:
        if "value" in candidate:
            return candidate["value"]

        if "display" in candidate:
            return candidate["display"]

        if "name" in candidate:
            return candidate["name"]

        return candidate.get("raw_text")

    @staticmethod
    def _item_text(item: Any) -> str:
        if item is None:
            return ""

        if isinstance(item, dict):
            return str(
                item.get(
                    "text",
                    item.get(
                        "raw_text",
                        "",
                    ),
                )
                or ""
            ).strip()

        return str(
            getattr(
                item,
                "text",
                "",
            )
            or ""
        ).strip()

    @staticmethod
    def _item_bbox(item: Any) -> Any:
        if item is None:
            return None

        if isinstance(item, dict):
            return item.get("bbox")

        return getattr(
            item,
            "bbox",
            None,
        )

    @staticmethod
    def _candidate_bbox(
        candidate: Dict[str, Any],
    ) -> Any:
        return candidate.get("bbox")

    @staticmethod
    def _bbox_geometry(
        bbox: Any,
    ) -> Tuple[
        float,
        float,
        float,
        float,
        Tuple[float, float, float, float],
    ]:

        if not bbox:
            return (
                0.0,
                0.0,
                0.0,
                0.0,
                (
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ),
            )

        try:
            points = []

            if (
                isinstance(bbox, list)
                and bbox
                and isinstance(
                    bbox[0],
                    (list, tuple),
                )
            ):
                for point in bbox:
                    if len(point) >= 2:
                        points.append(
                            (
                                float(point[0]),
                                float(point[1]),
                            )
                        )
            elif (
                isinstance(bbox, list)
                and len(bbox) >= 4
            ):
                xs = [
                    float(bbox[0]),
                    float(bbox[2]),
                ]
                ys = [
                    float(bbox[1]),
                    float(bbox[3]),
                ]

                points = [
                    (
                        xs[0],
                        ys[0],
                    ),
                    (
                        xs[1],
                        ys[1],
                    ),
                ]

            if not points:
                return (
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    (
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ),
                )

            min_x = min(
                point[0]
                for point in points
            )

            max_x = max(
                point[0]
                for point in points
            )

            min_y = min(
                point[1]
                for point in points
            )

            max_y = max(
                point[1]
                for point in points
            )

            width = max_x - min_x
            height = max_y - min_y

            cx = (min_x + max_x) / 2.0
            cy = (min_y + max_y) / 2.0

            return (
                width,
                height,
                cx,
                cy,
                (
                    min_x,
                    min_y,
                    max_x,
                    max_y,
                ),
            )

        except Exception:
            return (
                0.0,
                0.0,
                0.0,
                0.0,
                (
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ),
            )

    @classmethod
    def _bbox_dimensions(
        cls,
        bbox: Any,
    ) -> Tuple[float, float]:
        width, height, _, _, _ = cls._bbox_geometry(
            bbox
        )

        return width, height

    def _nearby_items(
        self,
        candidate: Dict[str, Any],
        ocr_items: List[Any],
        radius: float = 220,
    ) -> List[Any]:

        _, _, cx, cy, _ = self._bbox_geometry(
            self._candidate_bbox(candidate)
        )

        if cx == 0 and cy == 0:
            return list(ocr_items)

        nearby = []

        for item in ocr_items:
            bbox = self._item_bbox(item)

            _, _, item_cx, item_cy, _ = (
                self._bbox_geometry(bbox)
            )

            distance = (
                (
                    (cx - item_cx) ** 2
                    + (cy - item_cy) ** 2
                )
                ** 0.5
            )

            if distance <= radius:
                nearby.append(item)

        return nearby

    @staticmethod
    def _contains_any(
        text: str,
        terms: List[str],
    ) -> bool:

        lower = str(text).lower()

        return any(
            term.lower() in lower
            for term in terms
        )

    def _find_nearby_label(
        self,
        nearby: List[Any],
        labels: List[str],
    ) -> bool:

        return any(
            self._contains_any(
                self._item_text(item),
                labels,
            )
            for item in nearby
        )

    def _has_nearby_context(
        self,
        nearby: List[Any],
        terms: List[str],
    ) -> bool:

        return any(
            self._contains_any(
                self._item_text(item),
                terms,
            )
            for item in nearby
        )

    @staticmethod
    def _evidence_text(item: Any) -> str:
        return VerificationService._item_text(item)

    @staticmethod
    def _to_float(
        value: Any,
    ) -> Optional[float]:

        try:
            return float(
                str(value)
                .replace(",", ".")
                .strip()
            )
        except Exception:
            return None

    @staticmethod
    def _find_best_before_duration(
        nearby: List[Any],
    ) -> Optional[str]:

        combined = " ".join(
            VerificationService._item_text(item)
            for item in nearby
        )

        match = re.search(
            r"best\s*before.{0,80}?"
            r"(\d+(?:\.\d+)?)\s*"
            r"(days?|months?|years?)",
            combined,
            re.IGNORECASE,
        )

        if not match:
            return None

        return match.group(0).strip()

    @staticmethod
    def _reject(
        field: str,
        value: Any,
        reason: str,
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {
            "field": field,
            "value": value,
            "verified": False,
            "decision": "REJECT",
            "confidence": round(
                float(
                    candidate.get(
                        "confidence",
                        0.0,
                    )
                ),
                3,
            ),
            "reason": reason,
            "evidence": [],
        }

    @staticmethod
    def _review(
        field: str,
        value: Any,
        reason: str,
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {
            "field": field,
            "value": value,
            "verified": False,
            "decision": "REVIEW",
            "confidence": round(
                float(
                    candidate.get(
                        "confidence",
                        0.0,
                    )
                ),
                3,
            ),
            "reason": reason,
            "evidence": [],
        }
from app.schemas.ocr import OcrTextItem
