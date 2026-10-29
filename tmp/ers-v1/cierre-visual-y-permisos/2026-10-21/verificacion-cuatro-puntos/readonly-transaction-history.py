"""Read append-only valuation/movement history for V04 in the isolated clone."""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXPECTED = "erp_db_ers_final4p_20261020"
url = make_url(os.environ["DATABASE_URL_SYNC"])
if url.database != EXPECTED:
    raise SystemExit(f"Refusing database {url.database!r}; expected isolated clone.")

engine = create_engine(url)
with engine.connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    print(f"DATABASE={url.database}; READ ONLY")
    previous = connection.execute(
        text(
            """
            SELECT DISTINCT ON (p.sku) p.sku, e.sequence, e.kind,
                   e.balance_quantity, e.balance_value, e.average_unit_cost, e.posted_at
            FROM inventory_valuation_entries e
            JOIN inventory_items i ON i.company_id = e.company_id AND i.id = e.inventory_item_id
            JOIN products p ON p.id_product = i.product_id
            WHERE p.sku IN ('PRD-JAR-012', 'PRD-EMP-009')
              AND e.posted_at < TIMESTAMPTZ '2026-10-21 05:01:00+00'
            ORDER BY p.sku, e.sequence DESC
            """
        )
    ).all()
    for row in previous:
        print("VALUATION_BEFORE_V04", *row, sep="|")
    entries = connection.execute(
        text(
            """
            SELECT p.sku, e.id, e.sequence, e.kind, e.quantity_base, e.source_value,
                   e.inventory_delta, e.balance_quantity, e.balance_value,
                   e.average_unit_cost, e.original_entry_id, e.movement_line_id,
                   m.movement_type, m.source_reference, e.posted_at
            FROM inventory_valuation_entries e
            JOIN inventory_items i ON i.company_id = e.company_id AND i.id = e.inventory_item_id
            JOIN products p ON p.id_product = i.product_id
            LEFT JOIN inventory_movement_lines ml
              ON ml.company_id = e.company_id AND ml.id = e.movement_line_id
            LEFT JOIN inventory_movements m
              ON m.company_id = ml.company_id AND m.id = ml.movement_id
            WHERE p.sku IN ('PRD-JAR-012', 'PRD-EMP-009')
              AND e.posted_at >= TIMESTAMPTZ '2026-10-20 00:00:00+00'
            ORDER BY p.sku, e.sequence
            """
        )
    ).all()
    for row in entries:
        print("VALUATION_HISTORY", *row, sep="|")

    movements = connection.execute(
        text(
            """
            SELECT p.sku, m.id, m.movement_type, m.source_reference, m.posted_at,
                   ml.id, ml.quantity_base, ml.handling_unit_id, ml.from_warehouse_id,
                   ml.from_location_id, ml.from_stock_status, ml.to_warehouse_id,
                   ml.to_location_id, ml.to_stock_status
            FROM inventory_movements m
            JOIN inventory_movement_lines ml
              ON ml.company_id = m.company_id AND ml.movement_id = m.id
            JOIN inventory_items i
              ON i.company_id = ml.company_id AND i.id = ml.inventory_item_id
            JOIN products p ON p.id_product = i.product_id
            WHERE p.sku IN ('PRD-JAR-012', 'PRD-EMP-009')
              AND m.posted_at >= TIMESTAMPTZ '2026-10-20 00:00:00+00'
            ORDER BY p.sku, m.posted_at, m.id, ml.line_number
            """
        )
    ).all()
    for row in movements:
        print("MOVEMENT_HISTORY", *row, sep="|")
engine.dispose()
