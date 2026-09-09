"""
Inspections Router

Main inspection endpoints including:
- Create inspection
- List inspections
- Get inspection details
- Upload images
- Submit OCR data
- Run OCR (mock)
- Extract fields
- Check compliance
- Full analysis pipeline
- Manual overrides

This is the CORE router for the SIH project.
"""
import os
import json
import shutil
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User
from app.models.ocr_data import OcrData
from app.models.image import ImageEvidence
from app.models.compliance_check import ComplianceCheck, ComplianceOverride
from app.models.audit_log import AuditLog
from app.schemas.inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionResponse,
    InspectionWithDetailsResponse,
)
from app.schemas.ocr import (
    OcrDataSubmit,
    OcrSubmitResponse,
    OcrJobResponse,
    OcrTextItem,
)
from app.schemas.compliance import (
    ComplianceAnalysis,
    ComplianceCheckResult,
    ComplianceOverrideInput,
    ComplianceOverrideResponse,
    CheckStatus,
)
from app.schemas.product import ProductResponse
from app.schemas.auth import UserResponse
from app.dependencies.auth import get_current_user, admin_or_inspector, inspector_or_viewer
from app.services.ocr_service import OcrService, ocr_service
from app.services.storage_service import StorageService, get_storage_service
from app.services.field_extractor import FieldExtractorService
from app.services.rule_engine import get_applicable_rules
from app.services.compliance_engine import ComplianceEngine
from app.services.visual_compliance_service import VisualComplianceService
from app.utils.helpers import calculate_compliance_percentage, paginate_query


router = APIRouter(prefix="/inspections", tags=["Inspections"])

# Model imports for forward references
from app.models.inspection import Inspection


def _convert_inspection_to_response(
    inspection: Inspection,
    include_details: bool = False,
    db: Session = None,
) -> InspectionResponse:
    """Convert Inspection model to response schema."""
    response = InspectionResponse(
        id=inspection.id,
        product_id=inspection.product_id,
        inspector_id=inspection.inspector_id,
        status=inspection.status,
        overall_score=inspection.overall_score,
        ruleset_version=inspection.ruleset_version,
        notes=inspection.notes,
        ocr_status=inspection.ocr_status,
        extraction_status=inspection.extraction_status,
        compliance_status=inspection.compliance_status,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
    )

    if include_details and db:
        # Add product info
        if inspection.product_id:
            product = db.query(Product).filter(Product.id == inspection.product_id).first()
            if product:
                response.product = ProductResponse.model_validate(product)

        # Add inspector info
        if inspection.inspector_id:
            inspector = db.query(User).filter(User.id == inspection.inspector_id).first()
            if inspector:
                response.inspector = UserResponse.model_validate(inspector)

        # Add counts
        response.images_count = db.query(ImageEvidence).filter(
            ImageEvidence.inspection_id == inspection.id
        ).count()
        response.ocr_data_count = db.query(OcrData).filter(
            OcrData.inspection_id == inspection.id
        ).count()
        response.checks_count = db.query(ComplianceCheck).filter(
            ComplianceCheck.inspection_id == inspection.id
        ).count()

    return response


@router.post("/", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
def create_inspection(
    inspection_data: InspectionCreate,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Create a new inspection.

    INSPECTOR or ADMIN can create inspections.
    """
    # Validate product if provided
    product = None
    if inspection_data.product_id:
        product = db.query(Product).filter(Product.id == inspection_data.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

    # Validate inspector if provided
    if inspection_data.inspector_id:
        inspector = db.query(User).filter(User.id == inspection_data.inspector_id).first()
        if not inspector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inspector user not found",
            )

    # Create inspection
    inspection = Inspection(
        product_id=inspection_data.product_id,
        inspector_id=inspection_data.inspector_id or current_user.id,
        status=inspection_data.status,
        notes=inspection_data.notes,
        ruleset_version=inspection_data.ruleset_version,
    )

    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    # Log creation
    audit_log = AuditLog(
        user_id=current_user.id,
        action="create_inspection",
        entity_type="Inspection",
        entity_id=inspection.id,
        details={
            "product_id": inspection.product_id,
            "inspector_id": inspection.inspector_id,
            "status": inspection.status,
        },
    )
    db.add(audit_log)
    db.commit()

    return _convert_inspection_to_response(inspection, db=db)


@router.get("/", response_model=List[InspectionResponse])
def list_inspections(
    status: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    inspector_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List inspections with filtering and pagination.

    Filter by:
    - status (COMPLIANT, NON_COMPLIANT, MANUAL_REVIEW, PROCESSING)
    - product_id
    - inspector_id
    - date range
    - search term (searches product name)
    """
    query = db.query(Inspection)

    # Apply filters
    if status:
        query = query.filter(Inspection.status == status)

    if product_id:
        query = query.filter(Inspection.product_id == product_id)

    if inspector_id:
        query = query.filter(Inspection.inspector_id == inspector_id)

    if date_from:
        query = query.filter(Inspection.created_at >= date_from)

    if date_to:
        query = query.filter(Inspection.created_at <= date_to)

    if search:
        # Join with product to search by name
        query = query.join(Product, Inspection.product_id == Product.id, isouter=True)
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.product_name.ilike(search_term),
                Product.brand.ilike(search_term),
                Inspection.notes.ilike(search_term),
            )
        )

    # Order by creation date (newest first)
    query = query.order_by(Inspection.created_at.desc())

    # Paginate
    items, total, total_pages = paginate_query(query, page, page_size)
    inspections = items

    # Convert to responses
    results = []
    for inspection in inspections:
        results.append(_convert_inspection_to_response(inspection, include_details=True, db=db))

    return results


@router.get("/{inspection_id}", response_model=InspectionWithDetailsResponse)
def get_inspection(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get inspection with full details.

    Includes product, images, OCR data, and compliance checks.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Convert to response with details
    inspection_response = _convert_inspection_to_response(inspection, include_details=True, db=db)

    # Get images
    images = db.query(ImageEvidence).filter(
        ImageEvidence.inspection_id == inspection_id
    ).order_by(ImageEvidence.created_at).all()

    # Get OCR data
    ocr_data = db.query(OcrData).filter(
        OcrData.inspection_id == inspection_id
    ).order_by(OcrData.created_at).all()

    # Get compliance checks with overrides
    checks = db.query(ComplianceCheck).filter(
        ComplianceCheck.inspection_id == inspection_id
    ).order_by(ComplianceCheck.created_at).all()

    # Convert to detailed response
    return InspectionWithDetailsResponse(
        inspection=inspection_response,
        product=inspection_response.product,
        inspector=inspection_response.inspector,
        images=[
            {
                "id": img.id,
                "inspection_id": img.inspection_id,
                "view_type": img.view_type,
                "filename": img.filename,
                "storage_path": img.storage_path,
                "storage_url": img.storage_url,
                "content_type": img.content_type,
                "file_size": img.file_size,
                "notes": img.notes,
                "created_at": img.created_at,
            }
            for img in images
        ],
        ocr_data=[item.to_dict() for item in ocr_data],
        compliance_checks=[
            {
                "id": check.id,
                "inspection_id": check.inspection_id,
                "rule_id": check.rule_id,
                "rule_code": check.rule_code,
                "field_name": check.field_name,
                "status": check.status,
                "message": check.message,
                "confidence": check.confidence,
                "evidence": check.evidence,
                "check_details": check.check_details,
                "created_at": check.created_at,
                "updated_at": check.updated_at,
                "overrides": [
                    {
                        "id": override.id,
                        "check_id": override.check_id,
                        "original_status": override.original_status,
                        "new_status": override.new_status,
                        "reason": override.reason,
                        "inspector_id": override.inspector_id,
                        "created_at": override.created_at,
                    }
                    for override in check.overrides
                ],
            }
            for check in checks
        ],
    )


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection(
    inspection_id: int,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Delete an inspection (soft delete).

    INSPECTOR or ADMIN can delete inspections.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Log deletion
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete_inspection",
        entity_type="Inspection",
        entity_id=inspection.id,
    )
    db.add(audit_log)

    # Delete related records
    db.query(ComplianceOverride).filter(
        ComplianceOverride.check_id.in_(
            db.query(ComplianceCheck.id).filter(ComplianceCheck.inspection_id == inspection_id)
        )
    ).delete(synchronize_session=False)

    db.query(ComplianceCheck).filter(ComplianceCheck.inspection_id == inspection_id).delete()
    db.query(OcrData).filter(OcrData.inspection_id == inspection_id).delete()
    db.query(ImageEvidence).filter(ImageEvidence.inspection_id == inspection_id).delete()

    db.delete(inspection)
    db.commit()

    return None


# ================ IMAGE UPLOAD ENDPOINTS ================

@router.post("/{inspection_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_inspection_images(
    inspection_id: int,
    images: List[UploadFile] = File(...),
    view_type: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Upload images for an inspection.

    Supported views: front, back, left, right, top, bottom, other
    Allowed formats: jpg, jpeg, png, webp
    Max size: 10MB per image
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Validate view type
    valid_view_types = ["front", "back", "left", "right", "top", "bottom", "other"]
    if view_type not in valid_view_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid view type. Valid: {', '.join(valid_view_types)}",
        )

    storage_service = get_storage_service()
    uploaded_images = []

    for image_file in images:
        # Validate file
        is_valid, error_msg = storage_service.validate_file_type(image_file.content_type)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        # Read file content
        content = await image_file.read()
        file_size = len(content)

        # Check size
        if not storage_service.validate_file_size(file_size):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max: 10MB",
            )

        # Save file
        storage_info = await storage_service.save_image(
            file_data=content,
            filename=image_file.filename,
            view_type=view_type,
            inspection_id=inspection_id,
            content_type=image_file.content_type,
            file_size=file_size,
        )

        # Create database record
        image_evidence = ImageEvidence(
            inspection_id=inspection_id,
            view_type=view_type,
            filename=image_file.filename,
            storage_path=storage_info["storage_path"],
            storage_url=storage_info["storage_url"],
            content_type=image_file.content_type,
            file_size=file_size,
            notes=notes,
        )

        db.add(image_evidence)
        uploaded_images.append(image_evidence)

    db.commit()

    # Log upload
    audit_log = AuditLog(
        user_id=current_user.id,
        action="upload_images",
        entity_type="ImageEvidence",
        entity_id=inspection_id,
        details={"inspection_id": inspection_id, "view_type": view_type, "count": len(images)},
    )
    db.add(audit_log)
    db.commit()

    return {
        "message": f"Successfully uploaded {len(images)} image(s)",
        "inspection_id": inspection_id,
        "view_type": view_type,
        "images": [
            {
                "id": img.id,
                "filename": img.filename,
                "view_type": img.view_type,
                "storage_url": img.storage_url,
            }
            for img in uploaded_images
        ],
    }


# ================ OCR DATA ENDPOINTS ================

@router.post("/{inspection_id}/ocr-data", response_model=OcrSubmitResponse)
async def submit_ocr_data(
    inspection_id: int,
    ocr_data: OcrDataSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit OCR data (JSON) for an inspection.

    This endpoint accepts OCR output from the OCR team.
    Expects format:
    {
        "texts": [
            {
                "text": "MRP ₹120 incl. of all taxes",
                "confidence": 0.97,
                "bbox": [[10,20],[300,20],[300,50],[10,50]],
                "image_name": "back.jpg"
            }
        ]
    }
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Import here to avoid circular imports
    from app.services.ocr_service import submit_ocr_data as save_ocr

    count = save_ocr(inspection_id, ocr_data, db)

    # Update inspection status
    inspection.ocr_status = "completed"
    db.commit()

    # Log submission
    audit_log = AuditLog(
        user_id=current_user.id,
        action="submit_ocr_data",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={"inspection_id": inspection_id, "text_count": count},
    )
    db.add(audit_log)
    db.commit()

    return OcrSubmitResponse(
        message=f"Successfully saved {count} OCR text items",
        count=count,
        inspection_id=inspection_id,
    )


@router.post("/{inspection_id}/run-ocr", response_model=OcrJobResponse)
async def run_ocr(
    inspection_id: int,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Run OCR on uploaded images for an inspection.

    Currently uses MOCK OCR implementation.
    OCR teammates will replace this with real PaddleOCR/OpenCV.
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Check if there are images to process
    images = db.query(ImageEvidence).filter(
        ImageEvidence.inspection_id == inspection_id
    ).all()

    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No images uploaded for this inspection. Upload images first.",
        )

    # Get storage service
    storage_service = get_storage_service()

    # Process each image
    all_texts = []
    image_names = []

    for image in images:
        if image.storage_path and os.path.exists(image.storage_path):
            # Run OCR on image
            texts = await ocr_service.run_ocr(image.storage_path, image.filename)
            all_texts.extend(texts)
            image_names.append(image.filename)

            # Save OCR data
            for text_item in texts:
                ocr_data = OcrData(
                    inspection_id=inspection_id,
                    text=text_item["text"],
                    confidence=text_item.get("confidence"),
                    bounding_box=text_item.get("bbox"),
                    source_image=text_item.get("image_name", image.filename),
                )
                db.add(ocr_data)

    db.commit()

    # Update inspection status
    inspection.ocr_status = "completed"
    db.commit()

    # Log OCR run
    audit_log = AuditLog(
        user_id=current_user.id,
        action="run_ocr",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={
            "inspection_id": inspection_id,
            "image_count": len(images),
            "text_count": len(all_texts),
            "ocr_engine": "mock",
        },
    )
    db.add(audit_log)
    db.commit()

    return OcrJobResponse(
        inspection_id=inspection_id,
        ocr_status=inspection.ocr_status,
        message=f"OCR completed on {len(images)} image(s), found {len(all_texts)} text items",
        text_count=len(all_texts),
    )


# ================ FIELD EXTRACTION ENDPOINT ================

@router.post("/{inspection_id}/extract-fields")
async def extract_fields(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Extract structured fields from OCR data.

    Uses regex and string processing to identify:
    - MRP
    - Net quantity
    - Manufacturer info
    - Dates
    - Consumer care
    - Country of origin
    - And more...
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Get OCR data
    ocr_items = db.query(OcrData).filter(OcrData.inspection_id == inspection_id).all()

    if not ocr_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OCR data found. Submit OCR data or run OCR first.",
        )

    # Convert to OcrTextItem format
    ocr_texts = []
    for item in ocr_items:
        ocr_texts.append(
            OcrTextItem(
                text=item.text,
                confidence=item.confidence,
                bbox=item.bbox,
                image_name=item.source_image,
                page_number=item.page_number,
            )
        )

    # Extract fields
    field_extractor = FieldExtractorService()
    extracted_fields = await field_extractor.extract_fields(ocr_texts)

    # Update inspection status
    inspection.extraction_status = "completed"
    db.commit()

    # Log extraction
    audit_log = AuditLog(
        user_id=current_user.id,
        action="extract_fields",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={
            "inspection_id": inspection_id,
            "fields_found": len([k for k, v in extracted_fields.items() if v is not None]),
        },
    )
    db.add(audit_log)
    db.commit()

    return {
        "inspection_id": inspection_id,
        "extraction_status": inspection.extraction_status,
        "fields": extracted_fields,
        "message": "Field extraction completed successfully",
    }


# ================ COMPLIANCE CHECK ENDPOINT ================

@router.post("/{inspection_id}/check-compliance", response_model=ComplianceAnalysis)
async def check_compliance(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check compliance of an inspection against legal rules.

    Runs compliance engine against extracted fields and applicable rules.
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Get OCR data
    ocr_items = db.query(OcrData).filter(OcrData.inspection_id == inspection_id).all()

    if not ocr_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OCR data found. Submit OCR data or run OCR first.",
        )

    # Convert to OcrTextItem format
    ocr_texts = [
        OcrTextItem(
            text=item.text,
            confidence=item.confidence,
            bbox=item.bbox,
            image_name=item.source_image,
            page_number=item.page_number,
        )
        for item in ocr_items
    ]

    # Get product category for rule filtering
    product_category = None
    if inspection.product_id:
        product = db.query(Product).filter(Product.id == inspection.product_id).first()
        if product:
            product_category = product.category

    # Extract fields
    field_extractor = FieldExtractorService()
    extracted_fields = await field_extractor.extract_fields(ocr_texts)

    # Run compliance engine
    compliance_engine = ComplianceEngine()
    analysis = await compliance_engine.analyze_compliance(
        inspection_id=inspection_id,
        extracted_fields=extracted_fields,
        ocr_texts=ocr_texts,
        product_category=product_category,
        ruleset_version=inspection.ruleset_version,
        db=db,
    )

    # Save compliance checks to database
    for check in analysis.checks:
        compliance_check = ComplianceCheck(
            inspection_id=inspection_id,
            rule_id=None,  # Would need to lookup rule ID
            rule_code=check.rule_code,
            field_name=check.field,
            status=check.status.value,
            message=check.message,
            confidence=check.confidence,
            evidence=check.evidence,
            check_details=check.details,
        )
        db.add(compliance_check)

    # Update inspection
    inspection.status = analysis.overall_status.value
    inspection.overall_score = analysis.compliance_percentage / 100
    inspection.compliance_status = "completed"
    inspection.notes = analysis.notes

    db.commit()

    # Log compliance check
    audit_log = AuditLog(
        user_id=current_user.id,
        action="check_compliance",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={
            "inspection_id": inspection_id,
            "overall_status": analysis.overall_status.value,
            "compliance_percentage": analysis.compliance_percentage,
            "passed": analysis.passed_checks,
            "failed": analysis.failed_checks,
        },
    )
    db.add(audit_log)
    db.commit()

    return analysis


# ================ FULL ANALYSIS PIPELINE ================

@router.post("/{inspection_id}/analyze")
async def analyze_inspection(
    inspection_id: int,
    run_visual_check: bool = False,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Complete analysis pipeline for an inspection.

    Performs:
    1. OCR on uploaded images (if images exist and OCR not done)
    2. Field extraction from OCR data
    3. Applicable rule selection
    4. Compliance checking
    5. Save all results
    6. Return complete analysis JSON

    If run_visual_check is True, also runs visual compliance analysis.
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Step 1: Check/Run OCR
    if inspection.ocr_status != "completed":
        images = db.query(ImageEvidence).filter(
            ImageEvidence.inspection_id == inspection_id
        ).all()

        if images:
            # Run OCR
            for image in images:
                if image.storage_path and os.path.exists(image.storage_path):
                    texts = await ocr_service.run_ocr(image.storage_path, image.filename)
                    for text_item in texts:
                        ocr_data = OcrData(
                            inspection_id=inspection_id,
                            text=text_item["text"],
                            confidence=text_item.get("confidence"),
                            bounding_box=text_item.get("bbox"),
                            source_image=text_item.get("image_name", image.filename),
                        )
                        db.add(ocr_data)

            inspection.ocr_status = "completed"
            db.commit()

    # Get OCR data
    ocr_items = db.query(OcrData).filter(OcrData.inspection_id == inspection_id).all()

    if not ocr_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OCR data available. Upload images and run OCR first.",
        )

    # Convert to OcrTextItem format
    ocr_texts = [
        OcrTextItem(
            text=item.text,
            confidence=item.confidence,
            bbox=item.bbox,
            image_name=item.source_image,
            page_number=item.page_number,
        )
        for item in ocr_items
    ]

    # Step 2: Extract fields
    field_extractor = FieldExtractorService()
    extracted_fields = await field_extractor.extract_fields(ocr_texts)
    inspection.extraction_status = "completed"
    db.commit()

    # Step 3: Get applicable rules
    product_category = None
    if inspection.product_id:
        product = db.query(Product).filter(Product.id == inspection.product_id).first()
        if product:
            product_category = product.category

    applicable_rules = get_applicable_rules(db=db, category=product_category)

    # Step 4: Run compliance engine
    compliance_engine = ComplianceEngine()
    analysis = await compliance_engine.analyze_compliance(
        inspection_id=inspection_id,
        extracted_fields=extracted_fields,
        ocr_texts=ocr_texts,
        product_category=product_category,
        ruleset_version=inspection.ruleset_version,
        db=db,
    )

    # Save compliance checks
    for check in analysis.checks:
        compliance_check = ComplianceCheck(
            inspection_id=inspection_id,
            rule_id=None,
            rule_code=check.rule_code,
            field_name=check.field,
            status=check.status.value,
            message=check.message,
            confidence=check.confidence,
            evidence=check.evidence,
            check_details=check.details,
        )
        db.add(compliance_check)

    # Update inspection
    inspection.status = analysis.overall_status.value
    inspection.overall_score = analysis.compliance_percentage / 100
    inspection.compliance_status = "completed"
    inspection.notes = analysis.notes
    db.commit()

    # Step 5: Visual compliance (optional)
    visual_results = None
    if run_visual_check:
        visual_service = VisualComplianceService()
        image_paths = {}
        images = db.query(ImageEvidence).filter(
            ImageEvidence.inspection_id == inspection_id
        ).all()
        for img in images:
            if img.storage_path:
                image_paths[img.view_type] = img.storage_path

        visual_results = await visual_service.analyze_visual_compliance(
            inspection_id=inspection_id,
            image_paths=image_paths if image_paths else None,
            ocr_texts=ocr_texts,
        )

    # Log analysis
    audit_log = AuditLog(
        user_id=current_user.id,
        action="analyze_inspection",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={
            "inspection_id": inspection_id,
            "overall_status": analysis.overall_status.value,
            "compliance_percentage": analysis.compliance_percentage,
            "visual_check": run_visual_check,
        },
    )
    db.add(audit_log)
    db.commit()

    # Build complete response
    response = {
        "inspection_id": inspection_id,
        "status": analysis.overall_status.value,
        "compliance_percentage": analysis.compliance_percentage,
        "ruleset_version": analysis.ruleset_version,
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "extracted_fields": extracted_fields,
        "compliance_checks": [
            {
                "rule_code": check.rule_code,
                "rule_name": check.rule_name,
                "field": check.field,
                "status": check.status.value,
                "message": check.message,
                "confidence": check.confidence,
                "evidence": check.evidence,
                "details": check.details,
            }
            for check in analysis.checks
        ],
        "summary": {
            "total_checks": analysis.total_checks,
            "passed": analysis.passed_checks,
            "failed": analysis.failed_checks,
            "manual_review": analysis.manual_review_checks,
            "not_applicable": analysis.not_applicable_checks,
        },
        "notes": analysis.notes,
    }

    if visual_results:
        response["visual_compliance"] = visual_results

    return response


@router.post("/{inspection_id}/analyze-from-ocr")
async def analyze_from_ocr(
    inspection_id: int,
    ocr_json: OcrDataSubmit,
    run_visual_check: bool = False,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Analyze inspection from provided OCR JSON.

    Accepts OCR data from teammates and runs full analysis pipeline.
    Useful when OCR is done externally and results are submitted here.

    This is a KEY endpoint for the SIH hackathon.
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Save OCR data
    from app.services.ocr_service import submit_ocr_data as save_ocr
    count = save_ocr(inspection_id, ocr_json, db)
    inspection.ocr_status = "completed"
    db.commit()

    # Get OCR data (including newly saved)
    ocr_items = db.query(OcrData).filter(OcrData.inspection_id == inspection_id).all()

    # Convert to OcrTextItem format
    ocr_texts = [
        OcrTextItem(
            text=item.text,
            confidence=item.confidence,
            bbox=item.bbox,
            image_name=item.source_image,
            page_number=item.page_number,
        )
        for item in ocr_items
    ]

    # Extract fields
    field_extractor = FieldExtractorService()
    extracted_fields = await field_extractor.extract_fields(ocr_texts)
    inspection.extraction_status = "completed"
    db.commit()

    # Get applicable rules
    product_category = None
    if inspection.product_id:
        product = db.query(Product).filter(Product.id == inspection.product_id).first()
        if product:
            product_category = product.category

    # Run compliance engine
    compliance_engine = ComplianceEngine()
    analysis = await compliance_engine.analyze_compliance(
        inspection_id=inspection_id,
        extracted_fields=extracted_fields,
        ocr_texts=ocr_texts,
        product_category=product_category,
        ruleset_version=inspection.ruleset_version,
        db=db,
    )

    # Save compliance checks
    for check in analysis.checks:
        compliance_check = ComplianceCheck(
            inspection_id=inspection_id,
            rule_id=None,
            rule_code=check.rule_code,
            field_name=check.field,
            status=check.status.value,
            message=check.message,
            confidence=check.confidence,
            evidence=check.evidence,
            check_details=check.details,
        )
        db.add(compliance_check)

    # Update inspection
    inspection.status = analysis.overall_status.value
    inspection.overall_score = analysis.compliance_percentage / 100
    inspection.compliance_status = "completed"
    inspection.notes = analysis.notes
    db.commit()

    # Visual compliance (optional)
    visual_results = None
    if run_visual_check:
        visual_service = VisualComplianceService()
        visual_results = await visual_service.analyze_visual_compliance(inspection_id)

    # Log analysis
    audit_log = AuditLog(
        user_id=current_user.id,
        action="analyze_from_ocr",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={
            "inspection_id": inspection_id,
            "ocr_text_count": count,
            "overall_status": analysis.overall_status.value,
        },
    )
    db.add(audit_log)
    db.commit()

    # Build response
    response = {
        "inspection_id": inspection_id,
        "status": analysis.overall_status.value,
        "compliance_percentage": analysis.compliance_percentage,
        "ruleset_version": analysis.ruleset_version,
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "extracted_fields": extracted_fields,
        "compliance_checks": [
            {
                "rule_code": check.rule_code,
                "rule_name": check.rule_name,
                "field": check.field,
                "status": check.status.value,
                "message": check.message,
                "confidence": check.confidence,
                "evidence": check.evidence,
                "details": check.details,
            }
            for check in analysis.checks
        ],
        "summary": {
            "total_checks": analysis.total_checks,
            "passed": analysis.passed_checks,
            "failed": analysis.failed_checks,
            "manual_review": analysis.manual_review_checks,
            "not_applicable": analysis.not_applicable_checks,
        },
        "notes": analysis.notes,
    }

    if visual_results:
        response["visual_compliance"] = visual_results

    return response


# ================ MANUAL OVERRIDE ENDPOINT ================

@router.post("/{inspection_id}/checks/{check_id}/override", response_model=ComplianceOverrideResponse)
def override_check(
    inspection_id: int,
    check_id: int,
    override_data: ComplianceOverrideInput,
    current_user: User = Depends(admin_or_inspector),
    db: Session = Depends(get_db),
):
    """
    Manually override a compliance check result.

    INSPECTOR or ADMIN can override checks.
    Original result is preserved; override is stored separately.
    """
    # Verify inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Get the check
    check = db.query(ComplianceCheck).filter(
        ComplianceCheck.id == check_id,
        ComplianceCheck.inspection_id == inspection_id,
    ).first()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compliance check not found",
        )

    # Create override record
    override = ComplianceOverride(
        check_id=check_id,
        inspector_id=current_user.id,
        original_status=check.status,
        new_status=override_data.new_status.value,
        reason=override_data.reason,
    )

    db.add(override)

    # Update the check status
    check.status = override_data.new_status.value
    check.message = f"[OVERRIDDEN] {check.message}" if check.message else "[OVERRIDDEN] Manual override by inspector"

    db.commit()
    db.refresh(override)

    # Log override
    audit_log = AuditLog(
        user_id=current_user.id,
        action="override_check",
        entity_type="ComplianceCheck",
        entity_id=check_id,
        details={
            "inspection_id": inspection_id,
            "check_id": check_id,
            "rule_code": check.rule_code,
            "original_status": check.status,
            "new_status": override_data.new_status.value,
            "reason": override_data.reason,
        },
    )
    db.add(audit_log)
    db.commit()

    return {
        "id": override.id,
        "check_id": override.check_id,
        "original_status": override.original_status,
        "new_status": override.new_status,
        "reason": override.reason,
        "inspector_id": override.inspector_id,
        "created_at": override.created_at,
    }
