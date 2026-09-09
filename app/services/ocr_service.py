"""
LEGALENS OCR Service

Adapter between the project's PaddleOCR 3.x engine and the
LEGALENS backend OCR schema.

The compliance, extraction, database, and router layers should
not need to know anything about PaddleOCR internals.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.schemas.ocr import OcrTextItem, OcrDataSubmit
from app.config import settings


class OcrService:
    """
    OCR integration layer for LEGALENS.

    Uses the working PaddleOCR engine supplied by the OCR teammate
    and converts its output into the backend's standard format.
    """

    def __init__(self):
        self.config = {
            "supported_formats": ["jpg", "jpeg", "png", "webp"],
            "max_image_size": 50 * 1024 * 1024,
            "default_language": "en",
        }

        self._ocr_engine = None

    def _get_ocr_engine(self):
        """
        Lazily import the OCR engine.

        This prevents PaddleOCR from loading during application
        startup and keeps the service easier to test.
        """
        if self._ocr_engine is None:
            from ocr_engine import run_ocr
            self._ocr_engine = run_ocr

        return self._ocr_engine

    async def run_ocr(
        self,
        image_path: str,
        image_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run real PaddleOCR and convert its results to LEGALENS format.
        """

        if not os.path.exists(image_path):
            return []

        if image_name is None:
            image_name = os.path.basename(image_path)

        # Validate extension
        if not self.validate_image_format(image_name):
            return []

        # Check file size
        try:
            file_size = os.path.getsize(image_path)
        except OSError:
            return []

        if file_size > self.config["max_image_size"]:
            return []

        # Temporary output file for the OCR engine.
        output_dir = Path(settings.UPLOAD_DIR) / "ocr_results"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{Path(image_name).stem}_ocr.json"

        # Use the teammate's working PaddleOCR engine.
        engine = self._get_ocr_engine()
        raw_results = engine(
            image_path,
            str(output_file),
        )

        # Normalize into the backend schema.
        normalized = []

        for item in raw_results:
            normalized.append(
                {
                    "text": str(item.get("text", "")).strip(),
                    "confidence": float(item.get("confidence", 0.0)),
                    "bbox": item.get("bbox", []),
                    "image_name": image_name,
                    "page_number": 1,
                }
            )

        return normalized

    async def process_image_from_bytes(
        self,
        image_bytes: bytes,
        image_name: str,
        temp_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process uploaded image bytes through the real OCR engine.
        """

        if temp_dir is None:
            temp_dir = str(Path(settings.UPLOAD_DIR) / "ocr_temp")

        temp_path = Path(temp_dir) / image_name
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "wb") as f:
            f.write(image_bytes)

        try:
            return await self.run_ocr(
                str(temp_path),
                image_name,
            )
        finally:
            # Remove temporary file after OCR.
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def validate_image_format(self, filename: str) -> bool:
        """Validate supported image extensions."""

        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in self.config["supported_formats"]

    def get_supported_formats(self) -> List[str]:
        return self.config["supported_formats"].copy()


async def run_ocr(image_path: str) -> List[Dict[str, Any]]:
    """Convenience function."""

    service = OcrService()
    return await service.run_ocr(image_path)


def submit_ocr_data(
    inspection_id: int,
    ocr_json: OcrDataSubmit,
    db: Any,
) -> int:
    """
    Save externally supplied OCR data into the database.
    """

    from app.models.ocr_data import OcrData

    count = 0

    for text_item in ocr_json.texts:
        ocr_data = OcrData(
            inspection_id=inspection_id,
            text=text_item.text,
            confidence=text_item.confidence,
            bounding_box=text_item.bbox,
            source_image=text_item.image_name,
            page_number=text_item.page_number,
        )

        db.add(ocr_data)
        count += 1

    db.commit()

    return count


# Global service instance
ocr_service = OcrService()