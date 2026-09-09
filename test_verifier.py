import asyncio
import sqlite3
import json
from types import SimpleNamespace

from app.services.field_extractor import FieldExtractorService


async def main():
    conn = sqlite3.connect("legal_metrology.db")

    rows = conn.execute(
        """
        SELECT
            id,
            inspection_id,
            text,
            confidence,
            bounding_box,
            source_image,
            page_number,
            created_at
        FROM ocr_data
        WHERE inspection_id = 14
        ORDER BY id
        """
    ).fetchall()

    items = [
        SimpleNamespace(
            id=row[0],
            inspection_id=row[1],
            text=row[2],
            confidence=row[3],
            bbox=json.loads(row[4])
            if row[4]
            else None,
            source_image=row[5],
            page_number=row[6],
            created_at=row[7],
        )
        for row in rows
    ]

    extractor = FieldExtractorService()

    result = await extractor.extract_fields(items)

    output = {
        "mrp": result.get("mrp"),
        "net_quantity": result.get("net_quantity"),
        "product_name": result.get("product_name"),
        "verification": result.get("verification"),
    }

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
    )

    conn.close()


asyncio.run(main())