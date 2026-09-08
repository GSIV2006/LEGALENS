"""Inspection schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

# Import other schemas first for forward reference resolution
from app.schemas.product import ProductResponse
from app.schemas.auth import UserResponse
from app.schemas.ocr import OcrDataResponse
from app.schemas.compliance import ComplianceCheckResponse, ImageResponse


class InspectionCreate(BaseModel):
    """Schema for inspection creation."""
    product_id: Optional[int] = None
    inspector_id: Optional[int] = None
    status: str = "PROCESSING"
    notes: Optional[str] = None
    ruleset_version: Optional[str] = "1.0.0"


class InspectionUpdate(BaseModel):
    """Schema for inspection update."""
    status: Optional[str] = None
    overall_score: Optional[float] = None
    notes: Optional[str] = None
    ocr_status: Optional[str] = None
    extraction_status: Optional[str] = None
    compliance_status: Optional[str] = None
    ruleset_version: Optional[str] = None


class InspectionResponse(BaseModel):
    """Schema for inspection response."""
    id: int
    product_id: Optional[int]
    inspector_id: Optional[int]
    status: str
    overall_score: Optional[float]
    ruleset_version: str
    notes: Optional[str]
    ocr_status: Optional[str]
    extraction_status: Optional[str]
    compliance_status: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Nested relationships (optional, for detailed views)
    product: Optional[ProductResponse] = None
    inspector: Optional[UserResponse] = None
    images_count: Optional[int] = None
    ocr_data_count: Optional[int] = None
    checks_count: Optional[int] = None

    class Config:
        from_attributes = True


class InspectionListParams(BaseModel):
    """Query parameters for listing inspections."""
    status: Optional[str] = None
    product_id: Optional[int] = None
    inspector_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None  # Search in product name, brand, etc.
    page: int = 1
    page_size: int = 20


class InspectionWithDetailsResponse(BaseModel):
    """Detailed inspection response with all related data."""
    inspection: InspectionResponse
    product: Optional[ProductResponse] = None
    inspector: Optional[UserResponse] = None
    images: List[ImageResponse] = []
    ocr_data: List[OcrDataResponse] = []
    compliance_checks: List[ComplianceCheckResponse] = []

    class Config:
        from_attributes = True
