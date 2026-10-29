"""Read-only discovery of applicable V03 lot aliases in isolated ERS clone."""
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
    print(f"DATABASE={url.database}")

    lot_rows = connection.execute(
        text(
            """
            SELECT p.sku, p.name, l.code AS header_code, d.code AS detail_code,
                   d.quantity_received, d.accepted_quantity_base,
                   COUNT(DISTINCT h.id) AS open_hu_count,
                   COALESCE(SUM(h.quantity_base), 0) AS open_hu_quantity
            FROM inventory_lots l
            JOIN inventory_lot_details d
              ON d.company_id = l.company_id AND d.inventory_lot_id = l.id
            JOIN products p
              ON p.company_id = d.company_id AND p.id_product = d.product_id
            LEFT JOIN inventory_handling_units h
              ON h.company_id = d.company_id
             AND h.inventory_lot_detail_id = d.id
             AND h.closed_at IS NULL
            GROUP BY p.sku, p.name, l.code, d.code, d.quantity_received,
                     d.accepted_quantity_base
            ORDER BY l.code, d.code
            LIMIT 40
            """
        )
    ).all()
    for row in lot_rows:
        print("RECEIPT_ALIAS", *row, sep="|")

    movement_rows = connection.execute(
        text(
            """
            SELECT p.sku, m.movement_type, m.source_reference, m.posted_at,
                   ml.line_number, ml.lot_code,
                   ml.inventory_lot_detail_id, h.code AS handling_unit_code,
                   h.inventory_lot_detail_id AS current_hu_detail_id,
                   d.code AS resolved_detail_code, l.code AS resolved_header_code
            FROM inventory_movement_lines ml
            JOIN inventory_movements m
              ON m.company_id = ml.company_id AND m.id = ml.movement_id
            LEFT JOIN inventory_items ii
              ON ii.company_id = ml.company_id AND ii.id = ml.inventory_item_id
            LEFT JOIN products p
              ON p.company_id = ii.company_id AND p.id_product = ii.product_id
            LEFT JOIN inventory_handling_units h
              ON h.company_id = ml.company_id AND h.id = ml.handling_unit_id
            LEFT JOIN inventory_lot_details d
              ON d.company_id = ml.company_id
             AND d.id = COALESCE(ml.inventory_lot_detail_id, h.inventory_lot_detail_id)
            LEFT JOIN inventory_lots l
              ON l.company_id = d.company_id AND l.id = d.inventory_lot_id
            WHERE ml.lot_code IS NOT NULL
              AND (ml.inventory_lot_detail_id IS NULL OR ml.lot_code <> d.code)
            ORDER BY m.posted_at, ml.line_number
            LIMIT 40
            """
        )
    ).all()
    for row in movement_rows:
        print("MOVEMENT_ALIAS", *row, sep="|")

    legacy_units = connection.execute(
        text(
            """
            SELECT p.sku, h.code, h.lot_code, h.inventory_lot_id,
                   h.inventory_lot_detail_id, h.quantity_base, h.stock_status
            FROM inventory_handling_units h
            JOIN inventory_items ii
              ON ii.company_id = h.company_id AND ii.id = h.inventory_item_id
            JOIN products p
              ON p.company_id = ii.company_id AND p.id_product = ii.product_id
            WHERE h.closed_at IS NULL
              AND h.inventory_lot_id IS NULL
              AND h.inventory_lot_detail_id IS NULL
            ORDER BY p.sku, h.code
            LIMIT 40
            """
        )
    ).all()
    for row in legacy_units:
        print("LEGACY_UNIT_WITHOUT_RECEIPT_LOT", *row, sep="|")

engine.dispose()
