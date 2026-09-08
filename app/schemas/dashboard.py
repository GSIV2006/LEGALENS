"""Dashboard schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class ViolationStats(BaseModel):
    """Violation statistics grouped by rule."""
    rule_code: str
    rule_name: str
    violation_count: int
    severity: str
    percentage: float


class ViolationType(BaseModel):
    """Single violation type entry."""
    rule_code: str
    rule_name: str
    count: int
    severity: str


class InspectionSummary(BaseModel):
    """Brief inspection summary for dashboard."""
    id: int
    status: str
    product_name: Optional[str] = None
    inspector_name: Optional[str] = None
    created_at: datetime


class DashboardSummary(BaseModel):
    """Dashboard summary statistics."""
    total_inspections: int
    compliant: int
    non_compliant: int
    manual_review: int
    processing: int
    total_violations: int
    compliance_percentage: float
    recent_inspections: List[InspectionSummary] = []
    top_violation_types: List[ViolationType] = []


class HistoryFilter(BaseModel):
    """Filter parameters for history endpoint."""
    product_name: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    inspector_name: Optional[str] = None
    page: int = 1
    page_size: int = 20
