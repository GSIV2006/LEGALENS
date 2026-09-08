"""
Rule Engine

Manages legal rules and determines which rules apply to which inspections.
Provides rule validation and filtering based on product category.
"""
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.rule import Rule
from app.schemas.rule import RuleResponse


class RuleEngine:
    """
    Engine for managing and applying legal compliance rules.

    Responsibilities:
    - Fetch applicable rules for a product category
    - Validate rule configurations
    - Provide rule metadata for compliance checking
    """

    def __init__(self, db: Session):
        """Initialize rule engine with database session."""
        self.db = db

    def get_all_rules(
        self,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> List[Rule]:
        """
        Get all rules with optional filtering.

        Args:
            active_only: Only return active rules
            page: Page number
            page_size: Items per page

        Returns:
            List of rules
        """
        query = self.db.query(Rule)

        if active_only:
            query = query.filter(Rule.active == True)

        # Order by severity and rule code
        query = query.order_by(Rule.severity, Rule.rule_code)

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        return query.all()

    def get_rule_by_id(self, rule_id: int) -> Optional[Rule]:
        """Get a rule by ID."""
        return self.db.query(Rule).filter(Rule.id == rule_id).first()

    def get_rule_by_code(self, rule_code: str) -> Optional[Rule]:
        """Get a rule by its code."""
        return self.db.query(Rule).filter(Rule.rule_code == rule_code).first()

    def get_rules_by_field(self, field_name: str) -> List[Rule]:
        """Get all rules for a specific field."""
        return (
            self.db.query(Rule)
            .filter(Rule.field_name == field_name)
            .filter(Rule.active == True)
            .all()
        )

    def get_applicable_rules(
        self,
        category: Optional[str] = None,
        ruleset_version: str = "1.0.0",
        field_names: Optional[List[str]] = None,
    ) -> List[Rule]:
        """
        Get rules applicable to a specific product category or field.

        Args:
            category: Product category (optional)
            ruleset_version: Ruleset version to use
            field_names: Specific field names to get rules for (optional)

        Returns:
            List of applicable rules
        """
        query = self.db.query(Rule).filter(Rule.active == True)

        # Filter by ruleset version if specified
        if ruleset_version:
            query = query.filter(Rule.ruleset_version == ruleset_version)

        # Filter by category if specified
        if category:
            query = query.filter(
                or_(
                    Rule.applicable_category == None,  # No category restriction
                    Rule.applicable_category == category,
                )
            )

        # Filter by specific field names if provided
        if field_names:
            query = query.filter(Rule.field_name.in_(field_names))

        # Order by severity (CRITICAL first)
        query = query.order_by(
            Rule.severity.desc(),
            Rule.rule_code,
        )

        return query.all()

    def validate_rule_code(self, rule_code: str) -> bool:
        """
        Validate rule code format.

        Expected format: LM-XX-XXX (e.g., LM-MRP-001)
        """
        import re
        pattern = r'^LM-[A-Z]{2,4}-\d{3}$'
        return bool(re.match(pattern, rule_code))

    def validate_severity(self, severity: str) -> bool:
        """Validate severity level."""
        valid_severities = [Rule.Severity.LOW, Rule.Severity.MEDIUM,
                          Rule.Severity.HIGH, Rule.Severity.CRITICAL]
        return severity in valid_severities

    def validate_validation_type(self, validation_type: str) -> bool:
        """Validate validation type."""
        valid_types = [
            Rule.ValidationType.REQUIRED,
            Rule.ValidationType.FORMAT,
            Rule.ValidationType.RANGE,
            Rule.ValidationType.PATTERN,
            Rule.ValidationType.CUSTOM,
            Rule.ValidationType.EXISTS,
        ]
        return validation_type in valid_types

    def create_rule(self, rule_data: Dict) -> Rule:
        """Create a new rule."""
        rule = Rule(**rule_data)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, rule_id: int, rule_data: Dict) -> Optional[Rule]:
        """Update an existing rule."""
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            return None

        for key, value in rule_data.items():
            if hasattr(rule, key) and key not in ['id', 'created_at']:
                setattr(rule, key, value)

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a rule (soft delete by setting active=False)."""
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            return False

        rule.active = False
        self.db.commit()
        return True

    def get_rules_count(self, active_only: bool = True) -> int:
        """Get total count of rules."""
        query = self.db.query(Rule)
        if active_only:
            query = query.filter(Rule.active == True)
        return query.count()

    def get_severity_distribution(self) -> Dict[str, int]:
        """Get distribution of rules by severity."""
        rules = self.get_all_rules(active_only=True)
        distribution = {
            Rule.Severity.CRITICAL: 0,
            Rule.Severity.HIGH: 0,
            Rule.Severity.MEDIUM: 0,
            Rule.Severity.LOW: 0,
        }
        for rule in rules:
            if rule.severity in distribution:
                distribution[rule.severity] += 1
        return distribution


def get_applicable_rules(
    db: Any,
    category: Optional[str] = None,
    ruleset_version: str = "1.0.0",
    field_names: Optional[List[str]] = None,
) -> List[Any]:
    """
    Convenience function to get applicable rules.

    Args:
        db: Database session
        category: Product category filter
        ruleset_version: Ruleset version
        field_names: Specific fields to get rules for

    Returns:
        List of applicable Rule objects
    """
    engine = RuleEngine(db)
    return engine.get_applicable_rules(
        category=category,
        ruleset_version=ruleset_version,
        field_names=field_names,
    )


def get_all_rules_for_inspection(
    db: Any,
    field_names: Optional[List[str]] = None,
) -> List[Any]:
    """
    Get all active rules, optionally filtered by field names.

    Useful for getting rules to apply to an inspection.
    """
    engine = RuleEngine(db)
    field_names = field_names or [
        "mrp",
        "net_quantity",
        "product_name",
        "manufacturer",
        "manufacturing_date",
        "consumer_care",
        "country_of_origin",
    ]
    return engine.get_applicable_rules(field_names=field_names)
