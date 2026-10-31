"""Inspect receipt unit conversions without changing products or stock."""
import json
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ["DATABASE_URL_SYNC"])
if url.database != "erp_db":
    raise SystemExit("Unexpected database; read-only diagnostic not executed.")

with create_engine(url).connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    rows = connection.execute(text("""
        SELECT p.id_product, p.sku, p.name, pd.quantity_received,
               u.code AS received_unit, b.code AS inventory_base_unit,
               i.is_active AS inventory_active,
               k.code AS presentation, ku.code AS presentation_unit,
               k.base_quantity AS conversion_to_base,
               r.code AS receipt, r.status AS receipt_status,
               r.inventory_movement_id, o.code AS order_code, o.status AS order_status
        FROM purchases r
        JOIN purchase_orders o ON o.id = r.purchase_order_id AND o.company_id = r.company_id
        JOIN purchase_details pd ON pd.purchase_id = r.id AND pd.company_id = r.company_id
        JOIN products p ON p.id_product = pd.product_id AND p.company_id = r.company_id
        JOIN units u ON u.id_unit = pd.unit_id
        LEFT JOIN inventory_items i ON i.company_id = pd.company_id
              AND i.product_id = pd.product_id AND i.variant_id IS NULL
        LEFT JOIN units b ON b.id_unit = i.base_unit_id
        LEFT JOIN inventory_packaging_definitions k ON k.inventory_item_id = i.id
              AND k.company_id = i.company_id AND k.is_active AND k.is_current
        LEFT JOIN units ku ON ku.id_unit = k.packaging_unit_id
        WHERE r.id = :receipt_id
        ORDER BY p.id_product, k.code
    """), {"receipt_id": "b803ed0c-bfd7-400a-b291-918b3628f45c"}).mappings().all()
    for row in rows:
        print("RECEIPT_UNIT", json.dumps(dict(row), default=str, ensure_ascii=True))
    print("TRANSACTION_READ_ONLY", connection.exec_driver_sql("SHOW transaction_read_only").scalar())
