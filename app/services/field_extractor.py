"""
LEGALENS Field Extraction Service

Converts OCR detections into structured packaged-commodity fields.

Design goals:
- Work with arbitrary packaged-product label layouts.
- Preserve OCR evidence and bounding boxes.
- Extract fields only when there is sufficient textual evidence.
- Never invent values when the OCR does not support them.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from app.schemas.ocr import OcrTextItem


class FieldExtractorService:

    def __init__(self):
        self.unit_normalization = {
            "g": "g",
            "gm": "g",
            "gms": "g",
            "gram": "g",
            "grams": "g",

            "kg": "kg",
            "kgs": "kg",
            "kilogram": "kg",
            "kilograms": "kg",

            "mg": "mg",
            "milligram": "mg",
            "milligrams": "mg",

            "ml": "ml",
            "milliliter": "ml",
            "milliliters": "ml",
            "millilitre": "ml",
            "millilitres": "ml",

            "l": "L",
            "lt": "L",
            "ltr": "L",
            "liter": "L",
            "litre": "L",
            "liters": "L",
            "litres": "L",
        }

    # =============================================================
    # Main extraction
    # =============================================================

    async def extract_fields(
        self,
        ocr_texts: List[OcrTextItem],
        images_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:

        items = [
            item
            for item in ocr_texts
            if item.text and item.text.strip()
        ]

        lines = [
            self._clean_text(item.text)
            for item in items
        ]

        extracted = {
            "product_name": None,

            "mrp": None,
            "currency": "INR",

            "net_quantity": None,
            "net_quantity_value": None,
            "net_quantity_unit": None,

            "manufacturer_name": None,
            "manufacturer_address": None,

            "packer": None,
            "importer": None,

            "manufacturing_date": None,
            "manufacturing_month": None,
            "manufacturing_year": None,

            "packing_date": None,
            "import_date": None,

            "best_before": None,
            "use_by": None,
            "expiry_date": None,

            "consumer_care_phone": None,
            "consumer_care_email": None,
            "consumer_care_address": None,

            "country_of_origin": None,
            "unit_sale_price": None,

            "barcode": None,
            "fssai_license": None,
            "manufacturing_license": None,

            "extracted_fields": {},
            "confidence": 0.0,
            "extraction_method": "ocr-aware-regex",
            "extracted_at": datetime.utcnow().isoformat(),
        }

        confidences: List[float] = []

        # ---------------------------------------------------------
        # MRP
        # ---------------------------------------------------------

        mrp_result = self._extract_mrp(items)

        if mrp_result:
            extracted["mrp"] = mrp_result["value"]
            extracted["currency"] = mrp_result.get(
                "currency",
                "INR",
            )
            extracted["extracted_fields"]["mrp"] = mrp_result
            confidences.append(mrp_result["confidence"])

        # ---------------------------------------------------------
        # Net quantity
        # ---------------------------------------------------------

        qty_result = self._extract_net_quantity(items)

        if qty_result:
            extracted["net_quantity"] = qty_result["display"]
            extracted["net_quantity_value"] = qty_result["value"]
            extracted["net_quantity_unit"] = qty_result["unit"]
            extracted["extracted_fields"]["net_quantity"] = qty_result
            confidences.append(qty_result["confidence"])

        # ---------------------------------------------------------
        # Manufacturer
        # ---------------------------------------------------------

        manufacturer = self._extract_labeled_party(
            items,
            [
                "manufacturer",
                "manufactured by",
                "manufactured & marketed by",
                "manufactured and marketed by",
                "manufactured for",
                "made by",
                "prepared by",
                "mfg.",
                "mfg",
            ],
        )

        if manufacturer:
            extracted["manufacturer_name"] = manufacturer["name"]

            extracted["extracted_fields"][
                "manufacturer"
            ] = manufacturer

            confidences.append(
                manufacturer["confidence"]
            )

        # ---------------------------------------------------------
        # Packer
        # ---------------------------------------------------------

        packer = self._extract_labeled_party(
            items,
            [
                "packer",
                "packed by",
                "packaged by",
            ],
        )

        if packer:
            extracted["packer"] = packer["name"]

            extracted["extracted_fields"][
                "packer"
            ] = packer

            confidences.append(
                packer["confidence"]
            )

            # In packaged-goods inspection, a clear packer
            # declaration is useful evidence for the
            # manufacturer/packer requirement.
            if not extracted["manufacturer_name"]:
                extracted["manufacturer_name"] = packer["name"]

                extracted["extracted_fields"][
                    "manufacturer"
                ] = {
                    "name": packer["name"],
                    "confidence": packer["confidence"],
                    "raw_text": packer["raw_text"],
                    "bbox": packer["bbox"],
                    "source": "packer_declaration",
                }

        # ---------------------------------------------------------
        # Manufacturer / packer address
        # ---------------------------------------------------------

        address = self._extract_party_address(
            items,
            manufacturer,
            packer,
        )

        if address:
            extracted["manufacturer_address"] = address["value"]

            extracted["extracted_fields"][
                "manufacturer_address"
            ] = address

            confidences.append(
                address["confidence"]
            )

        # ---------------------------------------------------------
        # Importer
        # ---------------------------------------------------------

        importer = self._extract_labeled_party(
            items,
            [
                "importer",
                "imported by",
                "imported for",
            ],
        )

        if importer:
            extracted["importer"] = importer["name"]

            extracted["extracted_fields"][
                "importer"
            ] = importer

            confidences.append(
                importer["confidence"]
            )

        # ---------------------------------------------------------
        # Dates
        # ---------------------------------------------------------

        manufacture = self._extract_date_field(
            items,
            [
                "date of manufacture",
                "date of mfg",
                "manufacturing date",
                "mfg date",
                "mfg. date",
                "month/year of manufacture",
                "month/year of mfg",
            ],
        )

        if manufacture:
            extracted["manufacturing_date"] = manufacture["date"]
            extracted["manufacturing_month"] = manufacture.get(
                "month"
            )
            extracted["manufacturing_year"] = manufacture.get(
                "year"
            )

            extracted["extracted_fields"][
                "manufacturing_date"
            ] = manufacture

            confidences.append(
                manufacture["confidence"]
            )

        packing = self._extract_date_field(
            items,
            [
                "date of packing",
                "date of pack",
                "packing date",
                "pack date",
                "pkd on",
                "packed on",
                "date packed",
            ],
        )

        if packing:
            extracted["packing_date"] = packing["date"]

            extracted["extracted_fields"][
                "packing_date"
            ] = packing

            confidences.append(
                packing["confidence"]
            )

        use_by = self._extract_date_field(
            items,
            [
                "use by date",
                "use by",
            ],
            exclude_labels=[
                "date of manufacture",
                "manufacturing date",
                "date of mfg",
                "mfg date",
                "date of packing",
                "packing date",
                "best before",
            ],
        )

        if use_by:
            extracted["use_by"] = use_by["date"]
            extracted["expiry_date"] = use_by["date"]

            extracted["extracted_fields"][
                "use_by"
            ] = use_by

            confidences.append(
                use_by["confidence"]
            )

        best_before = self._extract_best_before(items)

        if best_before:
            extracted["best_before"] = best_before["date"]

            extracted["extracted_fields"][
                "best_before"
            ] = best_before

            confidences.append(
                best_before["confidence"]
            )

        # ---------------------------------------------------------
        # Consumer care
        # ---------------------------------------------------------

        consumer_care = self._extract_consumer_care(
            items
        )

        if consumer_care:
            extracted["consumer_care_phone"] = (
                consumer_care.get("phone")
            )

            extracted["consumer_care_email"] = (
                consumer_care.get("email")
            )

            extracted["consumer_care_address"] = (
                consumer_care.get("address")
            )

            extracted["extracted_fields"][
                "consumer_care"
            ] = consumer_care

            confidences.append(
                consumer_care["confidence"]
            )

        # ---------------------------------------------------------
        # Country of origin
        # ---------------------------------------------------------

        country = self._extract_country_of_origin(
            items
        )

        if country:
            extracted["country_of_origin"] = country["value"]

            extracted["extracted_fields"][
                "country_of_origin"
            ] = country

            confidences.append(
                country["confidence"]
            )

        # ---------------------------------------------------------
        # Unit sale price
        # ---------------------------------------------------------

        unit_price = self._extract_unit_sale_price(
            items
        )

        if unit_price:
            extracted["unit_sale_price"] = (
                unit_price["value"]
            )

            extracted["extracted_fields"][
                "unit_sale_price"
            ] = unit_price

            confidences.append(
                unit_price["confidence"]
            )

        # ---------------------------------------------------------
        # Barcode
        # ---------------------------------------------------------

        barcode = self._extract_barcode(items)

        if barcode:
            extracted["barcode"] = barcode["value"]

            extracted["extracted_fields"][
                "barcode"
            ] = barcode

            confidences.append(
                barcode["confidence"]
            )

        # ---------------------------------------------------------
        # FSSAI
        # ---------------------------------------------------------

        fssai = self._extract_fssai(items)

        if fssai:
            extracted["fssai_license"] = fssai["value"]

            extracted["extracted_fields"][
                "fssai_license"
            ] = fssai

            confidences.append(
                fssai["confidence"]
            )

        # ---------------------------------------------------------
        # Manufacturing license
        # ---------------------------------------------------------

        license_result = (
            self._extract_manufacturing_license(items)
        )

        if license_result:
            extracted["manufacturing_license"] = (
                license_result["value"]
            )

            extracted["extracted_fields"][
                "manufacturing_license"
            ] = license_result

            confidences.append(
                license_result["confidence"]
            )

        # ---------------------------------------------------------
        # Product name
        # ---------------------------------------------------------

        product = self._extract_product_name(items)

        if product:
            extracted["product_name"] = product["value"]

            extracted["extracted_fields"][
                "product_name"
            ] = product

            confidences.append(
                product["confidence"]
            )

        # ---------------------------------------------------------
        # Final confidence
        # ---------------------------------------------------------

        if confidences:
            extracted["confidence"] = round(
                sum(confidences) / len(confidences),
                2,
            )

        return extracted

    # =============================================================
    # General helpers
    # =============================================================

    @staticmethod
    def _clean_text(text: str) -> str:
        text = str(text or "")
        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _item_text(item: OcrTextItem) -> str:
        return FieldExtractorService._clean_text(
            item.text
        )

    @staticmethod
    def _bbox_bounds(
        bbox: Any,
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Return min_x, min_y, max_x, max_y.
        Supports polygon or [x1,y1,x2,y2]-style boxes.
        """
        if not bbox:
            return None

        points = []

        try:
            for point in bbox:
                if (
                    isinstance(point, (list, tuple))
                    and len(point) >= 2
                ):
                    points.append(
                        (
                            float(point[0]),
                            float(point[1]),
                        )
                    )
                elif isinstance(point, (int, float)):
                    continue
        except Exception:
            return None

        if not points:
            return None

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        return (
            min(xs),
            min(ys),
            max(xs),
            max(ys),
        )

    @classmethod
    def _bbox_geometry(
        cls,
        bbox: Any,
    ) -> Tuple[float, float, float, float, float]:
        bounds = cls._bbox_bounds(bbox)

        if not bounds:
            return (
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            )

        min_x, min_y, max_x, max_y = bounds

        width = max_x - min_x
        height = max_y - min_y

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        return (
            width,
            height,
            center_x,
            center_y,
            min_y,
        )

    @staticmethod
    def _normalize_unit(unit: str) -> str:
        key = unit.lower().strip()

        return FieldExtractorService().unit_normalization.get(
            key,
            key,
        )

    # =============================================================
    # MRP
    # =============================================================

    def _extract_mrp(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        patterns = [
            r"\bmrp\b\s*(?:rs\.?|₹|inr)?\s*[:.\-]?\s*"
            r"(\d+(?:[.,]\d{1,2})?)",

            r"\bmaximum\s+retail\s+price\b\s*"
            r"(?:rs\.?|₹|inr)?\s*[:.\-]?\s*"
            r"(\d+(?:[.,]\d{1,2})?)",

            r"\bmax\.?\s+retail\s+price\b\s*"
            r"(?:rs\.?|₹|inr)?\s*[:.\-]?\s*"
            r"(\d+(?:[.,]\d{1,2})?)",
        ]

        for item in items:
            text = self._item_text(item)

            for pattern in patterns:
                match = re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                )

                if match:
                    return {
                        "value": float(
                            match.group(1).replace(",", "")
                        ),
                        "currency": "INR",
                        "confidence": float(
                            item.confidence or 0.9
                        ),
                        "raw_text": text,
                        "bbox": item.bbox,
                    }

        # Split declaration:
        # MRP Rs.
        # 25.00
        for index, item in enumerate(items):
            text = self._item_text(item)

            if not re.search(
                r"\bmrp\b|maximum\s+retail\s+price",
                text,
                re.IGNORECASE,
            ):
                continue

            for candidate in items[
                index + 1:index + 4
            ]:
                candidate_text = self._item_text(
                    candidate
                )

                match = re.search(
                    r"^(?:₹|rs\.?|inr)?\s*"
                    r"(\d+(?:[.,]\d{1,2})?)$",
                    candidate_text,
                    re.IGNORECASE,
                )

                if match:
                    return {
                        "value": float(
                            match.group(1).replace(",", "")
                        ),
                        "currency": "INR",
                        "confidence": float(
                            candidate.confidence or 0.85
                        ),
                        "raw_text": (
                            f"{text} {candidate_text}"
                        ),
                        "bbox": candidate.bbox,
                    }

        return None

    # =============================================================
    # Quantity
    # =============================================================

    def _extract_net_quantity(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        unit_pattern = (
            r"g|gm|gms|gram|grams|"
            r"kg|kgs|kilogram|kilograms|"
            r"mg|milligram|milligrams|"
            r"ml|milliliter|milliliters|"
            r"millilitre|millilitres|"
            r"l|lt|ltr|liter|litre|liters|litres"
        )

        label_pattern = (
            r"net\s*(?:qty|quantity|wt|weight)"
            r"|net\s*weight"
            r"|qty"
            r"|quantity"
        )

        full_pattern = re.compile(
            rf"\b(?:{label_pattern})\b"
            rf"\s*[:.\-]?\s*"
            rf"([\d,.]+)\s*"
            rf"({unit_pattern})\b",
            re.IGNORECASE,
        )

        # Same OCR detection
        for item in items:
            text = self._item_text(item)

            match = full_pattern.search(text)

            if match:
                value = float(
                    match.group(1).replace(",", "")
                )

                unit = self.unit_normalization.get(
                    match.group(2).lower(),
                    match.group(2).lower(),
                )

                return {
                    "value": value,
                    "unit": unit,
                    "display": f"{value:g} {unit}",
                    "confidence": float(
                        item.confidence or 0.9
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        # Split OCR detections
        quantity_labels = re.compile(
            r"\b(?:net\s*(?:qty|quantity|wt|weight)|"
            r"net\s*weight)\b",
            re.IGNORECASE,
        )

        unit_value_pattern = re.compile(
            rf"([\d,.]+)\s*({unit_pattern})\b",
            re.IGNORECASE,
        )

        for index, item in enumerate(items):
            text = self._item_text(item)

            if not quantity_labels.search(text):
                continue

            # Look forward and backward because OCR ordering
            # isn't guaranteed.
            candidate_indices = []

            for distance in range(1, 5):
                prev = index - distance
                nxt = index + distance

                if prev >= 0:
                    candidate_indices.append(prev)

                if nxt < len(items):
                    candidate_indices.append(nxt)

            for candidate_index in candidate_indices:
                candidate = items[candidate_index]
                candidate_text = self._item_text(candidate)

                match = unit_value_pattern.search(
                    candidate_text
                )

                if not match:
                    continue

                # Don't steal dates or declaration codes.
                if re.search(
                    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
                    candidate_text,
                ):
                    continue

                value = float(
                    match.group(1).replace(",", "")
                )

                unit = self.unit_normalization.get(
                    match.group(2).lower(),
                    match.group(2).lower(),
                )

                return {
                    "value": value,
                    "unit": unit,
                    "display": f"{value:g} {unit}",
                    "confidence": float(
                        min(
                            float(item.confidence or 0.85),
                            float(
                                candidate.confidence or 0.85
                            ),
                        )
                    ),
                    "raw_text": (
                        f"{text} {candidate_text}"
                    ),
                    "bbox": candidate.bbox,
                }

        return None

    # =============================================================
    # Manufacturer / Packer / Importer
    # =============================================================

    def _extract_labeled_party(
        self,
        items: List[OcrTextItem],
        labels: List[str],
    ) -> Optional[Dict[str, Any]]:

        # Longest labels first
        labels_sorted = sorted(
            labels,
            key=len,
            reverse=True,
        )

        for index, item in enumerate(items):
            text = self._item_text(item)

            for label in labels_sorted:

                same_line = re.search(
                    rf"\b{re.escape(label)}\b"
                    rf"\s*[:#\-]?\s*(.+)$",
                    text,
                    re.IGNORECASE,
                )

                if same_line:
                    candidate = (
                        self._clean_party_name(
                            same_line.group(1)
                        )
                    )

                    if self._valid_party_name(candidate):
                        return {
                            "name": candidate,
                            "confidence": float(
                                item.confidence or 0.85
                            ),
                            "raw_text": text,
                            "bbox": item.bbox,
                        }

                label_only = re.fullmatch(
                    rf"\s*{re.escape(label)}"
                    rf"[\s:#.\-]*",
                    text,
                    re.IGNORECASE,
                )

                if label_only:
                    for next_item in items[
                        index + 1:index + 4
                    ]:
                        candidate = (
                            self._clean_party_name(
                                self._item_text(
                                    next_item
                                )
                            )
                        )

                        if self._valid_party_name(
                            candidate
                        ):
                            return {
                                "name": candidate,
                                "confidence": float(
                                    next_item.confidence
                                    or 0.8
                                ),
                                "raw_text": (
                                    self._item_text(
                                        next_item
                                    )
                                ),
                                "bbox": next_item.bbox,
                            }

        return None

    @staticmethod
    def _clean_party_name(
        value: str,
    ) -> str:

        value = re.sub(
            r"\b(?:country\s+of\s+origin|"
            r"batch\s+number|use\s+by\s+date|"
            r"best\s+before|mrp|"
            r"incl\.?\s+of\s+all\s+taxes|"
            r"net\s*(?:wt|weight|qty|quantity)|"
            r"fssai|lic\s*no\.?)\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\b(?:license|licence|lic)\s*"
            r"(?:no\.?|number)?\s*[:\-]?\s*"
            r"[A-Z0-9\-./]+",
            "",
            value,
            flags=re.IGNORECASE,
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip(" :-.,;")

    @staticmethod
    def _valid_party_name(
        value: str,
    ) -> bool:

        if not value:
            return False

        if len(value) < 2 or len(value) > 120:
            return False

        lower = value.lower()

        bad_terms = [
            "country of origin",
            "batch number",
            "use by date",
            "best before",
            "mrp",
            "incl. of all taxes",
            "net wt",
            "net weight",
            "fssai",
            "customer care",
            "consumer care",
        ]

        if any(
            term in lower
            for term in bad_terms
        ):
            return False

        if re.fullmatch(
            r"[\d\s./\-]+",
            value,
        ):
            return False

        return True

    def _extract_party_address(
        self,
        items: List[OcrTextItem],
        manufacturer: Optional[Dict[str, Any]],
        packer: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:

        target = packer or manufacturer

        if not target:
            return None

        target_bbox = target.get("bbox")

        target_bounds = self._bbox_bounds(
            target_bbox
        )

        if not target_bounds:
            return None

        target_center_y = (
            target_bounds[1] +
            target_bounds[3]
        ) / 2

        # Locate target OCR item
        target_index = None

        for index, item in enumerate(items):
            if item.bbox == target_bbox:
                target_index = index
                break

        if target_index is None:
            return None

        address_parts = []

        # Look at following lines.
        for item in items[
            target_index + 1:
            target_index + 5
        ]:
            text = self._item_text(item)

            if not text:
                continue

            lower = text.lower()

            if any(
                keyword in lower
                for keyword in [
                    "email:",
                    "email ",
                    "customer care",
                    "consumer care",
                    "phone",
                    "contact",
                    "mrp",
                    "fssai",
                    "lic no",
                ]
            ):
                break

            # Address-looking line
            address_signal = (
                re.search(
                    r"\b(?:road|rd|street|st|"
                    r"estate|industrial|ind\.|"
                    r"nagar|mumbai|bangalore|"
                    r"bengaluru|delhi|maharashtra|"
                    r"karnataka|pin|pincode)\b",
                    lower,
                    re.IGNORECASE,
                )
                or re.search(
                    r"\d",
                    text,
                )
            )

            if address_signal:
                address_parts.append(text)

        if not address_parts:
            return None

        return {
            "value": ", ".join(address_parts),
            "confidence": round(
                sum(
                    float(
                        item.confidence or 0.8
                    )
                    for item in items[
                        target_index + 1:
                        target_index + 1 + len(
                            address_parts
                        )
                    ]
                )
                / len(address_parts),
                2,
            ),
            "raw_text": " ".join(address_parts),
            "bbox": items[
                target_index + 1
            ].bbox,
        }

    # =============================================================
    # Dates
    # =============================================================

    def _extract_date_field(
        self,
        items: List[OcrTextItem],
        labels: List[str],
        exclude_labels: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:

        exclude_labels = [
            label.lower()
            for label in (exclude_labels or [])
        ]

        for index, item in enumerate(items):
            text = self._item_text(item)

            matched_label = None

            for label in labels:
                if label.lower() in text.lower():
                    matched_label = label
                    break

            if not matched_label:
                continue

            # Same line
            match = re.search(
                rf"{re.escape(matched_label)}"
                rf"\s*[:.\-]?\s*(.*)",
                text,
                re.IGNORECASE,
            )

            if match:
                date_match = re.search(
                    r"\b\d{1,2}[/-]"
                    r"\d{1,2}[/-]"
                    r"\d{2,4}\b",
                    match.group(1),
                )

                if date_match:
                    parsed = self._parse_date_from_text(
                        date_match.group(0)
                    )

                    if parsed:
                        parsed.update(
                            {
                                "confidence": float(
                                    item.confidence or 0.85
                                ),
                                "raw_text": text,
                                "bbox": item.bbox,
                            }
                        )
                        return parsed

            # Nearby candidates
            nearby = []

            for distance in range(1, 5):
                previous = index - distance
                following = index + distance

                if previous >= 0:
                    nearby.append(
                        (distance, previous)
                    )

                if following < len(items):
                    nearby.append(
                        (distance, following)
                    )

            nearby.sort(
                key=lambda pair: pair[0]
            )

            for _, candidate_index in nearby:
                candidate = items[candidate_index]
                candidate_text = self._item_text(
                    candidate
                )

                candidate_lower = (
                    candidate_text.lower()
                )

                # Candidate is another declaration label
                if any(
                    blocked in candidate_lower
                    for blocked in (
                        exclude_labels
                        + [
                            "date of manufacture",
                            "manufacturing date",
                            "date of mfg",
                            "mfg date",
                            "date of packing",
                            "packing date",
                            "batch number",
                            "mrp",
                            "net qty",
                            "net quantity",
                            "net wt",
                            "net weight",
                            "use by",
                            "best before",
                            "expiry",
                            "country of origin",
                            "manufacturer",
                            "packed by",
                            "packer",
                            "importer",
                        ]
                    )
                ):
                    continue

                date_match = re.search(
                    r"\b\d{1,2}[/-]"
                    r"\d{1,2}[/-]"
                    r"\d{2,4}\b",
                    candidate_text,
                )

                if not date_match:
                    continue

                parsed = self._parse_date_from_text(
                    date_match.group(0)
                )

                if parsed:
                    parsed.update(
                        {
                            "confidence": float(
                                min(
                                    float(
                                        item.confidence
                                        or 0.8
                                    ),
                                    float(
                                        candidate.confidence
                                        or 0.8
                                    ),
                                )
                            ),
                            "raw_text": (
                                f"{text} "
                                f"{candidate_text}"
                            ),
                            "bbox": candidate.bbox,
                        }
                    )

                    return parsed

        return None

    def _extract_best_before(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        # First: explicit date after best-before.
        result = self._extract_date_field(
            items,
            [
                "best before date",
                "best before",
            ],
            exclude_labels=[
                "date of manufacture",
                "manufacturing date",
                "use by",
                "use by date",
                "date of packing",
                "packing date",
            ],
        )

        if result:
            return result

        # Second: "BEST BEFORE : 6 MONTHS"
        for item in items:
            text = self._item_text(item)

            match = re.search(
                r"\bbest\s+before\b"
                r"\s*[:.\-]?\s*"
                r"(\d+(?:\.\d+)?)\s*"
                r"(days?|months?|years?)",
                text,
                re.IGNORECASE,
            )

            if match:
                return {
                    "date": (
                        f"{match.group(1)} "
                        f"{match.group(2).lower()}"
                    ),
                    "confidence": float(
                        item.confidence or 0.85
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

    # =============================================================
    # Date parser
    # =============================================================

    def _parse_date_from_text(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:

        text = self._clean_text(text)

        # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        match = re.search(
            r"\b(\d{1,2})"
            r"[/. -]"
            r"(\d{1,2})"
            r"[/. -]"
            r"(\d{2,4})\b",
            text,
        )

        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year_raw = match.group(3)

            if not 1 <= month <= 12:
                return None

            year = int(year_raw)

            if len(year_raw) == 2:
                year += 2000

            if not 1 <= day <= 31:
                return None

            return {
                "date": (
                    f"{day:02d}/"
                    f"{month:02d}/"
                    f"{year:04d}"
                ),
                "day": day,
                "month": self._month_to_name(
                    month
                ),
                "month_number": month,
                "year": year,
            }

        # Month YYYY
        match = re.search(
            r"\b("
            r"jan(?:uary)?|"
            r"feb(?:ruary)?|"
            r"mar(?:ch)?|"
            r"apr(?:il)?|"
            r"may|"
            r"jun(?:e)?|"
            r"jul(?:y)?|"
            r"aug(?:ust)?|"
            r"sep(?:tember)?|"
            r"sept(?:ember)?|"
            r"oct(?:ober)?|"
            r"nov(?:ember)?|"
            r"dec(?:ember)?"
            r")"
            r"[\s\-/,]+"
            r"(\d{4})\b",
            text,
            re.IGNORECASE,
        )

        if match:
            month_name = match.group(1)
            year = int(match.group(2))

            month_number = (
                self._month_to_number(
                    month_name
                )
            )

            if not month_number:
                return None

            return {
                "date": (
                    f"{month_name.title()} "
                    f"{year}"
                ),
                "month": month_name.title(),
                "month_number": month_number,
                "year": year,
            }

        # YYYY-MM-DD
        match = re.search(
            r"\b(\d{4})-"
            r"(\d{1,2})-"
            r"(\d{1,2})\b",
            text,
        )

        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))

            if (
                1 <= month <= 12
                and 1 <= day <= 31
            ):
                return {
                    "date": (
                        f"{year:04d}-"
                        f"{month:02d}-"
                        f"{day:02d}"
                    ),
                    "day": day,
                    "month": self._month_to_name(
                        month
                    ),
                    "month_number": month,
                    "year": year,
                }

        return None

    # =============================================================
    # Consumer care
    # =============================================================

    def _extract_consumer_care(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        full_text = "\n".join(
            self._item_text(item)
            for item in items
        )

        phone = None
        email = None
        address = None
        confidence_values = []

        # Email
        for item in items:
            text = self._item_text(item)

            email_match = re.search(
                r"[A-Za-z0-9._%+\-]+@"
                r"[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
                text,
            )

            if email_match:
                email = email_match.group(0)
                confidence_values.append(
                    float(item.confidence or 0.85)
                )
                break

        # Phone
        # Supports:
        # 022 28052276
        # 022-28052276
        # +91 22 28052276
        # 1800xxxxxxx
        phone_pattern = re.compile(
            r"(?<!\d)"
            r"(?:\+91[\s\-]?)?"
            r"(?:0[\s\-]?)?"
            r"(?:[2-9]\d{1,4})"
            r"[\s\-]?"
            r"\d{5,8}"
            r"(?!\d)"
        )

        for item in items:
            text = self._item_text(item)

            # Prioritize lines that look like contact fields.
            if re.search(
                r"(customer\s*care|consumer\s*care|"
                r"phone|contact|helpline|"
                r"tel|mobile)",
                text,
                re.IGNORECASE,
            ):
                phone_match = phone_pattern.search(
                    text
                )

                if phone_match:
                    raw_phone = phone_match.group(0)

                    digits = re.sub(
                        r"\D",
                        "",
                        raw_phone,
                    )

                    # Remove country code if present.
                    if (
                        digits.startswith("91")
                        and len(digits) >= 12
                    ):
                        digits = digits[2:]

                    if len(digits) >= 8:
                        phone = digits
                        confidence_values.append(
                            float(
                                item.confidence
                                or 0.85
                            )
                        )
                        break

        # Fallback: search all OCR lines.
        if not phone:
            for item in items:
                text = self._item_text(item)

                phone_match = phone_pattern.search(
                    text
                )

                if phone_match:
                    digits = re.sub(
                        r"\D",
                        "",
                        phone_match.group(0),
                    )

                    if (
                        digits.startswith("91")
                        and len(digits) >= 12
                    ):
                        digits = digits[2:]

                    if len(digits) >= 8:
                        phone = digits
                        confidence_values.append(
                            float(
                                item.confidence
                                or 0.8
                            )
                        )
                        break

        # Consumer-care address
        for item in items:
            text = self._item_text(item)

            address_match = re.search(
                r"(?:write\s+to|contact|"
                r"address)\s*[:\-]\s*(.+)",
                text,
                re.IGNORECASE,
            )

            if address_match:
                address = (
                    address_match.group(1)
                    .strip()
                )

                confidence_values.append(
                    float(item.confidence or 0.8)
                )

                break

        if (
            not phone
            and not email
            and not address
        ):
            return None

        return {
            "phone": phone,
            "email": email,
            "address": address,
            "confidence": (
                round(
                    sum(confidence_values)
                    / len(confidence_values),
                    2,
                )
                if confidence_values
                else 0.8
            ),
            "raw_text": full_text,
        }

    # =============================================================
    # Country
    # =============================================================

    def _extract_country_of_origin(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        patterns = [
            r"country\s+of\s+origin\s*"
            r"[:\-]?\s*"
            r"([A-Za-z][A-Za-z\s]{1,40})",

            r"made\s+in\s+"
            r"([A-Za-z][A-Za-z\s]{1,40})",

            r"origin\s*[:\-]\s*"
            r"([A-Za-z][A-Za-z\s]{1,40})",

            r"product\s+of\s+"
            r"([A-Za-z][A-Za-z\s]{1,40})",
        ]

        for item in items:
            text = self._item_text(item)

            for pattern in patterns:
                match = re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                )

                if not match:
                    continue

                value = match.group(1)

                value = re.split(
                    r"\b(?:batch|use by|"
                    r"best before|mrp|"
                    r"incl|fssai|lic)\b",
                    value,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip(
                    " .,:;-"
                )

                if not value:
                    continue

                if "india" in value.lower():
                    value = "India"

                return {
                    "value": value,
                    "confidence": float(
                        item.confidence or 0.9
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

    # =============================================================
    # Unit sale price
    # =============================================================

    def _extract_unit_sale_price(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        pattern = re.compile(
            r"\b(?:unit\s+(?:sale\s+)?price|"
            r"price\s+per)\b"
            r"\s*[:.\-]?\s*"
            r"(?:₹|rs\.?|inr)?\s*"
            r"(\d+(?:[.,]\d{1,2})?)",
            re.IGNORECASE,
        )

        for item in items:
            text = self._item_text(item)

            match = pattern.search(text)

            if match:
                return {
                    "value": float(
                        match.group(1).replace(
                            ",",
                            "",
                        )
                    ),
                    "confidence": float(
                        item.confidence or 0.85
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

    # =============================================================
    # Barcode
    # =============================================================

    def _extract_barcode(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        for item in items:
            text = self._item_text(item)

            labelled = re.search(
                r"\b(?:barcode|ean|upc|"
                r"isbn|gtin)\b"
                r"\s*[:.\-]?\s*"
                r"(\d{8,14})\b",
                text,
                re.IGNORECASE,
            )

            if labelled:
                return {
                    "value": labelled.group(1),
                    "confidence": float(
                        item.confidence or 0.85
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        # Barcode OCR commonly arrives with spaces:
        # 8 904043 708560
        for item in items:
            text = self._item_text(item)

            digits = re.sub(
                r"\D",
                "",
                text,
            )

            if (
                len(digits) in (8, 12, 13, 14)
                and re.fullmatch(
                    r"[\d\s]+",
                    text,
                )
            ):
                return {
                    "value": digits,
                    "confidence": float(
                        item.confidence or 0.8
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

    # =============================================================
    # FSSAI
    # =============================================================

    def _extract_fssai(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        # Same line
        for item in items:
            text = self._item_text(item)

            match = re.search(
                r"\b(?:fssai|fssal)\b"
                r"[\s:#.\-]*"
                r"(?:lic(?:ense|ence)?|"
                r"license|licence|no\.?)?"
                r"[\s:#.\-]*"
                r"(\d{14})\b",
                text,
                re.IGNORECASE,
            )

            if match:
                return {
                    "value": match.group(1),
                    "confidence": float(
                        item.confidence or 0.9
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        # Split:
        # FSSAI
        # LIC No.: 12345678901234
        for index, item in enumerate(items):
            text = self._item_text(item)

            if not re.search(
                r"\bfssai\b|\bfssal\b",
                text,
                re.IGNORECASE,
            ):
                continue

            for candidate in items[
                index + 1:index + 4
            ]:
                candidate_text = self._item_text(
                    candidate
                )

                match = re.search(
                    r"\b(?:lic(?:ense|ence)?|"
                    r"license|licence|no\.?)"
                    r"[\s:#.\-]*"
                    r"(\d{10,14})\b",
                    candidate_text,
                    re.IGNORECASE,
                )

                if match:
                    number = match.group(1)

                    return {
                        "value": number,
                        "confidence": float(
                            min(
                                float(
                                    item.confidence
                                    or 0.85
                                ),
                                float(
                                    candidate.confidence
                                    or 0.85
                                ),
                            )
                        ),
                        "raw_text": (
                            f"{text} "
                            f"{candidate_text}"
                        ),
                        "bbox": candidate.bbox,
                    }

                # Just a bare 14-digit line after FSSAI
                if re.fullmatch(
                    r"\d{14}",
                    candidate_text,
                ):
                    return {
                        "value": candidate_text,
                        "confidence": float(
                            candidate.confidence
                            or 0.85
                        ),
                        "raw_text": (
                            f"{text} "
                            f"{candidate_text}"
                        ),
                        "bbox": candidate.bbox,
                    }

        # Any standalone FSSAI-looking 14-digit line
        # near a license declaration.
        for index, item in enumerate(items):
            text = self._item_text(item)

            if not re.search(
                r"\blic\b|\blicense\b|\blicence\b",
                text,
                re.IGNORECASE,
            ):
                continue

            match = re.search(
                r"\b(\d{14})\b",
                text,
            )

            if match:
                return {
                    "value": match.group(1),
                    "confidence": float(
                        item.confidence or 0.85
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

    # =============================================================
    # Manufacturing license
    # =============================================================

    def _extract_manufacturing_license(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        pattern = re.compile(
            r"\b(?:mfg\.?|manuf\.?|manufacturing)\s+"
            r"(?:license|licence)\b"
            r"\s*(?:no\.?|number)?\s*"
            r"[:.\-]?\s*"
            r"([A-Z0-9][A-Z0-9./\-]{4,})",
            re.IGNORECASE,
        )

        for item in items:
            text = self._item_text(item)

            match = pattern.search(text)

            if match:
                value = match.group(1)

                return {
                    "value": value,
                    "confidence": float(
                        item.confidence or 0.85
                    ),
                    "raw_text": text,
                    "bbox": item.bbox,
                }

        return None

        # =============================================================
    # Product name
    # =============================================================

    def _extract_product_name(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        candidates = []

        rejected_terms = [
            "ingredients",
            "net wt",
            "net weight",
            "net qty",
            "net quantity",
            "batch",
            "pkd on",
            "packed on",
            "best before",
            "use by",
            "mrp",
            "incl of all taxes",
            "incl. of all taxes",
            "fssai",
            "lic no",
            "license",
            "licence",
            "packed by",
            "packaged by",
            "manufactured by",
            "manufactured and",
            "manufactured &",
            "customer care",
            "consumer care",
            "email",
            "country of origin",
            "product of",
            "made in",
        ]

        address_terms = [
            "road",
            "cross road",
            "estate",
            "ind. estate",
            "mumbai",
            "bengaluru",
            "bangalore",
            "chennai",
            "delhi",
            "maharashtra",
            "karnataka",
            "tamil nadu",
            "gujarat",
            "nagar",
            "pin",
            "pvt",
            "private limited",
            "ltd",
            "plot",
            "building",
            "floor",
            "industrial",
            "sector",
        ]

        for item in items:
            text = self._item_text(item).strip()

            if len(text) < 3 or len(text) > 80:
                continue

            lower = text.lower()

            # Declaration / legal text.
            if any(term in lower for term in rejected_terms):
                continue

            # Address-like text.
            if any(term in lower for term in address_terms):
                continue

            # Emails / URLs.
            if "@" in text or "www." in lower or "http" in lower:
                continue

            # Long numeric / barcode-like text.
            digits = re.sub(r"\D", "", text)

            if len(digits) >= 8:
                continue

            # License-like strings.
            if re.search(
                r"\blic\s*no\b|\bfssai\b",
                lower,
            ):
                continue

            # Bounding box.
            width, height, cx, cy, _ = (
                self._bbox_geometry(item.bbox)
            )

            # Reject vertically oriented OCR.
            if (
                width > 0
                and height > 0
                and height > width * 2.5
            ):
                continue

            # Must contain letters.
            alpha_count = sum(
                1
                for char in text
                if char.isalpha()
            )

            if alpha_count < 3:
                continue

            words = text.split()

            alpha_words = [
                word
                for word in words
                if re.search(
                    r"[A-Za-z]{2,}",
                    word,
                )
            ]

            if not alpha_words:
                continue

            # Tiny isolated OCR fragments are unreliable.
            if len(words) == 1 and len(text) <= 4:
                continue

            confidence = float(
                item.confidence or 0.0
            )

            score = confidence * 10

            # -----------------------------------------------------
            # TITLE POSITION
            # -----------------------------------------------------
            # Earlier text is more likely to be the title.
            if cy < 100:
                score += 12.0
            elif cy < 160:
                score += 8.0
            elif cy < 250:
                score += 3.0
            elif cy > 300:
                score -= 6.0

            # -----------------------------------------------------
            # TITLE-LIKE LENGTH
            # -----------------------------------------------------
            if 2 <= len(words) <= 5:
                score += 5.0
            elif len(words) == 1:
                score += 1.0
            elif len(words) > 8:
                score -= 3.0

            # -----------------------------------------------------
            # PRODUCT-LIKE TEXT
            # -----------------------------------------------------
            if any(
                char.isdigit()
                for char in text
            ):
                score += 2.0

            uppercase_chars = sum(
                1
                for char in text
                if char.isupper()
            )

            if uppercase_chars >= 4:
                score += 2.0

            if 5 <= len(text) <= 35:
                score += 2.0

            # Penalize punctuation-heavy text.
            punctuation_count = sum(
                1
                for char in text
                if char in ",.:;/-()"
            )

            if punctuation_count >= 4:
                score -= 2.0

            candidates.append(
                (
                    score,
                    item,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda pair: pair[0],
            reverse=True,
        )

        item = candidates[0][1]
        text = self._item_text(item)

        return {
            "value": text,
            "confidence": float(
                item.confidence or 0.7
            ),
            "raw_text": text,
            "bbox": item.bbox,
        }
    # =============================================================
    # Utilities
    # =============================================================

    @staticmethod
    def _month_to_number(
        month_name: str,
    ) -> Optional[int]:

        months = {
            "january": 1,
            "jan": 1,
            "february": 2,
            "feb": 2,
            "march": 3,
            "mar": 3,
            "april": 4,
            "apr": 4,
            "may": 5,
            "june": 6,
            "jun": 6,
            "july": 7,
            "jul": 7,
            "august": 8,
            "aug": 8,
            "september": 9,
            "sep": 9,
            "sept": 9,
            "october": 10,
            "oct": 10,
            "november": 11,
            "nov": 11,
            "december": 12,
            "dec": 12,
        }

        return months.get(
            month_name.lower()
        )

    @staticmethod
    def _month_to_name(
        month_number: int,
    ) -> Optional[str]:

        months = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }

        return months.get(
            month_number
        )


# =============================================================
# Convenience wrapper
# =============================================================

async def extract_fields(
    ocr_texts: List[OcrTextItem],
) -> Dict[str, Any]:
    """Convenience wrapper."""

    service = FieldExtractorService()

    return await service.extract_fields(
        ocr_texts
    )