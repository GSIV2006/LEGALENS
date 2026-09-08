"""
Dashboard Router

Dashboard statistics endpoints:
- GET /dashboard/summary - Overall summary
- GET /dashboard/violations - Violation statistics
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User
from app.models.compliance_check import ComplianceCheck
from app.models.rule import Rule
from app.models.audit_log import AuditLog
from app.schemas.dashboard import (
    DashboardSummary,
    ViolationStats,
    InspectionSummary,
    ViolationType,
)
from app.dependencies.auth import get_current_user


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get dashboard summary statistics.

    Returns:
    - Total inspections
    - Compliant count
    - Non-compliant count
    - Manual review count
    - Total violations
    - Compliance percentage
    - Recent inspections
    - Top violation types
    """
    # Total inspections
    total_inspections = db.query(Inspection).count()

    # Count by status
    compliant = db.query(Inspection).filter(Inspection.status == "COMPLIANT").count()
    non_compliant = db.query(Inspection).filter(Inspection.status == "NON_COMPLIANT").count()
    manual_review = db.query(Inspection).filter(Inspection.status == "MANUAL_REVIEW").count()
    processing = db.query(Inspection).filter(Inspection.status == "PROCESSING").count()

    # Total violations (from compliance checks)
    total_violations = db.query(ComplianceCheck).filter(
        ComplianceCheck.status == "FAIL"
    ).count()

    # Compliance percentage
    if total_inspections > 0:
        compliance_percentage = round(
            (compliant / total_inspections) * 100, 2
        )
    else:
        compliance_percentage = 0.0

    # Recent inspections (last 10)
    recent = db.query(Inspection).order_by(
        Inspection.created_at.desc()
    ).limit(10).all()

    recent_inspections = []
    for insp in recent:
        summary = {
            "id": insp.id,
            "status": insp.status,
            "product_name": None,
            "inspector_name": None,
            "created_at": insp.created_at,
        }

        if insp.product_id:
            product = db.query(Product).filter(Product.id == insp.product_id).first()
            if product:
                summary["product_name"] = product.product_name

        if insp.inspector_id:
            inspector = db.query(User).filter(User.id == insp.inspector_id).first()
            if inspector:
                summary["inspector_name"] = inspector.full_name or inspector.username

        recent_inspections.append(summary)

    # Top violation types
    violation_checks = db.query(ComplianceCheck).filter(
        ComplianceCheck.status == "FAIL"
    ).all()

    violation_counts = {}
    for check in violation_checks:
        rule_code = check.rule_code
        if rule_code not in violation_counts:
            violation_counts[rule_code] = {
                "rule_code": rule_code,
                "rule_name": "",
                "count": 0,
                "severity": "MEDIUM",
            }
        violation_counts[rule_code]["count"] += 1

    # Get rule names and severity
    for rule_code, data in violation_counts.items():
        rule = db.query(Rule).filter(Rule.rule_code == rule_code).first()
        if rule:
            data["rule_name"] = rule.rule_name
            data["severity"] = rule.severity

    top_violations = sorted(
        violation_counts.values(),
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    top_violation_types = [
        ViolationType(
            rule_code=v["rule_code"],
            rule_name=v["rule_name"],
            count=v["count"],
            severity=v["severity"],
        )
        for v in top_violations
    ]

    return DashboardSummary(
        total_inspections=total_inspections,
        compliant=compliant,
        non_compliant=non_compliant,
        manual_review=manual_review,
        processing=processing,
        total_violations=total_violations,
        compliance_percentage=compliance_percentage,
        recent_inspections=recent_inspections,
        top_violation_types=top_violation_types,
    )


@router.get("/violations", response_model=List[ViolationStats])
def get_violations_stats(
    rule_code: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get violation statistics grouped by rule.

    Query parameters:
    - rule_code: Filter by specific rule
    - severity: Filter by severity level
    - limit: Maximum number of results
    """
    # Base query for failed checks
    query = db.query(
        ComplianceCheck.rule_code,
        func.count(ComplianceCheck.id).label("violation_count"),
    ).filter(
        ComplianceCheck.status == "FAIL"
    ).group_by(
        ComplianceCheck.rule_code
    )

    # Apply filters
    if rule_code:
        query = query.filter(ComplianceCheck.rule_code == rule_code)

    # Get results
    results = query.all()

    # Build response
    violation_stats = []

    for rule_code, count in results:
        # Get rule info
        rule = db.query(Rule).filter(Rule.rule_code == rule_code).first()

        rule_name = rule.rule_name if rule else rule_code
        rule_severity = rule.severity if rule else "MEDIUM"

        # Filter by severity if specified
        if severity and rule_severity != severity:
            continue

        # Calculate percentage
        total_violations = db.query(ComplianceCheck).filter(
            ComplianceCheck.status == "FAIL"
        ).count()

        percentage = (count / total_violations * 100) if total_violations > 0 else 0

        violation_stats.append(
            ViolationStats(
                rule_code=rule_code,
                rule_name=rule_name,
                violation_count=count,
                severity=rule_severity,
                percentage=round(percentage, 2),
            )
        )

    # Sort by violation count (descending)
    violation_stats.sort(key=lambda x: x.violation_count, reverse=True)

    # Apply limit
    return violation_stats[:limit]
