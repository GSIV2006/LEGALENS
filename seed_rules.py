from app.database import SessionLocal
from app.models.rule import Rule

RULES = [
    {
        "rule_code": "LM-PROD-001",
        "rule_name": "Common / Generic Product Name",
        "description": "The packaged commodity should declare its common or generic name.",
        "field_name": "product_name",
        "required": True,
        "validation_type": "required",
        "severity": "HIGH",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": "{}",
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-QTY-001",
        "rule_name": "Net Quantity Declaration",
        "description": "The net quantity of the commodity should be declared in the prescribed manner.",
        "field_name": "net_quantity",
        "required": True,
        "validation_type": "required",
        "severity": "CRITICAL",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": "{}",
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-MRP-001",
        "rule_name": "Maximum Retail Price",
        "description": "Maximum Retail Price should be declared and should be inclusive of applicable taxes.",
        "field_name": "mrp",
        "required": True,
        "validation_type": "format",
        "severity": "CRITICAL",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": '{"currency":"INR","min":0}',
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-MFG-001",
        "rule_name": "Manufacturer / Packer Declaration",
        "description": "The applicable manufacturer, packer or importer identification should be declared.",
        "field_name": "manufacturer",
        "required": True,
        "validation_type": "required",
        "severity": "HIGH",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": "{}",
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-DATE-001",
        "rule_name": "Manufacture / Packing Date Information",
        "description": "Applicable month/year manufacture or packing information should be declared.",
        "field_name": "manufacturing_date",
        "required": True,
        "validation_type": "required",
        "severity": "MEDIUM",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": "{}",
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-CC-001",
        "rule_name": "Consumer Care Details",
        "description": "Consumer care contact information should be declared.",
        "field_name": "consumer_care",
        "required": True,
        "validation_type": "required",
        "severity": "MEDIUM",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": "{}",
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-ORIGIN-001",
        "rule_name": "Country of Origin",
        "description": "Country of origin information is applicable to imported commodities.",
        "field_name": "country_of_origin",
        "required": False,
        "validation_type": "required",
        "severity": "MEDIUM",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": '{"applies_when":"imported"}',
        "active": True,
        "ruleset_version": "1.0.0",
    },
    {
        "rule_code": "LM-UPC-001",
        "rule_name": "Unit Sale Price",
        "description": "Unit sale price should be declared where applicable under the packaged commodities requirements.",
        "field_name": "unit_sale_price",
        "required": False,
        "validation_type": "required",
        "severity": "HIGH",
        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "applicable_category": None,
        "validation_config": '{"conditional":true}',
        "active": True,
        "ruleset_version": "1.0.0",
    },
]

db = SessionLocal()

try:
    inserted = 0
    updated = 0

    for data in RULES:
        existing = (
            db.query(Rule)
            .filter(Rule.rule_code == data["rule_code"])
            .first()
        )

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(Rule(**data))
            inserted += 1

    db.commit()

    print("=" * 60)
    print("LEGALENS RULE SEED COMPLETE")
    print("=" * 60)
    print(f"Inserted: {inserted}")
    print(f"Updated : {updated}")
    print(f"Total active rules: {db.query(Rule).filter(Rule.active == True).count()}")
    print()

    rules = (
        db.query(Rule)
        .filter(Rule.ruleset_version == "1.0.0")
        .filter(Rule.active == True)
        .order_by(Rule.severity.desc(), Rule.rule_code)
        .all()
    )

    for rule in rules:
        print(
            f"{rule.rule_code:15} "
            f"{rule.field_name:22} "
            f"{rule.severity:8} "
            f"{rule.validation_type}"
        )

finally:
    db.close()
