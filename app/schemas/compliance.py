"""Compliance schemas."""
from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    """Compliance check statuses."""
    PASS = "PASS"
    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"


class OverallStatus(str, Enum):
    """Overall compliance status."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PROCESSING = "PROCESSING"


class ComplianceCheckResult(BaseModel):
    """Individual compliance check result."""
    rule_code: str
    rule_name: Optional[str] = None
    field: str
    status: CheckStatus
    message: Optional[str] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    details: Optional[dict] = None


class ComplianceAnalysis(BaseModel):
    """Complete compliance analysis result."""
    overall_status: OverallStatus
    checks: List[ComplianceCheckResult]
    total_checks: int
    passed_checks: int
    failed_checks: int
    manual_review_checks: int
    not_applicable_checks: int
    compliance_percentage: float
    ruleset_version: str
    notes: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceOverrideInput(BaseModel):
    """Input for manual override."""
    new_status: CheckStatus
    reason: str = Field(..., min_length=1)


class ComplianceOverrideResponse(BaseModel):
    """Response for override operation."""
    id: int
    check_id: int
    original_status: str
    new_status: str
    reason: str
    inspector_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Forward reference for ImageResponse
class ImageResponse(BaseModel):
    """Schema for image evidence response."""
    id: int
    inspection_id: Optional[int]
    view_type: str
    filename: str
    storage_path: Optional[str]
    storage_url: Optional[str]
    content_type: Optional[str]
    file_size: Optional[int]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ComplianceCheckResponse(BaseModel):
    """Schema for compliance check response."""
    id: int
    inspection_id: Optional[int]
    rule_id: Optional[int]
    rule_code: str
    field_name: str
    status: str
    message: Optional[str]
    confidence: Optional[float]
    evidence: Optional[str]
    check_details: Optional[dict]
    created_at: datetime
    updated_at: datetime
    overrides: List["ComplianceOverrideResponse"] = []

    class Config:
        from_attributes = True
