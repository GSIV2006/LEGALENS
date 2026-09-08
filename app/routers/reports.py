"""
Reports Router

Endpoints for generating PDF and DOCX compliance reports.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
import io

from app.database import get_db
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User
from app.models.ocr_data import OcrData
from app.schemas.inspection import InspectionResponse
from app.schemas.product import ProductResponse
from app.schemas.auth import UserResponse
from app.dependencies.auth import get_current_user
from app.services.report_generator import ReportGenerator
from app.models.audit_log import AuditLog


router = APIRouter(prefix="/reports", tags=["Reports"])

from app.models.inspection import Inspection
from app.schemas.inspection import InspectionResponse
from app.schemas.product import ProductResponse
from app.schemas.auth import UserResponse


def _get_inspection_data(
    inspection_id: int,
    db: Session,
) -> tuple:
    """Get inspection data for report generation."""
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Get product
    product = None
    if inspection.product_id:
        product = db.query(Product).filter(Product.id == inspection.product_id).first()

    # Get inspector
    inspector = None
    if inspection.inspector_id:
        inspector = db.query(User).filter(User.id == inspection.inspector_id).first()

    # Get OCR data
    ocr_data = db.query(OcrData).filter(OcrData.inspection_id == inspection_id).all()
    ocr_data_dicts = [item.to_dict() for item in ocr_data]

    # Get images
    images = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    image_list = []
    if images:
        from app.models.image import ImageEvidence
        images = db.query(ImageEvidence).filter(
            ImageEvidence.inspection_id == inspection_id
        ).all()
        image_list = [
            {
                "id": img.id,
                "view_type": img.view_type,
                "filename": img.filename,
                "storage_url": img.storage_url,
            }
            for img in images
        ]

    return inspection, product, inspector, ocr_data_dicts, image_list


@router.get("/{inspection_id}/pdf")
def generate_pdf_report(
    inspection_id: int,
    include_images: bool = Query(True),
    include_raw_ocr: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate PDF compliance report for an inspection.

    Returns a downloadable PDF file with:
    - Inspection details
    - Product information
    - Inspector info
    - Overall compliance status
    - All declaration checks (PASS/FAIL/MANUAL REVIEW)
    - Violation summary
    - Detected text/evidence with confidence
    - Legal rule references
    - Notes
    - Ruleset version
    - Image references where possible
    """
    # Get data
    inspection, product, inspector, ocr_data, images = _get_inspection_data(
        inspection_id, db
    )

    # Get compliance checks
    from app.models.compliance_check import ComplianceCheck
    checks = db.query(ComplianceCheck).filter(
        ComplianceCheck.inspection_id == inspection_id
    ).all()

    if not checks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No compliance analysis found. Run analysis first.",
        )

    # Build compliance analysis object
    from app.schemas.compliance import ComplianceAnalysis, CheckStatus
    checks_list = []
    for check in checks:
        checks_list.append(
            type(
                "Check",
                (),
                {
                    "rule_code": check.rule_code,
                    "rule_name": "",
                    "field": check.field_name,
                    "status": CheckStatus(check.status),
                    "message": check.message,
                    "confidence": check.confidence,
                    "evidence": check.evidence,
                    "details": check.check_details,
                },
            )()
        )

    passed = sum(1 for c in checks_list if c.status == CheckStatus.PASS)
    failed = sum(1 for c in checks_list if c.status == CheckStatus.FAIL)
    manual = sum(1 for c in checks_list if c.status == CheckStatus.MANUAL_REVIEW)
    na = sum(1 for c in checks_list if c.status == CheckStatus.NOT_APPLICABLE)

    compliance_analysis = ComplianceAnalysis(
        overall_status=CheckStatus(inspection.status),
        checks=checks_list,
        total_checks=len(checks_list),
        passed_checks=passed,
        failed_checks=failed,
        manual_review_checks=manual,
        not_applicable_checks=na,
        compliance_percentage=(passed / len(checks_list) * 100) if checks_list else 0,
        ruleset_version=inspection.ruleset_version,
        notes=inspection.notes,
        analyzed_at=inspection.updated_at,
    )

    # Convert to response schemas
    inspection_response = InspectionResponse.model_validate(inspection)
    product_response = ProductResponse.model_validate(product) if product else None
    inspector_response = UserResponse.model_validate(inspector) if inspector else None

    # Generate PDF
    generator = ReportGenerator()
    pdf_bytes = generator.generate_pdf(
        inspection=inspection_response,
        product=product_response,
        inspector=inspector_response,
        compliance_analysis=compliance_analysis,
        ocr_data=ocr_data if include_raw_ocr else [],
        images=images if include_images else [],
    )

    # Log report generation
    audit_log = AuditLog(
        user_id=current_user.id,
        action="generate_pdf_report",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={"inspection_id": inspection_id, "report_type": "pdf"},
    )
    db.add(audit_log)
    db.commit()

    # Return as download
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=compliance_report_{inspection_id}.pdf"
        },
    )


@router.get("/{inspection_id}/docx")
def generate_docx_report(
    inspection_id: int,
    include_images: bool = Query(True),
    include_raw_ocr: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate DOCX compliance report for an inspection.

    Returns a downloadable Word document with similar content to PDF.
    Editable format for further customization.
    """
    # Get data
    inspection, product, inspector, ocr_data, images = _get_inspection_data(
        inspection_id, db
    )

    # Get compliance checks
    from app.models.compliance_check import ComplianceCheck
    checks = db.query(ComplianceCheck).filter(
        ComplianceCheck.inspection_id == inspection_id
    ).all()

    if not checks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No compliance analysis found. Run analysis first.",
        )

    # Build compliance analysis object
    from app.schemas.compliance import ComplianceAnalysis, CheckStatus
    checks_list = []
    for check in checks:
        checks_list.append(
            type(
                "Check",
                (),
                {
                    "rule_code": check.rule_code,
                    "rule_name": "",
                    "field": check.field_name,
                    "status": CheckStatus(check.status),
                    "message": check.message,
                    "confidence": check.confidence,
                    "evidence": check.evidence,
                    "details": check.check_details,
                },
            )()
        )

    passed = sum(1 for c in checks_list if c.status == CheckStatus.PASS)
    failed = sum(1 for c in checks_list if c.status == CheckStatus.FAIL)
    manual = sum(1 for c in checks_list if c.status == CheckStatus.MANUAL_REVIEW)
    na = sum(1 for c in checks_list if c.status == CheckStatus.NOT_APPLICABLE)

    compliance_analysis = ComplianceAnalysis(
        overall_status=CheckStatus(inspection.status),
        checks=checks_list,
        total_checks=len(checks_list),
        passed_checks=passed,
        failed_checks=failed,
        manual_review_checks=manual,
        not_applicable_checks=na,
        compliance_percentage=(passed / len(checks_list) * 100) if checks_list else 0,
        ruleset_version=inspection.ruleset_version,
        notes=inspection.notes,
        analyzed_at=inspection.updated_at,
    )

    # Convert to response schemas
    inspection_response = InspectionResponse.model_validate(inspection)
    product_response = ProductResponse.model_validate(product) if product else None
    inspector_response = UserResponse.model_validate(inspector) if inspector else None

    # Generate DOCX
    generator = ReportGenerator()
    docx_bytes = generator.generate_docx(
        inspection=inspection_response,
        product=product_response,
        inspector=inspector_response,
        compliance_analysis=compliance_analysis,
        ocr_data=ocr_data if include_raw_ocr else [],
        images=images if include_images else [],
    )

    # Log report generation
    audit_log = AuditLog(
        user_id=current_user.id,
        action="generate_docx_report",
        entity_type="Inspection",
        entity_id=inspection_id,
        details={"inspection_id": inspection_id, "report_type": "docx"},
    )
    db.add(audit_log)
    db.commit()

    # Return as download
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=compliance_report_{inspection_id}.docx"
        },
    )
