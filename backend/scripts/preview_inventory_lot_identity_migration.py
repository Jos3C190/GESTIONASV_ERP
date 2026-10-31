"""Read-only preflight for migration 0085's receipt-detail lot identity."""

from __future__ import annotations

import argparse
import json
import sys

import sqlalchemy as sa
from app.core.config import settings
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

MIN_CODE_LENGTH = 3
MAX_CODE_LENGTH = 120


def preview(expected_database: str) -> int:
    engine: Engine = sa.create_engine(settings.DATABASE_URL_SYNC, poolclass=NullPool)
    try:
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            actual_database = str(connection.scalar(sa.text("SELECT current_database()")))
            if actual_database != expected_database:
                print(
                    f"Destino rechazado: la conexión está en {actual_database!r}, "
                    f"se esperaba {expected_database!r}.",
                    file=sys.stderr,
                )
                return 2

            revision = str(
                connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            )
            has_detail_code_column = bool(
                connection.scalar(
                    sa.text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'inventory_lot_details' AND column_name = 'code')"
                    )
                )
            )
            details = connection.execute(
                sa.text(
                    "SELECT detail.company_id, detail.id, detail.inventory_lot_id, "
                    "detail.accepted_quantity_base, lot.code AS header_code, "
                    "lot.code || '-D' || upper(replace(detail.id::text, '-', '')) AS proposed_code "
                    "FROM inventory_lot_details AS detail "
                    "LEFT JOIN inventory_lots AS lot "
                    "ON lot.company_id = detail.company_id AND lot.id = detail.inventory_lot_id "
                    "ORDER BY detail.company_id, detail.id"
                )
            ).mappings().all()
            duplicates = connection.execute(
                sa.text(
                    "SELECT company_id, proposed_code, count(*) AS occurrences "
                    "FROM (SELECT detail.company_id, "
                    "lot.code || '-D' || upper(replace(detail.id::text, '-', '')) AS proposed_code "
                    "FROM inventory_lot_details AS detail JOIN inventory_lots AS lot "
                    "ON lot.company_id = detail.company_id AND lot.id = detail.inventory_lot_id) AS map "
                    "GROUP BY company_id, proposed_code HAVING count(*) > 1 "
                    "ORDER BY company_id, proposed_code"
                )
            ).mappings().all()
            missing_origins = [row for row in details if row["header_code"] is None]
            existing_codes = (
                dict(
                    connection.execute(
                        sa.text("SELECT id, code FROM inventory_lot_details")
                    ).all()
                )
                if has_detail_code_column
                else {}
            )
            invalid_codes = [
                row
                for row in details
                if row["proposed_code"] is not None
                and not MIN_CODE_LENGTH <= len(row["proposed_code"]) <= MAX_CODE_LENGTH
            ]
            incorrect_existing_codes = [
                row
                for row in details
                if has_detail_code_column
                and existing_codes.get(row["id"]) != row["proposed_code"]
            ]
            history = connection.execute(
                sa.text(
                    "SELECT count(*) AS movement_lines, "
                    "count(*) FILTER (WHERE hu.inventory_lot_detail_id IS NOT NULL) AS "
                    "resolvable_through_handling_unit "
                    "FROM inventory_movement_lines AS line "
                    "LEFT JOIN inventory_handling_units AS hu "
                    "ON hu.company_id = line.company_id AND hu.id = line.handling_unit_id"
                )
            ).mappings().one()
            summary = {
                "database": actual_database,
                "revision": revision,
                "detail_code_column_exists": has_detail_code_column,
                "mode": "read-only preview; no rows were changed",
                "planned_detail_codes": [
                    {
                        "company_id": str(row["company_id"]),
                        "detail_id": str(row["id"]),
                        "receipt_header_code": row["header_code"],
                        "existing_code": existing_codes.get(row["id"]),
                        "proposed_code": row["proposed_code"],
                        "accepted_quantity_base": str(row["accepted_quantity_base"]),
                    }
                    for row in details
                ],
                "movement_history": {
                    "rows": int(history["movement_lines"]),
                    "legacy_lines_resolvable_through_exact_handling_unit": int(
                        history["resolvable_through_handling_unit"]
                    ),
                    "historical_lines_will_be_modified": False,
                },
                "label_print_rows_preserved": int(
                    connection.scalar(sa.text("SELECT count(*) FROM inventory_label_prints"))
                ),
                "validation_errors": [
                    *(
                        [
                            f"Detalle {row['id']} no tiene una cabecera de recepción válida."
                            for row in missing_origins
                        ]
                    ),
                    *(
                        [
                            f"Código propuesto fuera de longitud para el detalle {row['id']}."
                            for row in invalid_codes
                        ]
                    ),
                    *(
                        [
                            f"El código guardado no coincide con la identidad esperada para el detalle {row['id']}."
                            for row in incorrect_existing_codes
                        ]
                    ),
                    *(
                        [
                            f"Código duplicado {row['proposed_code']} en empresa {row['company_id']}."
                            for row in duplicates
                        ]
                    ),
                ],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return 1 if summary["validation_errors"] else 0
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-database",
        required=True,
        help="Exact PostgreSQL database name expected for this read-only preview.",
    )
    args = parser.parse_args()
    return preview(args.expect_database)


if __name__ == "__main__":
    raise SystemExit(main())
