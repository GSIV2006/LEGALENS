"""OCR Data model for storing extracted text from images."""
import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class OcrData(Base):
    """
    Model for storing OCR-extracted text data.

    Stores individual text detections with confidence scores and bounding boxes.
    """

    __tablename__ = "ocr_data"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=True)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    bounding_box = Column(Text, nullable=True)  # JSON stored as string
    source_image = Column(String(255), nullable=True)  # e.g., "front.jpg"
    page_number = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    inspection = relationship("Inspection", back_populates="ocr_data")

    def __init__(self, **kwargs):
        """Custom init to handle bbox serialization."""
        if "bounding_box" in kwargs and isinstance(kwargs["bounding_box"], list):
            kwargs["bounding_box"] = json.dumps(kwargs["bounding_box"])
        super().__init__(**kwargs)

    @property
    def bbox(self) -> Optional[List[List[float]]]:
        """Get bounding box as list (deserialized)."""
        if self.bounding_box:
            try:
                return json.loads(self.bounding_box)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @bbox.setter
    def bbox(self, value):
        """Set bounding box from list (serialized)."""
        if value and isinstance(value, list):
            self.bounding_box = json.dumps(value)
        else:
            self.bounding_box = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "bounding_box": self.bbox,
            "source_image": self.source_image,
            "page_number": self.page_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        text_preview = self.text[:50] if self.text else ""
        return f"<OcrData(id={self.id}, confidence={self.confidence}, text='{text_preview}...')>"
