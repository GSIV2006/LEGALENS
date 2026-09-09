"""
LEGALENS Field Extraction Service

Converts OCR detections into structured packaged-commodity fields.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.schemas.ocr import OcrTextItem
from app.services.verification_service import VerificationService


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

        self.verifier = VerificationService()

    async def extract_fields(
        self,
        ocr_texts: List[OcrTextItem],
        images_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:

        items = [
            item
            for item in ocr_texts
            if getattr(item, "text", None)
            and str(item.text).strip()
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
            "verification": {},
            "confidence": 0.0,
            "extraction_method":
                "ocr-aware-regex+semantic-verification",
            "extracted_at":
                datetime.utcnow().isoformat(),
        }

        confidences = []

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

            extracted["extracted_fields"]["mrp"] = (
                mrp_result
            )

            confidences.append(
                mrp_result["confidence"]
            )

        # ---------------------------------------------------------
        # NET QUANTITY
        # ---------------------------------------------------------

        qty_result = self._extract_net_quantity(items)

        if qty_result:
            extracted["net_quantity"] = (
                qty_result["display"]
            )

            extracted["net_quantity_value"] = (
                qty_result["value"]
            )

            extracted["net_quantity_unit"] = (
                qty_result["unit"]
            )

            extracted["extracted_fields"][
                "net_quantity"
            ] = qty_result

            confidences.append(
                qty_result["confidence"]
            )

        # ---------------------------------------------------------
        # MANUFACTURER
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
                "mfd by",
                "mfd.",
                "mfd",
                "mid by",
                "mfg.",
                "mfg",
            ],
        )

        if manufacturer:
            extracted["manufacturer_name"] = (
                manufacturer["name"]
            )

            extracted["extracted_fields"][
                "manufacturer"
            ] = manufacturer

            confidences.append(
                manufacturer["confidence"]
            )

            # ---------------------------------------------------------
            # MANUFACTURER ADDRESS
            # ---------------------------------------------------------

            manufacturer_address = None
            manufacturer_index = None

            for idx, item in enumerate(items):
                item_text = self._item_text(item)

                if not item_text:
                    continue

                normalized = re.sub(
                    r"\s+",
                    " ",
                    item_text,
                ).strip().lower()

                if (
                    "mfd by" in normalized
                    or "mid by" in normalized
                    or "manufactured by" in normalized
                    or "manufactured and marketed by" in normalized
                    or "manufactured & marketed by" in normalized
                    or "mfd." in normalized
                ):
                    manufacturer_index = idx
                    break

            if manufacturer_index is not None:
                for next_item in items[
                    manufacturer_index + 1:
                    manufacturer_index + 5
                ]:
                    candidate_raw = self._item_text(
                        next_item
                    )

                    if not candidate_raw:
                        continue

                    candidate = re.sub(
                        r"\s+",
                        " ",
                        candidate_raw,
                    ).strip()

                    lower_candidate = candidate.lower()

                    if re.search(
                        r"\b(?:mfg\.?\s+lic|licence|license)\b",
                        lower_candidate,
                        re.IGNORECASE,
                    ):
                        break

                    looks_like_address = (
                        bool(re.search(r"\d", candidate))
                        and (
                            "," in candidate
                            or re.search(
                                r"\b(?:road|rd|street|st|"
                                r"nagar|estate|industrial|"
                                r"phase|district|"
                                r"puducherry|delhi|"
                                r"mumbai|chennai|"
                                r"bangalore|bengaluru|"
                                r"india)\b",
                                lower_candidate,
                            )
                        )
                    )

                    if looks_like_address:
                        manufacturer_address = {
                            "value": candidate,
                            "confidence": float(
                                getattr(
                                    next_item,
                                    "confidence",
                                    None,
                                )
                                or 0.85
                            ),
                            "raw_text": candidate_raw,
                            "bbox": getattr(
                                next_item,
                                "bbox",
                                None,
                            ),
                        }
                        break

            if manufacturer_address:
                extracted["manufacturer_address"] = (
                    manufacturer_address["value"]
                )

                extracted["extracted_fields"][
                    "manufacturer_address"
                ] = manufacturer_address

                confidences.append(
                    manufacturer_address["confidence"]
                )

        # ---------------------------------------------------------
        # PACKER
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

        # ---------------------------------------------------------
        # IMPORTER
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
        # MANUFACTURING DATE
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
            extracted["manufacturing_date"] = (
                manufacture["date"]
            )

            extracted["manufacturing_month"] = (
                manufacture.get("month")
            )

            extracted["manufacturing_year"] = (
                manufacture.get("year")
            )

            extracted["extracted_fields"][
                "manufacturing_date"
            ] = manufacture

            confidences.append(
                manufacture["confidence"]
            )

        # ---------------------------------------------------------
        # PACKING DATE
        # ---------------------------------------------------------

        packing = self._extract_date_field(
            items,
            [
                "date of packing",
                "date of pack",
                "packing date",
                "pack date",
            ],
        )

        if packing:
            extracted["packing_date"] = (
                packing["date"]
            )

            extracted["extracted_fields"][
                "packing_date"
            ] = packing

            confidences.append(
                packing["confidence"]
            )

        # ---------------------------------------------------------
        # USE BY
        # ---------------------------------------------------------

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
            ],
        )

        if use_by:
            extracted["use_by"] = (
                use_by["date"]
            )

            extracted["expiry_date"] = (
                use_by["date"]
            )

            extracted["extracted_fields"][
                "use_by"
            ] = use_by

            confidences.append(
                use_by["confidence"]
            )

        # ---------------------------------------------------------
        # BEST BEFORE
        # ---------------------------------------------------------

        best_before = self._extract_best_before(items)

        if best_before:
            extracted["best_before"] = (
                best_before["date"]
            )

            extracted["extracted_fields"][
                "best_before"
            ] = best_before

            confidences.append(
                best_before["confidence"]
            )

        # ---------------------------------------------------------
        # CONSUMER CARE
        # ---------------------------------------------------------

        consumer_care = self._extract_consumer_care(
            items
        )

        if consumer_care:

            if consumer_care.get("phone"):
                extracted["consumer_care_phone"] = (
                    consumer_care["phone"]
                )

            if consumer_care.get("email"):
                extracted["consumer_care_email"] = (
                    consumer_care["email"]
                )

            if consumer_care.get("address"):
                extracted["consumer_care_address"] = (
                    consumer_care["address"]
                )

            extracted["extracted_fields"][
                "consumer_care"
            ] = consumer_care

            confidences.append(
                consumer_care["confidence"]
            )

        # ---------------------------------------------------------
        # COUNTRY
        # ---------------------------------------------------------

        country = self._extract_country_of_origin(
            items
        )

        if country:
            extracted["country_of_origin"] = (
                country["value"]
            )

            extracted["extracted_fields"][
                "country_of_origin"
            ] = country

            confidences.append(
                country["confidence"]
            )

        # ---------------------------------------------------------
        # UNIT SALE PRICE
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
        # BARCODE
        # ---------------------------------------------------------

        barcode = self._extract_barcode(items)

        if barcode:
            extracted["barcode"] = (
                barcode["value"]
            )

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
            extracted["fssai_license"] = (
                fssai["value"]
            )

            extracted["extracted_fields"][
                "fssai_license"
            ] = fssai

            confidences.append(
                fssai["confidence"]
            )

        # ---------------------------------------------------------
        # MANUFACTURING LICENSE
        # ---------------------------------------------------------

        manufacturing_license = (
            self._extract_manufacturing_license(items)
        )

        if manufacturing_license:

            extracted["manufacturing_license"] = (
                manufacturing_license["value"]
            )

            extracted["extracted_fields"][
                "manufacturing_license"
            ] = manufacturing_license

            confidences.append(
                manufacturing_license["confidence"]
            )

        # ---------------------------------------------------------
        # PRODUCT NAME
        # ---------------------------------------------------------

        product = self._extract_product_name(items)

        if product:
            extracted["product_name"] = (
                product["value"]
            )

            extracted["extracted_fields"][
                "product_name"
            ] = product

            confidences.append(
                product["confidence"]
            )

        if confidences:
            extracted["confidence"] = round(
                sum(confidences) / len(confidences),
                2,
            )

        # ---------------------------------------------------------
        # SEMANTIC VERIFICATION
        # ---------------------------------------------------------

        try:

            verification = self.verifier.verify_all(
                extracted["extracted_fields"],
                items,
            )

            extracted["verification"] = verification

            self._apply_verification(
                extracted,
                verification,
            )

        except Exception as exc:

            extracted["verification"] = {
                "_system": {
                    "field": "_system",
                    "verified": False,
                    "decision": "REVIEW",
                    "confidence": 0.0,
                    "reason":
                        f"Semantic verification error: {exc}",
                    "evidence": [],
                }
            }

        return extracted

    # =============================================================
    # APPLY VERIFICATION
    # =============================================================

    def _apply_verification(
        self,
        extracted: Dict[str, Any],
        verification: Dict[str, Any],
    ) -> None:

        field_map = {
            "mrp": [
                "mrp",
            ],

            "net_quantity": [
                "net_quantity",
                "net_quantity_value",
                "net_quantity_unit",
            ],

            "product_name": [
                "product_name",
            ],

            "manufacturer": [
                "manufacturer_name",
            ],

            "packer": [
                "packer",
            ],

            "importer": [
                "importer",
            ],

            "manufacturing_date": [
                "manufacturing_date",
                "manufacturing_month",
                "manufacturing_year",
            ],

            "packing_date": [
                "packing_date",
            ],

            "use_by": [
                "use_by",
                "expiry_date",
            ],

            "best_before": [
                "best_before",
            ],

            "consumer_care": [
                "consumer_care_phone",
                "consumer_care_email",
                "consumer_care_address",
            ],

            "country_of_origin": [
                "country_of_origin",
            ],

            "unit_sale_price": [
                "unit_sale_price",
            ],

            "barcode": [
                "barcode",
            ],

            "fssai_license": [
                "fssai_license",
            ],

            "manufacturing_license": [
                "manufacturing_license",
            ],
        }

        for verification_key, canonical_keys in field_map.items():

            result = verification.get(
                verification_key
            )

            if not isinstance(result, dict):
                continue

            decision = str(
                result.get(
                    "decision",
                    "",
                )
            ).upper()

            if decision in {
                "REVIEW",
                "REJECT",
            }:

                for key in canonical_keys:

                    if key in extracted:
                        extracted[key] = None

    # =============================================================
    # TEXT
    # =============================================================

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        text = str(text or "")

        text = text.replace(
            "\r",
            " ",
        )

        text = text.replace(
            "\n",
            " ",
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    @staticmethod
    def _item_text(
        item: OcrTextItem,
    ) -> str:

        return FieldExtractorService._clean_text(
            getattr(
                item,
                "text",
                "",
            )
        )

    # =============================================================
    # MRP
    # =============================================================

    def _extract_mrp(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        label_pattern = re.compile(
            r"\b(?:m\.?\s*r\.?\s*p\.?|"
            r"maximum\s+retail\s+price|"
            r"max\.?\s+retail\s+price)\b",
            re.IGNORECASE,
        )

        money_pattern = re.compile(
            r"(?:rs\.?|inr)?\s*"
            r"(\d+(?:[.,]\d{1,2})?)"
            r"\s*(?:/-)?",
            re.IGNORECASE,
        )

        def get_box(item):
            try:
                box = getattr(item, "bounding_box", None)

                if box is None:
                    box = getattr(item, "bbox", None)

                if isinstance(box, str):
                    import json
                    box = json.loads(box)

                if not box or len(box) < 4:
                    return None

                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]

                return {
                    "left": min(xs),
                    "right": max(xs),
                    "top": min(ys),
                    "bottom": max(ys),
                    "cx": sum(xs) / len(xs),
                    "cy": sum(ys) / len(ys),
                }

            except Exception:
                return None

        def distance(a, b):
            dx = 0.0
            dy = 0.0

            if a["right"] < b["left"]:
                dx = b["left"] - a["right"]
            elif b["right"] < a["left"]:
                dx = a["left"] - b["right"]

            if a["bottom"] < b["top"]:
                dy = b["top"] - a["bottom"]
            elif b["bottom"] < a["top"]:
                dy = a["top"] - b["bottom"]

            return (dx * dx + dy * dy) ** 0.5

        # ---------------------------------------------------------
        # 1. Same-line / same-box MRP declarations
        # ---------------------------------------------------------

        for item in items:
            text_value = self._item_text(item)

            if not text_value or not label_pattern.search(text_value):
                continue

            match = money_pattern.search(
                text_value[label_pattern.search(text_value).end():]
            )

            if not match:
                continue

            value = float(
                match.group(1).replace(",", "")
            )

            # Reject clearly impossible prices.
            if value <= 0 or value > 100000:
                continue

            return {
                "value": value,
                "currency": "INR",
                "display": f"?{value:g}",
                "confidence": min(
                    0.99,
                    float(
                        getattr(item, "confidence", None)
                        or 0.9
                    ),
                ),
                "raw_text": text_value,
                "bbox": getattr(item, "bbox", None),
                "labelled": True,
            }

        # ---------------------------------------------------------
        # 2. Separate OCR boxes: MRP label + nearby price
        # ---------------------------------------------------------

        labels = []

        for item in items:
            text_value = self._item_text(item)

            if not text_value:
                continue

            if label_pattern.search(text_value):
                box = get_box(item)

                if box:
                    labels.append(
                        {
                            "item": item,
                            "text": text_value,
                            "box": box,
                        }
                    )

        if not labels:
            return None

        price_candidates = []

        for item in items:
            text_value = self._item_text(item)

            if not text_value:
                continue

            # Price candidates should be mostly numeric/currency.
            if not re.fullmatch(
                r"(?:rs\.?|inr)?\s*"
                r"\d+(?:[.,]\d{1,2})?"
                r"\s*(?:/-)?",
                text_value,
                re.IGNORECASE,
            ):
                continue

            match = money_pattern.fullmatch(text_value.strip())

            if not match:
                continue

            value = float(
                match.group(1).replace(",", "")
            )

            if value <= 0 or value > 100000:
                continue

            box = get_box(item)

            if box:
                price_candidates.append(
                    {
                        "item": item,
                        "text": text_value,
                        "value": value,
                        "box": box,
                    }
                )

        best = None

        for label in labels:
            for candidate in price_candidates:
                d = distance(label["box"], candidate["box"])

                # MRP label and value should normally be physically close.
                if d > 500:
                    continue

                score = 1000 - d

                # Same horizontal row gets a bonus.
                label_box = label["box"]
                price_box = candidate["box"]

                vertical_delta = abs(
                    label_box["cy"] - price_box["cy"]
                )

                if vertical_delta <= 100:
                    score += 200

                # Prefer values that look like normal retail prices.
                if candidate["value"] <= 10000:
                    score += 20

                if best is None or score > best["score"]:
                    best = {
                        "score": score,
                        "candidate": candidate,
                        "label": label,
                    }

        if best is None:
            return None

        candidate = best["candidate"]

        confidence = float(
            getattr(
                candidate["item"],
                "confidence",
                None,
            )
            or 0.85
        )

        return {
            "value": candidate["value"],
            "currency": "INR",
            "display": f"?{candidate['value']:g}",
            "confidence": min(0.98, confidence),
            "raw_text": (
                f"{best['label']['text']} "
                f"{candidate['text']}"
            ),
            "bbox": getattr(
                candidate["item"],
                "bbox",
                None,
            ),
            "labelled": True,
        }
    # =============================================================
    # NET QUANTITY
    # =============================================================

    def _extract_net_quantity(
        self,
        ocr_items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:
        """
        Extract net quantity for weight, volume and count-based packages.

        Examples:
            80 g
            1 kg
            500 ml
            10 condoms
            10 pcs
            12 tablets
            6 units
        """

        quantity_pattern = re.compile(
            r"(?<!\d)(\d+(?:[.,]\d+)?)\s*"
            r"(kg|kgs|g|gm|gms|mg|ml|l|ltr|litre|litres|cl|"
            r"pcs?|pieces?|units?|items?|counts?|"
            r"condoms?|tablets?|capsules?|bottles?|packs?|"
            r"boxes?|sachets?|pouches?|strips?|rolls?)\b",
            re.IGNORECASE,
        )

        label_pattern = re.compile(
            r"\bnet\s*(?:wt\.?|weight|qty\.?|quantity)\b",
            re.IGNORECASE,
        )

        def get_box(item):
            try:
                box = getattr(item, "bounding_box", None)

                if box is None:
                    box = getattr(item, "bbox", None)

                if isinstance(box, str):
                    import json
                    box = json.loads(box)

                if not box or len(box) < 4:
                    return None

                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]

                return {
                    "left": min(xs),
                    "right": max(xs),
                    "top": min(ys),
                    "bottom": max(ys),
                    "cx": sum(xs) / len(xs),
                    "cy": sum(ys) / len(ys),
                }

            except Exception:
                return None

        def distance(a, b):
            dx = 0.0
            dy = 0.0

            if a["right"] < b["left"]:
                dx = b["left"] - a["right"]
            elif b["right"] < a["left"]:
                dx = a["left"] - b["right"]

            if a["bottom"] < b["top"]:
                dy = b["top"] - a["bottom"]
            elif b["bottom"] < a["top"]:
                dy = a["top"] - b["bottom"]

            return (dx * dx + dy * dy) ** 0.5

        unit_map = {
            "kgs": "kg",
            "gm": "g",
            "gms": "g",
            "ltr": "l",
            "litre": "l",
            "litres": "l",
            "pcs": "pcs",
            "pc": "pc",
            "pieces": "pieces",
            "piece": "piece",
            "units": "units",
            "unit": "unit",
            "items": "items",
            "item": "item",
            "counts": "count",
            "count": "count",
        }

        quantities = []

        for item in ocr_items:
            text_value = self._item_text(item)

            if not text_value:
                continue

            match = quantity_pattern.search(text_value)

            if not match:
                continue

            value = match.group(1).replace(",", ".")
            raw_unit = match.group(2).lower()
            unit = unit_map.get(raw_unit, raw_unit)

            quantities.append(
                {
                    "value": value,
                    "unit": unit,
                    "display": f"{value} {unit}",
                    "text": text_value,
                    "box": get_box(item),
                    "distance": None,
                    "score": 0.0,
                    "item": item,
                }
            )

        if not quantities:
            return None

        labels = []

        for item in ocr_items:
            text_value = self._item_text(item)

            if not text_value:
                continue

            if label_pattern.search(text_value):
                box = get_box(item)

                if box:
                    labels.append(box)

        for candidate in quantities:

            if candidate["box"] is not None and labels:
                candidate["distance"] = min(
                    distance(candidate["box"], label_box)
                    for label_box in labels
                )

                d = candidate["distance"]

                if d <= 150:
                    candidate["score"] = 100.0
                elif d <= 300:
                    candidate["score"] = 80.0
                elif d <= 600:
                    candidate["score"] = 40.0
                else:
                    candidate["score"] = 5.0

            else:
                candidate["score"] = 1.0

            # Clean standalone quantity.
            if re.fullmatch(
                r"\d+(?:[.,]\d+)?\s*"
                r"(?:kg|kgs|g|gm|gms|mg|ml|l|ltr|litre|litres|cl|"
                r"pcs?|pieces?|units?|items?|counts?|"
                r"condoms?|tablets?|capsules?|bottles?|packs?|"
                r"boxes?|sachets?|pouches?|strips?|rolls?)",
                candidate["text"],
                re.IGNORECASE,
            ):
                candidate["score"] += 10.0

        labelled = [
            candidate
            for candidate in quantities
            if candidate["distance"] is not None
            and candidate["distance"] <= 300
        ]

        if labelled:
            labelled.sort(
                key=lambda candidate: (
                    candidate["score"],
                    -candidate["distance"],
                ),
                reverse=True,
            )
            best = labelled[0]
        else:
            quantities.sort(
                key=lambda candidate: candidate["score"],
                reverse=True,
            )
            best = quantities[0]

        # Preserve the actual label text for verifier context.
        return {
            "value": float(best["value"]),
            "unit": best["unit"],
            "display": best["display"],
            "confidence": 0.95,
            "raw_text": best["text"],
            "bbox": getattr(best["item"], "bbox", None),
        }

    # =============================================================
    # PARTY
    # =============================================================

    def _extract_labeled_party(
        self,
        items: List[OcrTextItem],
        labels: List[str],
    ) -> Optional[Dict[str, Any]]:

        for index, item in enumerate(items):

            text = self._item_text(item)

            for label in labels:

                pattern = (
                    rf"\b{re.escape(label)}\b"
                    r"\s*[:\-]?\s*(.+)"
                )

                match = re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                )

                if match:

                    candidate = (
                        self._clean_party_name(
                            match.group(1)
                        )
                    )

                    # Do not mistake licence numbers or licence
                    # declarations for the manufacturer/packer name.
                    if re.search(
                        r"\b(?:lic|licence|license|no\.?|number)\b",
                        candidate,
                        re.IGNORECASE,
                    ):
                        continue

                    if re.search(
                        r"\b(?:mfg|mfd|manufactur(?:er|ed)?)\b",
                        candidate,
                        re.IGNORECASE,
                    ) and re.search(
                        r"\b(?:lic|licence|license)\b",
                        candidate,
                        re.IGNORECASE,
                    ):
                        continue

                    if self._valid_party_name(
                        candidate
                    ):

                        return {
                            "name": candidate,
                            "confidence": float(
                                getattr(
                                    item,
                                    "confidence",
                                    None,
                                )
                                or 0.85
                            ),
                            "raw_text": text,
                            "bbox": getattr(
                                item,
                                "bbox",
                                None,
                            ),
                        }

                if re.fullmatch(
                    rf"{re.escape(label)}"
                    r"[\s:.#\-]*",
                    text,
                    re.IGNORECASE,
                ):

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
                                    getattr(
                                        next_item,
                                        "confidence",
                                        None,
                                    )
                                    or 0.8
                                ),
                                "raw_text": (
                                    self._item_text(
                                        next_item
                                    )
                                ),
                                "bbox": getattr(
                                    next_item,
                                    "bbox",
                                    None,
                                ),
                            }

        return None

    @staticmethod
    def _clean_party_name(
        value: str,
    ) -> str:

        value = re.sub(
            r"\b(?:country\s+of\s+origin|"
            r"batch\s+number|"
            r"use\s+by\s+date|"
            r"best\s+before|"
            r"mrp|"
            r"incl\.?\s+of\s+all\s+taxes)\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\b(?:license|licence)\s*"
            r"(?:no\.?|number)?\s*[:\-]?"
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

        if not value or len(value) < 2:
            return False

        lower = value.lower()

        blocked_terms = [
            "country of origin",
            "batch number",
            "use by date",
            "best before",
            "mrp",
            "incl. of all taxes",
            "consumer care",
            "customer care",
            "marketed by",
            "sold by",
            "distributed by",
            "brand owner",
            "proprietary",
            "net quantity",
            "ingredients",
            "nutrition",
            "calories",
            "carbohydrate",
            "protein",
            "fat",
        ]

        if any(
            term in lower
            for term in blocked_terms
        ):
            return False

        if re.fullmatch(
            r"[\d\s./\-]+",
            value,
        ):
            return False

        if "@" in value:
            return False

        return True

    # =============================================================
    # DATES
    # =============================================================

    def _extract_date_field(
        self,
        items: List[OcrTextItem],
        labels: List[str],
        exclude_labels: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:

        exclude_labels = exclude_labels or []

        blocked_labels = [
            label.lower()
            for label in exclude_labels
        ]

        blocked_labels += [
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
            "use by",
            "best before",
            "expiry",
            "country of origin",
            "manufacturer",
            "packer",
            "importer",
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

            after_label = re.sub(
                rf"^.*?\b"
                rf"{re.escape(matched_label)}"
                rf"\b",
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

            date_match = re.search(
                r"\b\d{1,2}[/-]"
                r"\d{1,2}[/-]"
                r"\d{2,4}\b",
                after_label,
            )

            if date_match:

                parsed = (
                    self._parse_date_from_text(
                        date_match.group(0)
                    )
                )

                if parsed:

                    parsed.update(
                        {
                            "confidence": float(
                                getattr(
                                    item,
                                    "confidence",
                                    None,
                                )
                                or 0.85
                            ),
                            "raw_text": text,
                            "bbox": getattr(
                                item,
                                "bbox",
                                None,
                            ),
                        }
                    )

                    return parsed

            for distance in range(1, 4):

                candidate_index = (
                    index + distance
                )

                if candidate_index >= len(items):
                    break

                candidate = items[
                    candidate_index
                ]

                candidate_text = (
                    self._item_text(candidate)
                )

                if not candidate_text:
                    continue

                if any(
                    blocked in candidate_text.lower()
                    for blocked in blocked_labels
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

                parsed = (
                    self._parse_date_from_text(
                        date_match.group(0)
                    )
                )

                if not parsed:
                    continue

                parsed.update(
                    {
                        "confidence": min(
                            float(
                                getattr(
                                    item,
                                    "confidence",
                                    None,
                                )
                                or 0.8
                            ),
                            float(
                                getattr(
                                    candidate,
                                    "confidence",
                                    None,
                                )
                                or 0.8
                            ),
                        ),
                        "raw_text": (
                            f"{text} "
                            f"{candidate_text}"
                        ),
                        "bbox": getattr(
                            candidate,
                            "bbox",
                            None,
                        ),
                    }
                )

                return parsed

        return None

    def _extract_best_before(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        result = self._extract_date_field(
            items,
            [
                "best before date",
                "best before",
            ],
            exclude_labels=[
                "date of manufacture",
                "manufacturing date",
                "use by date",
                "use by",
                "date of packing",
                "packing date",
            ],
        )

        if result:
            return result

        for item in items:

            text = self._item_text(item)

            match = re.search(
                r"\bbest\s+before\b"
                r"\s*[:.\-]?\s*"
                r"(.{0,80}?"
                r"(?:months?|month|years?|year)"
                r"(?:\s+from\s+manufacture|\s+from\s+mfg)?"
                r")",
                text,
                re.IGNORECASE,
            )

            if match:

                value = self._clean_text(
                    match.group(1)
                )

                return {
                    "date": value,
                    "value_type": "duration",
                    "duration_text": value,
                    "confidence": float(
                        getattr(
                            item,
                            "confidence",
                            None,
                        )
                        or 0.85
                    ),
                    "raw_text": text,
                    "bbox": getattr(
                        item,
                        "bbox",
                        None,
                    ),
                }

        return None

    # =============================================================
    # DATE PARSER
    # =============================================================

    def _parse_date_from_text(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:

        text = self._clean_text(text)

        match = re.search(
            r"\b(\d{1,2})[/.\-]"
            r"(\d{1,2})[/.\-]"
            r"(\d{2,4})\b",
            text,
        )

        if match:

            day = int(match.group(1))
            month = int(match.group(2))
            year_raw = match.group(3)

            if not (
                1 <= month <= 12
                and 1 <= day <= 31
            ):
                return None

            year = int(year_raw)

            if len(year_raw) == 2:
                year += 2000

            return {
                "date": (
                    f"{day:02d}/"
                    f"{month:02d}/"
                    f"{year:04d}"
                ),
                "day": day,
                "month":
                    self._month_to_name(month),
                "month_number": month,
                "year": year,
            }

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
            r"sep(?:t(?:ember)?)?|"
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
                "month":
                    month_name.title(),
                "month_number":
                    month_number,
                "year": year,
            }

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
                    "month":
                        self._month_to_name(month),
                    "month_number": month,
                    "year": year,
                }

        return None


    # =============================================================
    # CONSUMER CARE
    # =============================================================

    def _extract_consumer_care(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        context_pattern = re.compile(
            r"\b(?:consumer\s+care|"
            r"customer\s+care|"
            r"helpline|"
            r"contact\s+us|"
            r"toll[-\s]?free)\b",
            re.IGNORECASE,
        )

        phone_pattern = re.compile(
            r"(?<!\d)"
            r"(?:\+91[\s\-]?)?"
            r"(?:0[\s\-]?)?"
            r"[6-9]\d{9}"
            r"(?!\d)"
        )

        email_pattern = re.compile(
            r"[A-Za-z0-9._%+\-]+"
            r"@[A-Za-z0-9.\-]+\."
            r"[A-Za-z]{2,}"
        )

        address_pattern = re.compile(
            r"\b(?:p\.?\s*o\.?\s*box|"
            r"post\s+box|"
            r"address|"
            r"write\s+to|"
            r"road|"
            r"street|"
            r"nagar|"
            r"industrial\s+estate|"
            r"phase|"
            r"city|"
            r"state|"
            r"pincode|"
            r"pin\s*code|"
            r"india)\b",
            re.IGNORECASE,
        )

        context_index = None
        phone = None
        email = None
        address = None

        evidence = []

        for index, item in enumerate(items):
            text = self._item_text(item)

            if not text:
                continue

            if context_pattern.search(text):
                context_index = index
                break

        if context_index is None:
            return None

        # Consumer-care declarations are commonly split across
        # multiple OCR lines, so inspect a bounded window.
        window_end = min(
            len(items),
            context_index + 10,
        )

        phone_confidences = []
        email_confidences = []
        address_confidences = []

        address_parts = []

        for item in items[context_index:window_end]:
            text = self._item_text(item)

            if not text:
                continue

            lower = text.lower()

            # Stop at another major declaration.
            if (
                context_index != items.index(item)
                and re.search(
                    r"\b(?:mrp|net\s+quantity|"
                    r"ingredients|nutrition|"
                    r"country\s+of\s+origin|"
                    r"manufactured\s+by|"
                    r"mfd\s+by)\b",
                    lower,
                    re.IGNORECASE,
                )
            ):
                break

            item_conf = float(
                getattr(
                    item,
                    "confidence",
                    None,
                )
                or 0.85
            )

            # Phone numbers
            for raw_phone in phone_pattern.findall(text):
                cleaned = re.sub(
                    r"\D",
                    "",
                    raw_phone,
                )

                if (
                    cleaned.startswith("91")
                    and len(cleaned) == 12
                ):
                    cleaned = cleaned[2:]

                if len(cleaned) == 10:
                    phone = cleaned
                    phone_confidences.append(item_conf)

            # Email
            email_match = email_pattern.search(text)

            if email_match:
                email = email_match.group(0)
                email_confidences.append(item_conf)

            # Address / postal-contact text
            if address_pattern.search(text):
                cleaned_address = self._clean_text(text)

                if (
                    len(cleaned_address) >= 8
                    and cleaned_address not in address_parts
                ):
                    address_parts.append(
                        cleaned_address
                    )
                    address_confidences.append(
                        item_conf
                    )

            # Evidence
            if (
                context_pattern.search(text)
                or phone_pattern.search(text)
                or email_pattern.search(text)
                or address_pattern.search(text)
            ):
                evidence.append({
                    "text": text,
                    "confidence": item_conf,
                })

        if address_parts:
            address = " ".join(address_parts)

        if not phone and not email and not address:
            return None

        confidences = (
            phone_confidences
            + email_confidences
            + address_confidences
        )

        confidence = (
            round(
                sum(confidences) / len(confidences),
                2,
            )
            if confidences
            else 0.80
        )

        return {
            "phone": phone,
            "email": email,
            "address": address,
            "confidence": confidence,
            "raw_text": " | ".join(
                entry["text"]
                for entry in evidence
            ),
            "evidence": evidence,
            "context_seen": True,
        }
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

                value = re.split(
                    r"\b(?:batch|"
                    r"use\s+by|"
                    r"best\s+before|"
                    r"mrp|incl)\b",
                    match.group(1),
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip(" .,:;-")

                if not value:
                    continue

                if "india" in value.lower():
                    value = "India"

                return {
                    "value": value,
                    "confidence": float(
                        getattr(
                            item,
                            "confidence",
                            None,
                        )
                        or 0.9
                    ),
                    "raw_text": text,
                    "bbox": getattr(
                        item,
                        "bbox",
                        None,
                    ),
                }

        return None

    # =============================================================
    # UNIT SALE PRICE
    # =============================================================

    def _extract_unit_sale_price(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        pattern = re.compile(
            r"\b(?:unit\s+(?:sale\s+)?price|"
            r"price\s+per)\b"
            r"\s*[:.\-]?\s*"
            r"(?:₹|rs\.?|inr)?"
            r"\s*"
            r"(\d+(?:[.,]\d{1,2})?)",
            re.IGNORECASE,
        )

        for item in items:

            text = self._item_text(item)

            match = pattern.search(text)

            if not match:
                continue

            value = float(
                match.group(1).replace(
                    ",",
                    "",
                )
            )

            return {
                "value": value,
                "currency": "INR",
                "confidence": float(
                    getattr(
                        item,
                        "confidence",
                        None,
                    )
                    or 0.85
                ),
                "raw_text": text,
                "bbox": getattr(
                    item,
                    "bbox",
                    None,
                ),
            }

        return None

    # =============================================================
    # BARCODE
    # =============================================================

    def _extract_barcode(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        for item in items:

            text = self._item_text(item)

            match = re.search(
                r"\b(?:barcode|ean|upc|isbn|gtin)\b"
                r"\s*[:.\-]?\s*"
                r"(\d{8,14})\b",
                text,
                re.IGNORECASE,
            )

            if match:

                return {
                    "value": match.group(1),
                    "confidence": float(
                        getattr(
                            item,
                            "confidence",
                            None,
                        )
                        or 0.85
                    ),
                    "raw_text": text,
                    "bbox": getattr(
                        item,
                        "bbox",
                        None,
                    ),
                    "labelled": True,
                }

        for item in items:

            text = self._item_text(item)

            if not re.fullmatch(
                r"\d{13}",
                text,
            ):
                continue

            if not self._valid_ean13(text):
                continue

            return {
                "value": text,
                "confidence": float(
                    getattr(
                        item,
                        "confidence",
                        None,
                    )
                    or 0.8
                ),
                "raw_text": text,
                "bbox": getattr(
                    item,
                    "bbox",
                    None,
                ),
                "labelled": False,
                "checksum_valid": True,
            }

        return None

    @staticmethod
    def _valid_ean13(
        code: str,
    ) -> bool:

        if (
            len(code) != 13
            or not code.isdigit()
        ):
            return False

        digits = [
            int(d)
            for d in code
        ]

        total = 0

        for index, digit in enumerate(
            digits[:12]
        ):

            if index % 2 == 0:
                total += digit
            else:
                total += digit * 3

        check = (
            10 - total % 10
        ) % 10

        return check == digits[12]

    # =============================================================
    # FSSAI
    # =============================================================

    def _extract_fssai(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        for item in items:

            text = self._item_text(item)

            match = re.search(
                r"\b(?:fssai\s+"
                r"(?:license|licence|no\.?)?)"
                r"\s*[:.\-]?\s*"
                r"(\d{14})\b",
                text,
                re.IGNORECASE,
            )

            if match:

                return {
                    "value": match.group(1),
                    "confidence": float(
                        getattr(
                            item,
                            "confidence",
                            None,
                        )
                        or 0.9
                    ),
                    "raw_text": text,
                    "bbox": getattr(
                        item,
                        "bbox",
                        None,
                    ),
                }

        return None

    # =============================================================
    # MANUFACTURING LICENSE
    # =============================================================

    def _extract_manufacturing_license(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:

        patterns = [
            re.compile(
                r"\b(?:mfg\.?|manuf\.?|manufacturing)\s+"
                r"(?:lic\.?|license|licence)\s*"
                r"(?:no\.?|number)?\s*[:.\-]?\s*"
                r"([A-Z0-9][A-Z0-9./\-\s]{4,})",
                re.IGNORECASE,
            ),
            re.compile(
                r"\blic\.?\s*no\.?\s*[:.\-]?\s*"
                r"([A-Z0-9][A-Z0-9./\-\s]{4,})",
                re.IGNORECASE,
            ),
        ]

        for item in items:
            text = self._item_text(item)

            if not text:
                continue

            for pattern in patterns:
                match = pattern.search(text)

                if not match:
                    continue

                value = match.group(1)

                value = re.split(
                    r"\b(?:country|batch|use|best|mrp|incl)\b",
                    value,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0]

                value = re.sub(
                    r"\s+",
                    " ",
                    value,
                ).strip(" .,:;-")

                if not value:
                    continue

                if not re.search(r"\d", value):
                    continue

                return {
                    "value": value,
                    "confidence": float(
                        getattr(
                            item,
                            "confidence",
                            None,
                        )
                        or 0.85
                    ),
                    "raw_text": text,
                    "bbox": getattr(
                        item,
                        "bbox",
                        None,
                    ),
                }

        return None

    # =============================================================
    # PRODUCT NAME
    # =============================================================

    def _extract_product_name(
        self,
        items: List[OcrTextItem],
    ) -> Optional[Dict[str, Any]]:
        """
        Extract the most likely product/title name.

        Short title-like OCR is preferred over marketing slogans,
        instructions, addresses, declarations and long sentences.
        """

        rejected_patterns = [
            r"\bmrp\b",
            r"\brs\.?\b",
            r"\bprice\b",
            r"\bnet\s*(?:qty|quantity|wt|weight)\b",
            r"\bquantity\b",
            r"\bqty\b",
            r"\bmanufactur",
            r"\bmfg\b",
            r"\bmanufacturer\b",
            r"\bpack(?:ed|ing|age|aging|size)?\b",
            r"\bpacked\s+by\b",
            r"\bpackaged\s+by\b",
            r"\bpacker\b",
            r"\bbatch\b",
            r"\buse\s*by\b",
            r"\bbest\s*before\b",
            r"\bexpiry\b",
            r"\bexpire\b",
            r"\bincl\.?\b",
            r"\binclusive\b",
            r"\btaxes\b",
            r"\bcountry\s*of\s*origin\b",
            r"\borigin\b",
            r"\bimporter\b",
            r"\bimported\s+by\b",
            r"\bconsumer\s*care\b",
            r"\bcustomer\s*care\b",
            r"\bhelpline\b",
            r"\blicen[cs]e\b",
            r"\bfssai\b",
            r"\bdate\b",
            r"\bnumber\b",
            r"\bno\.?\b",
            r"\bmarketed\s+by\b",
            r"\bsold\s+by\b",
            r"\bdistributed\s+by\b",
            r"\bdistributor\b",
            r"\bbrand\s+owner\b",
            r"\bingredients?\b",
            r"\bnutrition(?:al)?\b",
            r"\benergy\b",
            r"\bcalories?\b",
            r"\bprotein\b",
            r"\bcarbohydrate\b",
            r"\bsugars?\b",
            r"\btotal\s+fat\b",
            r"\bsodium\b",
            r"\bplease\b",
            r"\bcarefully\b",
            r"\bhereby\b",
            r"\binstructions?\b",
            r"\brefer\s+to\b",
            r"\bdetails?\b",
            r"\bmethod\b",
            r"\bprotection\b",
            r"\bprotected\b",
            r"\bcontact\s+us\b",
            r"\bwebsite\b",
            r"\bwww\.",
            r"\.com\b",
            r"@",
        ]

        # Common marketing/instructional sentence signals.
        sentence_patterns = [
            r"\bcan be\b",
            r"\bto\s+(?:the|a|an|use)\b",
            r"\bfor\s+(?:single|use|details|more)\b",
            r"\bplease\b",
            r"\bwith\b",
            r"\band\b",
            r"\bcarefully\b",
            r"\bread\b",
            r"\bmethod of\b",
            r"\bprotection against\b",
            r"[.!?]$",
        ]

        # Brand/product title indicators.
        brand_patterns = [
            r"\bdurex\b",
            r"\bbingo\b",
            r"\bitc\b",
            r"\bparle\b",
        ]

        candidates = []

        for index, item in enumerate(items):
            text_value = self._item_text(item).strip()

            if len(text_value) < 2 or len(text_value) > 60:
                continue

            if any(
                re.search(pattern, text_value, re.IGNORECASE)
                for pattern in rejected_patterns
            ):
                continue

            if any(
                ord(ch) > 127
                for ch in text_value
            ):
                continue

            # Product titles should usually not be full sentences.
            sentence_hits = sum(
                bool(re.search(pattern, text_value, re.IGNORECASE))
                for pattern in sentence_patterns
            )

            if sentence_hits >= 2:
                continue

            # Avoid long prose even when no blacklist term matched.
            word_count = len(text_value.split())

            if word_count > 8:
                continue

            alpha_count = sum(
                ch.isalpha()
                for ch in text_value
            )

            if alpha_count < 2:
                continue

            confidence = float(
                getattr(item, "confidence", None)
                or 0.0
            )

            score = confidence * 10.0

            # Strong preference for compact product-title shapes.
            if 1 <= word_count <= 5:
                score += 8.0

            if 2 <= word_count <= 4:
                score += 5.0

            # Uppercase packaging text is often a product descriptor.
            if text_value.upper() == text_value:
                score += 3.0

            # Title Case is also useful.
            if all(
                word[:1].isupper()
                for word in text_value.split()
                if word and word[0].isalpha()
            ):
                score += 2.0

            # Strong product-brand signal.
            brand_hits = sum(
                bool(re.search(pattern, text_value, re.IGNORECASE))
                for pattern in brand_patterns
            )

            score += brand_hits * 12.0

            # Penalize prose-like punctuation.
            if re.search(r"[,;:!?]", text_value):
                score -= 4.0

            # Penalize very long text.
            if len(text_value) > 45:
                score -= 4.0

            candidates.append(
                (
                    score,
                    index,
                    item,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        _, _, item = candidates[0]

        text_value = self._item_text(item)

        return {
            "value": text_value,
            "confidence": float(
                getattr(item, "confidence", None)
                or 0.7
            ),
            "raw_text": text_value,
            "bbox": getattr(item, "bbox", None),
        }

    # =============================================================
    # UTILITIES
    # =============================================================

    def _normalize_unit(
        self,
        unit: str,
    ) -> str:

        return self.unit_normalization.get(
            str(unit).lower().strip(),
            str(unit).lower().strip(),
        )

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
            str(month_name).lower()
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


async def extract_fields(
    ocr_texts: List[OcrTextItem],
) -> Dict[str, Any]:

    service = FieldExtractorService()

    return await service.extract_fields(
        ocr_texts
    )
