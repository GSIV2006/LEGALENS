"""
Products Router

Endpoints:
- POST /products - Create product
- GET /products - List products
- GET /products/{id} - Get product by ID
- PUT /products/{id} - Update product
- DELETE /products/{id} - Delete product
- GET /products/search?q= - Search products
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.models.audit_log import AuditLog
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductSearchResult,
)
from app.dependencies.auth import get_current_user, admin_or_inspector
from app.models.user import User


router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: ProductCreate,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Create a new product.

    INSPECTOR or ADMIN can create products.
    """
    # Check barcode uniqueness if provided
    if product_data.barcode:
        existing = db.query(Product).filter(Product.barcode == product_data.barcode).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Barcode already exists",
            )

    # Create product
    product = Product(
        product_name=product_data.product_name,
        brand=product_data.brand,
        category=product_data.category,
        manufacturer=product_data.manufacturer,
        barcode=product_data.barcode,
        notes=product_data.notes,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    # Log creation
    audit_log = AuditLog(
        user_id=current_user.id,
        action="create_product",
        entity_type="Product",
        entity_id=product.id,
        details={"product_name": product.product_name},
    )
    db.add(audit_log)
    db.commit()

    return product


@router.get("/", response_model=ProductSearchResult)
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List products with optional filtering.

    All authenticated users can view products.
    """
    query = db.query(Product)

    # Filter by category
    if category:
        query = query.filter(Product.category == category)

    # Search in product name, brand, manufacturer
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            Product.product_name.ilike(search_term) |
            Product.brand.ilike(search_term) |
            Product.manufacturer.ilike(search_term)
        )

    # Order by creation date (newest first)
    query = query.order_by(Product.created_at.desc())

    # Get total count
    total = query.count()

    # Paginate
    products = query.offset(skip).limit(limit).all()

    return ProductSearchResult(
        products=products,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
    )


@router.get("/search", response_model=ProductSearchResult)
def search_products(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search products by name, brand, or manufacturer.

    All authenticated users can search products.
    """
    search_term = f"%{q}%"

    query = db.query(Product).filter(
        Product.product_name.ilike(search_term) |
        Product.brand.ilike(search_term) |
        Product.manufacturer.ilike(search_term)
    )

    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()

    return ProductSearchResult(
        products=products,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get product by ID.

    All authenticated users can view products.
    """
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Update a product.

    INSPECTOR or ADMIN can update products.
    """
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Update fields
    update_data = product_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            setattr(product, field, value)

    db.commit()
    db.refresh(product)

    # Log update
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_product",
        entity_type="Product",
        entity_id=product.id,
        details={"product_name": product.product_name},
    )
    db.add(audit_log)
    db.commit()

    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Delete a product (soft delete).

    INSPECTOR or ADMIN can delete products.
    """
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Check if product has associated inspections
    from app.models.inspection import Inspection
    inspection_count = db.query(Inspection).filter(
        Inspection.product_id == product_id
    ).count()

    if inspection_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete product with {inspection_count} associated inspection(s)",
        )

    # Log deletion
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete_product",
        entity_type="Product",
        entity_id=product.id,
        details={"product_name": product.product_name},
    )
    db.add(audit_log)
    db.commit()

    # Delete product
    db.delete(product)
    db.commit()

    return None
