"""
History Router

Compliance History / Repository endpoints.

Search and filter previous inspections with pagination.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.dashboard import (
    InspectionSummary,
    HistoryFilter,
)
from app.schemas.inspection import InspectionResponse
from app.dependencies.auth import get_current_user


router = APIRouter(prefix="/history", tags=["History"])


@router.get("/", response_model=List[InspectionSummary])
def get_history(
    product_name: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    inspector_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search and filter compliance history.

    Returns paginated list of past inspections with:
    - Product name
    - Brand
    - Manufacturer
    - Status
    - Date
    - Inspector name

    Filter by:
    - product_name
    - brand
    - manufacturer
    - status
    - date range
    - inspector name
    """
    from datetime import datetime

    # Base query with joins
    query = db.query(Inspection).join(
        Product, Inspection.product_id == Product.id, isouter=True
    ).join(
        User, Inspection.inspector_id == User.id, isouter=True
    )

    # Apply filters
    if product_name:
        query = query.filter(
            or_(
                Product.product_name.ilike(f"%{product_name}%"),
                Inspection.notes.ilike(f"%{product_name}%"),
            )
        )

    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))

    if manufacturer:
        query = query.filter(Product.manufacturer.ilike(f"%{manufacturer}%"))

    if status:
        query = query.filter(Inspection.status == status)

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(Inspection.created_at >= date_from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(Inspection.created_at <= date_to_dt)
        except ValueError:
            pass

    if inspector_name:
        query = query.filter(
            or_(
                User.full_name.ilike(f"%{inspector_name}%"),
                User.username.ilike(f"%{inspector_name}%"),
            )
        )

    # Order by date (newest first)
    query = query.order_by(Inspection.created_at.desc())

    # Paginate
    total = query.count()
    offset = (page - 1) * page_size
    inspections = query.offset(offset).limit(page_size).all()

    # Build response
    results = []
    for insp in inspections:
        summary = InspectionSummary(
            id=insp.id,
            status=insp.status,
            product_name=(Product.product_name if Product else None),
            inspector_name=None,
            created_at=insp.created_at,
        )

        # Get product name
        if insp.product:
            summary.product_name = insp.product.product_name

        # Get inspector name
        if insp.inspector_user:
            summary.inspector_name = (
                insp.inspector_user.full_name
                or insp.inspector_user.username
                or "Unknown"
            )

        results.append(summary)

    return results


@router.get("/{inspection_id}/full", response_model=InspectionResponse)
def get_inspection_history(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full inspection details from history.

    Includes all related data for a specific inspection.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Inspection not found",
        )

    # Convert to response with full details
    from app.routers.inspections import _convert_inspection_to_response
    return _convert_inspection_to_response(inspection, include_details=True, db=db)


@router.get("/export")
def export_history(
    format: str = Query("json", regex="^(json|jsonl|csv)$"),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export compliance history.

    Formats: json, jsonl, csv

    Useful for data analysis and reporting.
    """
    from datetime import datetime
    import json
    import csv
    import io

    # Base query
    query = db.query(Inspection).join(
        Product, Inspection.product_id == Product.id, isouter=True
    ).join(
        User, Inspection.inspector_id == User.id, isouter=True
    )

    # Apply filters
    if status:
        query = query.filter(Inspection.status == status)

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(Inspection.created_at >= date_from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(Inspection.created_at <= date_to_dt)
        except ValueError:
            pass

    inspections = query.order_by(Inspection.created_at.desc()).all()

    if format == "json":
        data = []
        for insp in inspections:
            item = {
                "id": insp.id,
                "status": insp.status,
                "overall_score": insp.overall_score,
                "ruleset_version": insp.ruleset_version,
                "notes": insp.notes,
                "created_at": insp.created_at.isoformat() if insp.created_at else None,
                "updated_at": insp.updated_at.isoformat() if insp.updated_at else None,
                "product": {
                    "id": insp.product.id if insp.product else None,
                    "product_name": insp.product.product_name if insp.product else None,
                    "brand": insp.product.brand if insp.product else None,
                    "category": insp.product.category if insp.product else None,
                    "manufacturer": insp.product.manufacturer if insp.product else None,
                } if insp.product else None,
                "inspector": {
                    "id": insp.inspector_user.id if insp.inspector_user else None,
                    "username": insp.inspector_user.username if insp.inspector_user else None,
                    "full_name": insp.inspector_user.full_name if insp.inspector_user else None,
                    "email": insp.inspector_user.email if insp.inspector_user else None,
                } if insp.inspector_user else None,
            }
            data.append(item)

        return {"data": data, "total": len(data), "format": "json"}

    elif format == "jsonl":
        lines = []
        for insp in inspections:
            item = {
                "id": insp.id,
                "status": insp.status,
                "overall_score": insp.overall_score,
                "ruleset_version": insp.ruleset_version,
                "created_at": insp.created_at.isoformat() if insp.created_at else None,
                "product_name": insp.product.product_name if insp.product else None,
                "inspector_name": (
                    insp.inspector_user.full_name
                    or insp.inspector_user.username
                    or "Unknown"
                ) if insp.inspector_user else None,
            }
            lines.append(json.dumps(item))
        return {"lines": lines, "total": len(lines), "format": "jsonl"}

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "ID", "Status", "Overall Score", "Ruleset Version",
            "Product Name", "Brand", "Category", "Manufacturer",
            "Inspector Name", "Inspector Email", "Created At", "Updated At"
        ])

        # Data rows
        for insp in inspections:
            writer.writerow([
                insp.id,
                insp.status,
                insp.overall_score,
                insp.ruleset_version,
                insp.product.product_name if insp.product else "",
                insp.product.brand if insp.product else "",
                insp.product.category if insp.product else "",
                insp.product.manufacturer if insp.product else "",
                (
                    insp.inspector_user.full_name
                    or insp.inspector_user.username
                    or ""
                ) if insp.inspector_user else "",
                insp.inspector_user.email if insp.inspector_user else "",
                insp.created_at.isoformat() if insp.created_at else "",
                insp.updated_at.isoformat() if insp.updated_at else "",
            ])

        csv_content = output.getvalue()
        output.close()

        return {
            "content": csv_content,
            "total": len(inspections),
            "format": "csv",
            "filename": "compliance_history.csv",
        }
