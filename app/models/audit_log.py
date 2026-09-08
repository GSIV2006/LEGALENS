"""Audit Log model for tracking system activities."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """
    Audit log entry for tracking user actions and system events.

    Used for:
    - Login events
    - Inspection creation/analysis
    - Manual overrides
    - Rule modifications
    - Report generation
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "login", "create_inspection", "override_check"
    entity_type = Column(String(100), nullable=True)  # e.g., "User", "Inspection", "Rule"
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Additional context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id})>"
