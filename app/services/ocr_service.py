"""
OCR Service - Integration Layer

This module provides the OCR integration layer.

IMPORTANT: Our OCR teammates will replace ONLY the internal implementation
of this service. The rest of the backend MUST NOT need modification when
real OCR is connected.

Expected OCR output structure:
{
    "texts": [
        {
            "text": "MRP ₹120 incl. of all taxes",
            "confidence": 0.97,
            "bbox": [[10,20],[300,20],[300,50],[10,50]],
            "image_name": "back.jpg"
        }
    ]
}

For now, this is a MOCK/STUB implementation.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import numpy as np

from app.schemas.ocr import OcrTextItem, OcrDataSubmit
from app.config import settings


class OcrService:
    """
    OCR Service - Integration layer for optical character recognition.

    This class provides a clean interface for OCR operations.
    The actual OCR implementation can be swapped without affecting
    the rest of the backend.
    """

    def __init__(self):
        """Initialize OCR service with configuration."""
        self.config = {
            "supported_formats": ["jpg", "jpeg", "png", "webp"],
            "max_image_size": 50 * 1024 * 1024,  # 50MB
            "default_language": "eng+hin",  # English + Hindi for Indian labels
        }

    async def run_ocr(
        self,
        image_path: str,
        image_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run OCR on an image file.

        Args:
            image_path: Path to the image file
            image_name: Optional name for the image (for reference)

        Returns:
            List of text detections with confidence and bounding boxes

        Note:
            This is a MOCK implementation. OCR teammates will replace
            this with real PaddleOCR/OpenCV implementation.
        """
        # Validate image exists
        if not os.path.exists(image_path):
            return []

        # Get image name from path if not provided
        if image_name is None:
            image_name = os.path.basename(image_path)

        # MOCK OCR IMPLEMENTATION
        # In production, this would use PaddleOCR, Tesseract, or similar
        mock_texts = self._generate_mock_ocr_results(image_path, image_name)

        return mock_texts

    def _generate_mock_ocr_results(
        self,
        image_path: str,
        image_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate mock OCR results for development/testing.

        In production, replace with actual OCR engine.
        """
        # Try to simulate realistic OCR output based on image characteristics
        # For now, return a set of mock results that simulate what real OCR would find

        mock_results = [
            {
                "text": "MRP ₹120 inclusive of all taxes",
                "confidence": 0.95,
                "bbox": [[50, 100], [350, 100], [350, 130], [50, 130]],
                "image_name": image_name,
            },
            {
                "text": "Net Qty 500 g",
                "confidence": 0.93,
                "bbox": [[50, 150], [200, 150], [200, 175], [50, 175]],
                "image_name": image_name,
            },
            {
                "text": "Mfg. License No. K2012220012345",
                "confidence": 0.88,
                "bbox": [[50, 200], [300, 200], [300, 220], [50, 220]],
                "image_name": image_name,
            },
            {
                "text": "Country of Origin: India",
                "confidence": 0.91,
                "bbox": [[50, 250], [250, 250], [250, 270], [50, 270]],
                "image_name": image_name,
            },
        ]

        return mock_results

    async def process_image_from_bytes(
        self,
        image_bytes: bytes,
        image_name: str,
        temp_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process an image from bytes (for uploaded files).

        Args:
            image_bytes: Raw image bytes
            image_name: Name for the image
            temp_dir: Optional temp directory for storing image

        Returns:
            List of OCR text detections
        """
        # Save to temp file if temp_dir provided, else process in memory
        if temp_dir:
            temp_path = Path(temp_dir) / image_name
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            return await self.run_ocr(str(temp_path), image_name)
        else:
            # For in-memory processing (mock)
            return self._generate_mock_ocr_results("", image_name)

    def validate_image_format(self, filename: str) -> bool:
        """Validate that the image format is supported."""
        ext = filename.lower().split(".")[-1]
        return ext in self.config["supported_formats"]

    def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats."""
        return self.config["supported_formats"].copy()


# Convenience function for running OCR
async def run_ocr(image_path: str) -> List[Dict[str, Any]]:
    """
    Convenience function to run OCR on an image.

    Args:
        image_path: Path to the image file

    Returns:
        List of text detections
    """
    service = OcrService()
    return await service.run_ocr(image_path)


def submit_ocr_data(
    inspection_id: int,
    ocr_json: OcrDataSubmit,
    db: Any,
) -> int:
    """
    Submit pre-extracted OCR data to the database.

    This function allows our OCR teammates to send already-processed
    OCR results directly without going through the mock OCR.

    Args:
        inspection_id: ID of the inspection
        ocr_json: OCR data in the expected format
        db: Database session

    Returns:
        Number of OCR items saved
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


# Create service instance for use
ocr_service = OcrService()
