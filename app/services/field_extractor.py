"""
Field Extraction Service

Extracts structured fields from OCR text using regex and string processing.

Extracts:
- product_name
- mrp (Maximum Retail Price)
- net_quantity_value, net_quantity_unit
- manufacturer_name
- manufacturer_address
- packer information
- importer information
- manufacturing date (month/year)
- packing date
- import date
- consumer_care (phone, email, address)
- country_of_origin
- unit_sale_price

Designed to work with OCR output format from our OCR teammates.
"""
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from app.schemas.ocr import OcrTextItem


class FieldExtractorService:
    """
    Service for extracting structured fields from OCR text.

    Uses regex patterns and string processing to identify and extract
    common fields found on packaged commodity labels in India.
    """

    def __init__(self):
        """Initialize field extractor with regex patterns."""
        self.patterns = self._init_patterns()
        self.currency_patterns = [
            (r'₹|inr|indian\s+rupee', 'INR'),
            (r'rs\.?', 'INR'),
            (r'usd|$\s*', 'USD'),
            (r'eur|€', 'EUR'),
        ]
        self.unit_normalization = {
            'g': 'g', 'gm': 'g', 'grams': 'g',
            'kg': 'kg', 'KG': 'kg', 'kgs': 'kg',
            'ml': 'ml', 'mL': 'ml', 'milliliter': 'ml', 'millilitre': 'ml',
            'l': 'L', 'L': 'L', 'liter': 'L', 'litre': 'L',
        }

    def _init_patterns(self) -> Dict[str, Any]:
        """Initialize regex patterns for field extraction."""
        return {
            # MRP - Maximum Retail Price
            "mrp": [
                # "MRP ₹120" or "MRP Rs.120" or "MRP INR 120"
                r'(?:mrp|maximum\s+retail\s+price|max\s+retail\s+price)[:\s]*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{2})?)',
                # "₹120/-" or "Rs.120/-" with MRP context
                r'(?:₹|rs\.?|inr)\s*(\d+(?:\.\d{2})?)\s*(?:/-|inclusive|inclusive of all taxes)',
                # Simple price patterns with MRP context
                r'(?:mrp)[:\s]*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{2})?)',
            ],

            # Net Quantity
            "net_quantity": [
                # "Net Qty 500 g" or "Net Quantity: 500g"
                r'(?:net\s+(?:qty|quantity))[:\s]*([\d,.]+)\s*(g|gm|grams|kg|KG|kg|m[lL]|[lL]iter?|ml|L)',
                # " 중량 500g" - sometimes just quantity with unit
                r'(?:qty|quantity)[:\s]*([\d,.]+)\s*(g|gm|grams|kg|KG|kg|m[lL]|[lL]iter?|ml|L)',
            ],

            # Product Name
            "product_name": [
                # Often at the top of the label in large text
                # This is heuristic - real extraction would need better CV
                r'^(.*?)(?:\s+-\s+|\s+[-:]\s+|Brand:|\n)',
            ],

            # Manufacturer
            "manufacturer": [
                r'(?:manufacturer|prepared\s+by|manufactured\s+by|made\s+by)[:\s]*([^\n]+)',
                r'(?:mfg\.?|manuf\.?)[:\s]*([^\n]+)',
            ],

            # Manufacturer Address
            "manufacturer_address": [
                r'(?:address|addr\.?)[:\s]*([^\n]+)',
                r'(?:manufacturer\s+address|plant\s+address|manufacturing\s+address)[:\n]*([^\n]+)',
            ],

            # Packer
            "packer": [
                r'(?:packer|packaged\s+by|packed\s+by)[:\s]*([^\n]+)',
            ],

            # Importer
            "importer": [
                r'(?:importer|imported\s+by|imported\s+for)[:\s]*([^\n]+)',
            ],

            # Month/Year of Manufacture
            "manufacturing_date": [
                # "Mfg. Date: Jan 2024" or "Month/Year of packing: 01/2024"
                r'(?:mfg\.?\s*(?:date|month/year)|month/year\s+of\s+(?:packing|manufacture|manufactured)|mfg\s+date)[:\s]*([a-zA-Z]{3,9}\s*\d{4}|\d{2}/\d{2,4}|\d{4}-\d{2})',
                # "Best before: Jan 2024"
                r'(?:best\s+before|best\s+before\s+date|expiry)[:\s]*([a-zA-Z]{3,9}\s*\d{4})',
            ],

            # Packing Date
            "packing_date": [
                r'(?:packing\s+date|pack\s+date|date\s+of\s+packing)[:\s]*([a-zA-Z]{3,9}\s*\d{4}|\d{2}/\d{2,4}|\d{4}-\d{2}-\d{2})',
            ],

            # Import Date
            "import_date": [
                r'(?:import\s+date|date\s+of\s+import)[:\s]*([a-zA-Z]{3,9}\s*\d{4}|\d{2}/\d{2,4})',
            ],

            # Consumer Care
            "consumer_care": [
                # Phone
                r'(?:consumer\s+care|consumer\s+care\s+no\.?|helpline|customer\s+care)[:\s]*(\d{10,15})',
                r'(?:telephone|phone|contact)[:\s]*(\+?\d{10,15})',
                # Email
                r'(?:email|e-mail)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                # Address
                r'(?:consumer\s+care\s+address|address\s+for\s+consumer\s+care)[:\n]*([^\n]+)',
            ],

            # Country of Origin
            "country_of_origin": [
                r'(?:country\s+of\s+origin|country\s+of\s+manufacture|made\s+in|origin)[:\s]*([A-Za-z\s]+)',
            ],

            # Unit Sale Price (for loose items)
            "unit_sale_price": [
                r'(?:unit\s+(?:sale|price)|price\s+per)[:\s]*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{2})?)',
            ],

            # Barcode
            "barcode": [
                r'(?:barcode|ean|upc|isbn|gtin)[:\s]*(\d{8,14})',
                r'\b(\d{13})\b',  # 13-digit barcode
            ],

            # FSSAI License (food products)
            "fssai_license": [
                r'(?:fssai\s+license|fssai\s+licence|fssai\s+no\.?)[:\s]*([A-Z0-9]{14})',
            ],

            # Manufacturing License
            "manufacturing_license": [
                r'(?:mfg\.?\s+license|mfg\.?\s+licence|manufacturing\s+license|license\s+no\.?)[:\s]*([A-Z0-9\-]+)',
            ],
        }

    async def extract_fields(
        self,
        ocr_texts: List[OcrTextItem],
        images_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured fields from OCR text items.

        Args:
            ocr_texts: List of OCR text items from the OCR service
            images_data: Optional additional image metadata

        Returns:
            Dictionary with extracted fields and metadata
        """
        # Combine all text for analysis
        all_text = " ".join([item.text for item in ocr_texts])

        # Also analyze by source image for better context
        text_by_image: Dict[str, str] = {}
        for item in ocr_texts:
            img = item.image_name or "unknown"
            if img not in text_by_image:
                text_by_image[img] = ""
            text_by_image[img] += " " + item.text

        extracted = {
            "product_name": None,
            "mrp": None,
            "currency": "INR",
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
            "consumer_care_phone": None,
            "consumer_care_email": None,
            "consumer_care_address": None,
            "country_of_origin": None,
            "unit_sale_price": None,
            "barcode": None,
            "fssai_license": None,
            "manufacturing_license": None,
            "extracted_fields": {},  # For storing raw extractions
            "confidence": 0.0,
            "extraction_method": "regex",
            "extracted_at": datetime.utcnow().isoformat(),
        }

        # Track extraction confidence
        total_confidence = 0.0
        fields_found = 0

        # Extract MRP
        mrp_result = self._extract_mrp(all_text, ocr_texts)
        if mrp_result:
            extracted["mrp"] = mrp_result["value"]
            extracted["currency"] = mrp_result.get("currency", "INR")
            total_confidence += mrp_result.get("confidence", 0.9)
            fields_found += 1
            extracted["extracted_fields"]["mrp"] = mrp_result

        # Extract Net Quantity
        qty_result = self._extract_net_quantity(all_text, ocr_texts)
        if qty_result:
            extracted["net_quantity_value"] = qty_result["value"]
            extracted["net_quantity_unit"] = qty_result["unit"]
            total_confidence += qty_result.get("confidence", 0.9)
            fields_found += 1
            extracted["extracted_fields"]["net_quantity"] = qty_result

        # Extract Manufacturer
        mfg_result = self._extract_manufacturer(all_text)
        if mfg_result:
            extracted["manufacturer_name"] = mfg_result.get("name")
            extracted["manufacturer_address"] = mfg_result.get("address")
            total_confidence += mfg_result.get("confidence", 0.85)
            fields_found += 1
            extracted["extracted_fields"]["manufacturer"] = mfg_result

        # Extract Dates
        mfg_date = self._extract_date(all_text, "manufacturing_date")
        if mfg_date:
            extracted["manufacturing_date"] = mfg_date["date"]
            extracted["manufacturing_month"] = mfg_date.get("month")
            extracted["manufacturing_year"] = mfg_date.get("year")
            total_confidence += mfg_date.get("confidence", 0.85)
            fields_found += 1
            extracted["extracted_fields"]["manufacturing_date"] = mfg_date

        packing_date = self._extract_date(all_text, "packing_date")
        if packing_date:
            extracted["packing_date"] = packing_date["date"]
            total_confidence += packing_date.get("confidence", 0.85)
            fields_found += 1
            extracted["extracted_fields"]["packing_date"] = packing_date

        # Extract Consumer Care
        cc_result = self._extract_consumer_care(all_text)
        if cc_result:
            if cc_result.get("phone"):
                extracted["consumer_care_phone"] = cc_result["phone"]
                fields_found += 1
            if cc_result.get("email"):
                extracted["consumer_care_email"] = cc_result["email"]
                fields_found += 1
            if cc_result.get("address"):
                extracted["consumer_care_address"] = cc_result["address"]
                fields_found += 1
            total_confidence += cc_result.get("confidence", 0.8)
            extracted["extracted_fields"]["consumer_care"] = cc_result

        # Extract Country of Origin
        country = self._extract_country_of_origin(all_text)
        if country:
            extracted["country_of_origin"] = country
            total_confidence += 0.9
            fields_found += 1
            extracted["extracted_fields"]["country_of_origin"] = {"value": country}

        # Extract other fields
        unit_price = self._extract_unit_sale_price(all_text)
        if unit_price:
            extracted["unit_sale_price"] = unit_price
            total_confidence += 0.85
            fields_found += 1
            extracted["extracted_fields"]["unit_sale_price"] = {"value": unit_price}

        barcode = self._extract_barcode(all_text)
        if barcode:
            extracted["barcode"] = barcode
            total_confidence += 0.9
            fields_found += 1
            extracted["extracted_fields"]["barcode"] = {"value": barcode}

        fssai = self._extract_fssai_license(all_text)
        if fssai:
            extracted["fssai_license"] = fssai
            total_confidence += 0.9
            fields_found += 1
            extracted["extracted_fields"]["fssai_license"] = {"value": fssai}

        mfg_license = self._extract_manufacturing_license(all_text)
        if mfg_license:
            extracted["manufacturing_license"] = mfg_license
            total_confidence += 0.9
            fields_found += 1
            extracted["extracted_fields"]["manufacturing_license"] = {"value": mfg_license}

        # Calculate average confidence
        if fields_found > 0:
            extracted["confidence"] = round(total_confidence / fields_found, 2)

        # Normalize quantity unit
        if extracted["net_quantity_unit"]:
            extracted["net_quantity_unit"] = self._normalize_unit(
                extracted["net_quantity_unit"]
            )

        return extracted

    def _extract_mrp(self, text: str, ocr_items: List[OcrTextItem]) -> Optional[Dict]:
        """Extract MRP (Maximum Retail Price) from text."""
        for pattern in self.patterns["mrp"]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = float(match.group(1).replace(",", ""))
                # Find the source text for evidence
                source_text = ""
                for item in ocr_items:
                    if re.search(pattern, item.text, re.IGNORECASE):
                        source_text = item.text
                        break

                return {
                    "value": value,
                    "currency": "INR",
                    "confidence": 0.95,
                    "raw_text": source_text or match.group(0),
                    "pattern_used": pattern,
                }

        return None

    def _extract_net_quantity(self, text: str, ocr_items: List[OcrTextItem]) -> Optional[Dict]:
        """Extract net quantity from text."""
        for pattern in self.patterns["net_quantity"]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = float(match.group(1).replace(",", ""))
                unit_raw = match.group(2)
                unit = self._normalize_unit(unit_raw)

                # Find source text for evidence
                source_text = ""
                for item in ocr_items:
                    if re.search(pattern, item.text, re.IGNORECASE):
                        source_text = item.text
                        break

                return {
                    "value": value,
                    "unit": unit,
                    "unit_raw": unit_raw,
                    "confidence": 0.93,
                    "raw_text": source_text or match.group(0),
                    "pattern_used": pattern,
                }

        return None

    def _extract_manufacturer(self, text: str) -> Optional[Dict]:
        """Extract manufacturer information."""
        for pattern in self.patterns["manufacturer"]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.sub(r'\s+', ' ', name)
                return {
                    "name": name,
                    "confidence": 0.88,
                    "raw_text": match.group(0),
                }

        return None

    def _extract_date(self, text: str, date_type: str) -> Optional[Dict]:
        """Extract date information."""
        patterns = self.patterns.get(date_type, [])
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                date_str = match.group(1).strip()
                result = {
                    "raw_text": match.group(0),
                    "confidence": 0.85,
                }

                # Parse the date
                parsed = self._parse_date(date_str)
                if parsed:
                    result.update(parsed)

                return result

        return None

    def _parse_date(self, date_str: str) -> Optional[Dict]:
        """Parse various date formats."""
        date_str = date_str.strip()

        # Month Year format: "Jan 2024", "January 2024"
        month_year_match = re.match(
            r'^([a-zA-Z]{3,9})\s+(\d{4})$',
            date_str,
            re.IGNORECASE
        )
        if month_year_match:
            month_name = month_year_match.group(1)
            year = int(month_year_match.group(2))
            month_num = self._month_to_number(month_name)
            if month_num:
                return {
                    "date": f"{month_name} {year}",
                    "month": month_name,
                    "month_number": month_num,
                    "year": year,
                }

        # DD/MM/YYYY or DD/MM/YY format
        slash_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
        if slash_match:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year_str = slash_match.group(3)
            year = int(year_str) if len(year_str) == 4 else (2000 + int(year_str))
            month_name = self._month_to_name(month)
            return {
                "date": date_str,
                "day": day,
                "month": month_name,
                "month_number": month,
                "year": year,
            }

        # YYYY-MM-DD format
        iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
            month_name = self._month_to_name(month)
            return {
                "date": date_str,
                "day": day,
                "month": month_name,
                "month_number": month,
                "year": year,
            }

        # Just return the raw string if we can't parse it
        return {"date": date_str}

    def _month_to_number(self, month_name: str) -> Optional[int]:
        """Convert month name to number."""
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        return months.get(month_name.lower())

    def _month_to_name(self, month_num: int) -> Optional[str]:
        """Convert month number to name."""
        months = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        return months.get(month_num)

    def _extract_consumer_care(self, text: str) -> Optional[Dict]:
        """Extract consumer care information."""
        result = {"phone": None, "email": None, "address": None}

        # Extract phone
        for pattern in self.patterns["consumer_care"][:2]:  # Phone patterns
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["phone"] = match.group(1).strip()
                break

        # Extract email
        email_match = re.search(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            text
        )
        if email_match:
            result["email"] = email_match.group(0)

        # Extract address for consumer care
        for pattern in self.patterns["consumer_care"][2:]:  # Address patterns
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result["address"] = match.group(1).strip()
                break

        if any(result.values()):
            result["confidence"] = 0.82
            return result

        return None

    def _extract_country_of_origin(self, text: str) -> Optional[str]:
        """Extract country of origin."""
        for pattern in self.patterns["country_of_origin"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                country = match.group(1).strip()
                # Common variations
                if 'india' in country.lower():
                    return 'India'
                return country
        return None

    def _extract_unit_sale_price(self, text: str) -> Optional[float]:
        """Extract unit sale price."""
        for pattern in self.patterns["unit_sale_price"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    def _extract_barcode(self, text: str) -> Optional[str]:
        """Extract barcode/GTIN."""
        for pattern in self.patterns["barcode"]:
            match = re.search(pattern, text)
            if match:
                code = match.group(1)
                # Validate barcode length
                if len(code) in [8, 12, 13, 14]:
                    return code
        return None

    def _extract_fssai_license(self, text: str) -> Optional[str]:
        """Extract FSSAI license number."""
        match = re.search(r'[A-Z0-9]{14}', text)
        if match:
            code = match.group(0)
            # FSSAI license pattern validation
            if re.match(r'^[A-Z]{3}[0-9]{4}[A-Z]{4}[0-9]{4}[A-Z]{3}$', code):
                return code
        return None

    def _extract_manufacturing_license(self, text: str) -> Optional[str]:
        """Extract manufacturing license number."""
        for pattern in self.patterns["manufacturing_license"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit of measurement."""
        unit_lower = unit.lower().strip()
        return self.unit_normalization.get(unit_lower, unit_lower)

    def extract_single_field(
        self,
        field_name: str,
        text: str,
        ocr_items: Optional[List[OcrTextItem]] = None,
    ) -> Optional[Dict]:
        """
        Extract a single field from text.

        Useful for testing specific extractions.
        """
        if field_name not in self.patterns:
            return None

        for pattern in self.patterns[field_name]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return {
                    "value": match.group(1) if match.lastindex else match.group(0),
                    "confidence": 0.9,
                    "raw_text": match.group(0),
                    "pattern_used": pattern,
                }

        return None


# Convenience function
async def extract_fields(
    ocr_texts: List[OcrTextItem],
) -> Dict[str, Any]:
    """
    Convenience function to extract fields from OCR text.

    Args:
        ocr_texts: List of OCR text items

    Returns:
        Dictionary with extracted fields
    """
    service = FieldExtractorService()
    return await service.extract_fields(ocr_texts)
