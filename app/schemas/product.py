"""Product schemas."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Schema for product creation."""
    product_name: str = Field(..., min_length=1, max_length=500)
    brand: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=255)
    manufacturer: Optional[str] = Field(None, max_length=500)
    barcode: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ProductUpdate(BaseModel):
    """Schema for product update."""
    product_name: Optional[str] = Field(None, min_length=1, max_length=500)
    brand: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=255)
    manufacturer: Optional[str] = Field(None, max_length=500)
    barcode: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ProductResponse(BaseModel):
    """Schema for product response."""
    id: int
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    manufacturer: Optional[str]
    barcode: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductSearchResult(BaseModel):
    """Schema for product search results."""
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int
