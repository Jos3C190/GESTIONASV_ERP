"""Read-only reconciliation for the final four-point verification.

The script accepts only the isolated ERS-FINAL-4P connection configured in the
API container, and switches the transaction to READ ONLY before each query.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXPECTED = "erp_db_ers_final4p_20261020"
url = make_url(os.environ["DATABASE_URL_SYNC"])
if url.database != EXPECTED:
    raise SystemExit(f"Refusing database {url.database!r}; expected isolated clone.")

protected = [
    "ERS-INC-EE8FE228",
    "ERS-LATE-B1B55D6D",
    "ERS-REVIEW-DD6BBF85",
    "ERS-UI-F767BABC",
]

engine = create_engine(url)
with engine.connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    print(f"DATABASE={url.database}")
    protected_rows = connection.execute(
        text(
            """
            SELECT p.sku,
                   COALESCE((SELECT SUM(h.quantity_base)
                             FROM inventory_handling_units h
                             JOIN inventory_items ii ON ii.id = h.inventory_item_id
                             WHERE ii.product_id = p.id_product AND h.closed_at IS NULL), 0) AS physical,
                   COALESCE((SELECT SUM(a.quantity_base)
                             FROM inventory_cost_averages a
                             JOIN inventory_items ii ON ii.id = a.inventory_item_id
                             WHERE ii.product_id = p.id_product), 0) AS valued,
                   COALESCE((SELECT SUM(a.inventory_value)
                             FROM inventory_cost_averages a
                             JOIN inventory_items ii ON ii.id = a.inventory_item_id
                             WHERE ii.product_id = p.id_product), 0) AS value_usd
            FROM products p WHERE p.sku = ANY(:skus) ORDER BY p.sku
            """
        ),
        {"skus": protected},
    ).all()
    for row in protected_rows:
        print("PROTECTED", *row, sep="|")

    adjustment_rows = connection.execute(
        text(
            """
            SELECT id, code, status, correction_of_id, applied_at
            FROM inventory_adjustments
            WHERE code IN ('AJ-20261020-000005', 'AJ-20261020-000006')
            ORDER BY code
            """
        )
    ).all()
    for row in adjustment_rows:
        print("ADJUSTMENT", *row, sep="|")
    correction_lines = connection.execute(
        text(
            """
            SELECT a.code, d.direction, d.quantity_base, d.movement_id,
                   d.movement_line_id, d.documented_total_cost
            FROM inventory_adjustments a
            JOIN inventory_adjustment_details d
              ON d.company_id = a.company_id AND d.adjustment_id = a.id
            WHERE a.code IN ('AJ-20261020-000005', 'AJ-20261020-000006')
            ORDER BY a.code, d.line_number
            """
        )
    ).all()
    for row in correction_lines:
        print("ADJUSTMENT_LINE", *row, sep="|")
    valuation_rows = connection.execute(
        text(
            """
            SELECT p.sku, a.quantity_base, a.inventory_value, a.average_unit_cost
            FROM products p
            JOIN inventory_items ii ON ii.product_id = p.id_product
            JOIN inventory_cost_averages a
              ON a.inventory_item_id = ii.id AND a.company_id = ii.company_id
            WHERE p.sku IN ('PRD-JAR-012', 'PRD-EMP-009')
            ORDER BY p.sku
            """
        )
    ).all()
    for row in valuation_rows:
        print("VALUATION", *row, sep="|")

    return_rows = connection.execute(
        text(
            """
            SELECT r.id, r.code, r.status, COUNT(DISTINCT l.id) AS lines,
                   COALESCE(SUM(l.quantity_received_base), 0) AS received
            FROM sales_returns r
            LEFT JOIN sales_return_lines l ON l.company_id = r.company_id AND l.return_id = r.id
            WHERE r.code = 'DEV-20261021-530AF39F'
            GROUP BY r.id, r.code, r.status
            """
        )
    ).all()
    for row in return_rows:
        print("RETURN", *row, sep="|")
    return_events = connection.execute(
        text(
            """
            SELECT e.decision, e.quantity_base, e.condition, e.movement_id, e.valuation_entry_id
            FROM sales_return_events e
            JOIN sales_returns r ON r.company_id = e.company_id AND r.id = e.return_id
            WHERE r.code = 'DEV-20261021-530AF39F'
            ORDER BY e.created_at, e.id
            """
        )
    ).all()
    for row in return_events:
        print("RETURN_EVENT", *row, sep="|")

    hu_rows = connection.execute(
        text(
            """
            SELECT h.id, h.code, p.sku, h.quantity_base, h.stock_status, h.closed_at,
                   w.code AS warehouse_code, l.code AS location_code,
                   (SELECT COUNT(*) FROM inventory_movement_lines ml
                    WHERE ml.company_id = h.company_id AND ml.handling_unit_id = h.id) AS linked_movement_lines,
                   (SELECT COUNT(*) FROM inventory_trace_capabilities c
                    WHERE c.company_id = h.company_id AND c.handling_unit_id = h.id
                      AND c.revoked_at IS NULL) AS active_public_capabilities
            FROM inventory_handling_units h
            JOIN inventory_items ii ON ii.id = h.inventory_item_id
            JOIN products p ON p.id_product = ii.product_id
            JOIN warehouses w ON w.id = h.warehouse_id
            JOIN locations l ON l.id = h.location_id
            WHERE h.code IN ('HU-8D63FE508BF14124', 'HU-8FEE57267CC84449')
            ORDER BY h.code
            """
        )
    ).all()
    for row in hu_rows:
        print("TRACE_UNIT_AFTER_QR_AND_CANCEL", *row, sep="|")
engine.dispose()

# Read only the four protected SKUs from the habitual demonstration database.
source_url = url.set(database="erp_db")
source_engine = create_engine(source_url)
with source_engine.connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    print("DATABASE=erp_db (read-only protected-SKU check)")
    source_rows = connection.execute(
        text(
            """
            SELECT p.sku,
                   COALESCE((SELECT SUM(h.quantity_base)
                             FROM inventory_handling_units h
                             JOIN inventory_items ii ON ii.id = h.inventory_item_id
                             WHERE ii.product_id = p.id_product AND h.closed_at IS NULL), 0) AS physical,
                   COALESCE((SELECT SUM(a.quantity_base)
                             FROM inventory_cost_averages a
                             JOIN inventory_items ii ON ii.id = a.inventory_item_id
                             WHERE ii.product_id = p.id_product), 0) AS valued,
                   COALESCE((SELECT SUM(a.inventory_value)
                             FROM inventory_cost_averages a
                             JOIN inventory_items ii ON ii.id = a.inventory_item_id
                             WHERE ii.product_id = p.id_product), 0) AS value_usd
            FROM products p WHERE p.sku = ANY(:skus) ORDER BY p.sku
            """
        ),
        {"skus": protected},
    ).all()
    for row in source_rows:
        print("PROTECTED", *row, sep="|")
source_engine.dispose()
