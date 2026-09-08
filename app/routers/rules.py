"""
Rules Router

CRUD endpoints for legal compliance rules.

Admin only for modifications.
All authenticated users can view.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rule import Rule
from app.models.audit_log import AuditLog
from app.schemas.rule import (
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleListResponse,
)
from app.dependencies.auth import get_current_user, admin_only
from app.models.user import User
from app.services.rule_engine import RuleEngine


router = APIRouter(prefix="/rules", tags=["Rules"])


@router.post("/", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    rule_data: RuleCreate,
    current_user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """
    Create a new compliance rule.

    ADMIN only.
    """
    # Validate rule code format
    engine = RuleEngine(db)
    if not engine.validate_rule_code(rule_data.rule_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rule code format. Expected: LM-XX-XXX (e.g., LM-MRP-001)",
        )

    # Validate severity
    if not engine.validate_severity(rule_data.severity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity. Valid: LOW, MEDIUM, HIGH, CRITICAL",
        )

    # Check for duplicate rule code
    existing = db.query(Rule).filter(Rule.rule_code == rule_data.rule_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule code already exists",
        )

    # Create rule
    rule = Rule(
        rule_code=rule_data.rule_code,
        rule_name=rule_data.rule_name,
        description=rule_data.description,
        field_name=rule_data.field_name,
        required=rule_data.required,
        validation_type=rule_data.validation_type,
        severity=rule_data.severity,
        legal_reference=rule_data.legal_reference,
        applicable_category=rule_data.applicable_category,
        validation_config=rule_data.validation_config,
        active=rule_data.active,
        ruleset_version=rule_data.ruleset_version,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    # Log creation
    audit_log = AuditLog(
        user_id=current_user.id,
        action="create_rule",
        entity_type="Rule",
        entity_id=rule.id,
        details={"rule_code": rule.rule_code, "rule_name": rule.rule_name},
    )
    db.add(audit_log)
    db.commit()

    return rule


@router.get("/", response_model=RuleListResponse)
def list_rules(
    active_only: bool = Query(True),
    severity: Optional[str] = Query(None),
    field_name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List compliance rules with filtering.

    Query parameters:
    - active_only: Only show active rules (default: True)
    - severity: Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
    - field_name: Filter by field name
    - search: Search in rule code, name, description
    - page: Page number
    - page_size: Items per page
    """
    engine = RuleEngine(db)
    rules = engine.get_all_rules(active_only=active_only)

    # Apply filters
    filtered_rules = []
    for rule in rules:
        if severity and rule.severity != severity:
            continue
        if field_name and rule.field_name != field_name:
            continue
        if search:
            search_lower = search.lower()
            if (search_lower not in rule.rule_code.lower() and
                search_lower not in rule.rule_name.lower() and
                (not rule.description or search_lower not in rule.description.lower())):
                continue
        filtered_rules.append(rule)

    # Paginate
    total = len(filtered_rules)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_rules = filtered_rules[start_idx:end_idx]

    # Get active count
    active_count = db.query(Rule).filter(Rule.active == True).count()

    return RuleListResponse(
        rules=[RuleResponse.model_validate(r) for r in paginated_rules],
        total=total,
        active_count=active_count,
        page=page,
        page_size=page_size,
    )


@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a rule by ID.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: int,
    rule_data: RuleUpdate,
    current_user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """
    Update a compliance rule.

    ADMIN only.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    # Validate rule code if being updated
    if rule_data.rule_code and rule_data.rule_code != rule.rule_code:
        if not RuleEngine(db).validate_rule_code(rule_data.rule_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid rule code format. Expected: LM-XX-XXX",
            )

        # Check for duplicate
        existing = db.query(Rule).filter(
            Rule.rule_code == rule_data.rule_code,
            Rule.id != rule_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rule code already exists",
            )

    # Update fields
    update_data = rule_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            setattr(rule, field, value)

    db.commit()
    db.refresh(rule)

    # Log update
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_rule",
        entity_type="Rule",
        entity_id=rule.id,
        details={"rule_code": rule.rule_code, "updated_fields": list(update_data.keys())},
    )
    db.add(audit_log)
    db.commit()

    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    current_user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """
    Delete a rule (soft delete - sets active=False).

    ADMIN only.
    """
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    # Soft delete
    rule.active = False
    db.commit()

    # Log deletion
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete_rule",
        entity_type="Rule",
        entity_id=rule.id,
        details={"rule_code": rule.rule_code},
    )
    db.add(audit_log)
    db.commit()

    return None


@router.get("/list/active")
def list_active_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of active rule codes only.

    Useful for quick reference.
    """
    rules = db.query(Rule).filter(Rule.active == True).all()

    return [
        {
            "id": r.id,
            "rule_code": r.rule_code,
            "rule_name": r.rule_name,
            "field_name": r.field_name,
            "severity": r.severity,
            "required": r.required,
        }
        for r in rules
    ]
