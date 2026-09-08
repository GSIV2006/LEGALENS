"""Legal Rule model for configurable compliance rules."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Rule(Base):
    """
    Configurable legal compliance rule.

    Rules are maintained as a versioned Legal Metrology compliance ruleset
    based on the official Department of Consumer Affairs reference material.
    """

    __tablename__ = "rules"

    class Severity:
        """Severity levels."""
        LOW = "LOW"
        MEDIUM = "MEDIUM"
        HIGH = "HIGH"
        CRITICAL = "CRITICAL"

    class ValidationType:
        """Validation types."""
        REQUIRED = "required"
        FORMAT = "format"
        RANGE = "range"
        PATTERN = "pattern"
        CUSTOM = "custom"
        EXISTS = "exists"

    id = Column(Integer, primary_key=True, index=True)
    rule_code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "LM-MRP-001"
    rule_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    field_name = Column(String(255), nullable=False)  # Field this rule checks
    required = Column(Boolean, default=True)
    validation_type = Column(String(50), default=ValidationType.REQUIRED)
    severity = Column(String(50), default=Severity.MEDIUM)
    legal_reference = Column(String(500), nullable=True)  # Legal provision reference
    applicable_category = Column(String(255), nullable=True)  # Product categories this applies to
    validation_config = Column(Text, nullable=True)  # JSON config for validation
    active = Column(Boolean, default=True)
    ruleset_version = Column(String(100), default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    compliance_checks = relationship("ComplianceCheck", back_populates="rule")

    def __repr__(self) -> str:
        return f"<Rule(id={self.id}, code={self.rule_code}, name={self.rule_name}, severity={self.severity})>"
