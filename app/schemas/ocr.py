"""OCR-related schemas."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, HttpUrl


class OcrTextItem(BaseModel):
    """Single OCR text detection item."""
    text: str
    confidence: Optional[float] = None  # 0.0 to 1.0
    bbox: Optional[List[List[float]]] = None  # [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
    image_name: Optional[str] = None
    page_number: int = 1


class OcrDataSubmit(BaseModel):
    """
    Schema for submitting OCR data from external OCR service.

    Expects the format that our OCR teammates will produce:
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
    """
    texts: List[OcrTextItem]


class OcrDataResponse(BaseModel):
    """Schema for OCR data response."""
    id: int
    inspection_id: Optional[int]
    text: str
    confidence: Optional[float]
    bounding_box: Optional[List[List[float]]]
    source_image: Optional[str]
    page_number: int
    created_at: datetime

    class Config:
        from_attributes = True


class OcrSubmitResponse(BaseModel):
    """Response for OCR data submission."""
    message: str
    count: int
    inspection_id: int


class OcrRunResult(BaseModel):
    """Result from running OCR (mock or real)."""
    success: bool
    message: str
    image_name: str
    texts: List[OcrTextItem] = []
    error: Optional[str] = None


class OcrJobResponse(BaseModel):
    """Response after running OCR on an inspection."""
    inspection_id: int
    ocr_status: str
    message: str
    text_count: int
