"""Rule schemas."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    """Schema for rule creation."""
    rule_code: str = Field(..., min_length=1, max_length=50)
    rule_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    field_name: str = Field(..., min_length=1, max_length=255)
    required: bool = True
    validation_type: str = "required"
    severity: str = "MEDIUM"
    legal_reference: Optional[str] = None
    applicable_category: Optional[str] = None
    validation_config: Optional[str] = None  # JSON string
    active: bool = True
    ruleset_version: Optional[str] = "1.0.0"


class RuleUpdate(BaseModel):
    """Schema for rule update."""
    rule_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    field_name: Optional[str] = Field(None, min_length=1, max_length=255)
    required: Optional[bool] = None
    validation_type: Optional[str] = None
    severity: Optional[str] = None
    legal_reference: Optional[str] = None
    applicable_category: Optional[str] = None
    validation_config: Optional[str] = None
    active: Optional[bool] = None
    ruleset_version: Optional[str] = None


class RuleResponse(BaseModel):
    """Schema for rule response."""
    id: int
    rule_code: str
    rule_name: str
    description: Optional[str]
    field_name: str
    required: bool
    validation_type: str
    severity: str
    legal_reference: Optional[str]
    applicable_category: Optional[str]
    validation_config: Optional[str]
    active: bool
    ruleset_version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    """Schema for rule list response."""
    rules: List[RuleResponse]
    total: int
    active_count: int
    page: int
    page_size: int
