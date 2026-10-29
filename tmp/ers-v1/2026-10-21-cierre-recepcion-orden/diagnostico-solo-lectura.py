"""Inspect the reported order without changing operational data."""
import json
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

order_id = "2e94b2d9-13fb-4fff-8a3b-7b8ab4339752"
url = make_url(os.environ["DATABASE_URL_SYNC"])
if url.database != "erp_db":
    raise SystemExit("Unexpected database; read-only diagnostic not executed.")

engine = create_engine(url)
with engine.connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    order = connection.execute(text(
        "SELECT id, code, company_id, status FROM purchase_orders WHERE id = :order_id"
    ), {"order_id": order_id}).mappings().one_or_none()
    if order is None:
        raise SystemExit("Reported order not found; no writes performed.")
    print("ORDER", json.dumps(dict(order), default=str))
    receipts = connection.execute(text("""
        SELECT p.id, p.code, p.status, p.inventory_movement_id,
               d.purchase_order_detail_id, d.quantity_received, d.quantity_accepted
        FROM purchases p
        LEFT JOIN purchase_details d
          ON d.purchase_id = p.id AND d.company_id = p.company_id
        WHERE p.purchase_order_id = :order_id AND p.company_id = :company_id
        ORDER BY p.created_at, p.code, d.created_at
    """), {"order_id": order_id, "company_id": order["company_id"]}).mappings().all()
    for receipt in receipts:
        print("RECEIPT", json.dumps(dict(receipt), default=str))
    summary = connection.execute(text("""
        SELECT p.status, COUNT(*) AS documents
        FROM purchases p
        WHERE p.purchase_order_id = :order_id AND p.company_id = :company_id
        GROUP BY p.status ORDER BY p.status
    """), {"order_id": order_id, "company_id": order["company_id"]}).mappings().all()
    print("SUMMARY", json.dumps([dict(row) for row in summary], default=str))
    print("TRANSACTION_READ_ONLY", connection.exec_driver_sql("SHOW transaction_read_only").scalar())
