"""Report schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Request for report generation."""
    include_images: bool = True
    include_raw_ocr: bool = True
    include_all_checks: bool = True
    notes: Optional[str] = None


class ReportMetadata(BaseModel):
    """Report metadata."""
    inspection_id: int
    report_type: str  # "pdf" or "docx"
    generated_at: datetime
    ruleset_version: str
    overall_status: str
