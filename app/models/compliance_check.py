"""Compliance Check and Override models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class ComplianceCheck(Base):
    """
    Individual compliance check result for a rule against extracted fields.
    """

    __tablename__ = "compliance_checks"

    class Status:
        """Check result statuses."""
        PASS = "PASS"
        FAIL = "FAIL"
        MANUAL_REVIEW = "MANUAL_REVIEW"
        NOT_APPLICABLE = "NOT_APPLICABLE"
        NOT_VERIFIED = "NOT_VERIFIED"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), nullable=True)

    # Check result
    rule_code = Column(String(50), nullable=False)
    field_name = Column(String(255), nullable=False)
    status = Column(String(50), default=Status.NOT_VERIFIED)
    message = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)  # Detection confidence 0-1
    evidence = Column(Text, nullable=True)  # Extracted text that was checked

    # Metadata
    check_details = Column(JSON, nullable=True)  # Additional details as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inspection = relationship("Inspection", back_populates="compliance_checks")
    rule = relationship("Rule", back_populates="compliance_checks")
    overrides = relationship("ComplianceOverride", back_populates="check")

    def __repr__(self) -> str:
        return f"<ComplianceCheck(id={self.id}, rule={self.rule_code}, status={self.status})>"


class ComplianceOverride(Base):
    """
    Manual override by an inspector for a compliance check.

    Never deletes the original automated result - stores the override separately.
    """

    __tablename__ = "compliance_overrides"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Original and new status
    original_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    check = relationship("ComplianceCheck", back_populates="overrides")
    inspector_user = relationship("User")

    def __repr__(self) -> str:
        return f"<ComplianceOverride(id={self.id}, check_id={self.check_id}, from={self.original_status}, to={self.new_status})>"
