"""Inspection model for compliance checking."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Inspection(Base):
    """Inspection model for tracking compliance checks."""

    __tablename__ = "inspections"

    class Status:
        """Inspection status constants."""
        PROCESSING = "PROCESSING"
        COMPLIANT = "COMPLIANT"
        NON_COMPLIANT = "NON_COMPLIANT"
        MANUAL_REVIEW = "MANUAL_REVIEW"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Status and scoring
    status = Column(String(50), default=Status.PROCESSING)
    overall_score = Column(Float, nullable=True)  # Confidence score 0-1
    ruleset_version = Column(String(100), default="1.0.0")

    # Notes and metadata
    notes = Column(Text, nullable=True)
    ocr_status = Column(String(50), nullable=True)  # completed, failed, pending
    extraction_status = Column(String(50), nullable=True)  # completed, failed, pending
    compliance_status = Column(String(50), nullable=True)  # completed, pending

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="inspections")
    inspector_user = relationship("User", back_populates="inspections")
    ocr_data = relationship("OcrData", back_populates="inspection", cascade="all, delete-orphan")
    images = relationship("ImageEvidence", back_populates="inspection", cascade="all, delete-orphan")
    compliance_checks = relationship("ComplianceCheck", back_populates="inspection", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Inspection(id={self.id}, status={self.status}, product_id={self.product_id})>"
