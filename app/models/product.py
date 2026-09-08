"""Product model for managing packaged commodities."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    """Product model representing a packaged commodity."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(500), nullable=False)
    brand = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    manufacturer = Column(String(500), nullable=True)
    barcode = Column(String(100), nullable=True, unique=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inspections = relationship("Inspection", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.product_name}, brand={self.brand})>"
