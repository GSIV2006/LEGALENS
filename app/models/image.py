"""Image Evidence model for storing uploaded package images."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ImageEvidence(Base):
    """
    Model for storing uploaded package images.

    Supports different views: front, back, left, right, top, bottom, other.
    """

    __tablename__ = "image_evidence"

    class ViewType:
        """Supported image view types."""
        FRONT = "front"
        BACK = "back"
        LEFT = "left"
        RIGHT = "right"
        TOP = "top"
        BOTTOM = "bottom"
        OTHER = "other"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=True)
    view_type = Column(String(50), nullable=False)  # front, back, left, right, top, bottom, other
    filename = Column(String(500), nullable=False)  # Original filename
    storage_path = Column(String(500), nullable=True)  # Path in storage
    storage_url = Column(String(500), nullable=True)  # URL for access (if applicable)
    content_type = Column(String(100), nullable=True)  # e.g., "image/jpeg"
    file_size = Column(Integer, nullable=True)  # Size in bytes
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    inspection = relationship("Inspection", back_populates="images")

    def __repr__(self) -> str:
        return f"<ImageEvidence(id={self.id}, view_type={self.view_type}, filename={self.filename})>"
