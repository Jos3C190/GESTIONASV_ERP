"""Read-only B01 preflight and company-to-central-warehouse mapping.

Run from backend with the intended DATABASE_URL_SYNC configured. The required
database-name assertion prevents accidentally previewing a different target.
This command never writes data; Alembic 0084 performs the transactional update.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from app.core.config import settings
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

MIGRATION_HEADQUARTERS_DESCRIPTION = (
    "Recepción y distribución. Dirección y geografía tomadas del domicilio "
    "de la empresa; coordenadas físicas no registradas."
)


def _has_headquarters_column(connection: sa.Connection) -> bool:
    return bool(
        connection.scalar(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'branches' "
                "AND column_name = 'is_headquarters')"
            )
        )
    )


def _preview_rows(connection: sa.Connection, has_column: bool) -> Sequence[sa.RowMapping]:
    if has_column:
        statement = sa.text(
            "SELECT company.id AS company_id, company.commercial_name, company.address, "
            "company.department_id, company.municipality_id, company.district_id, "
            "COALESCE((SELECT array_agg(branch.id ORDER BY branch.id) FROM branches AS branch "
            "WHERE branch.company_id = company.id AND branch.is_headquarters AND branch.is_active "
            "AND branch.operational_status = 'active' AND branch.deleted_at IS NULL), "
            "ARRAY[]::uuid[]) AS headquarters_ids, "
            "array_agg(warehouse.id ORDER BY warehouse.id) AS central_warehouse_ids, "
            "count(*) FILTER (WHERE warehouse.is_active AND warehouse.operational_status = 'active' "
            "AND warehouse.deleted_at IS NULL) AS active_central_count "
            "FROM companies AS company JOIN warehouses AS warehouse "
            "ON warehouse.company_id = company.id AND warehouse.is_central "
            "GROUP BY company.id ORDER BY company.commercial_name, company.id"
        )
    else:
        statement = sa.text(
            "SELECT company.id AS company_id, company.commercial_name, company.address, "
            "company.department_id, company.municipality_id, company.district_id, "
            "ARRAY[]::uuid[] AS headquarters_ids, "
            "array_agg(warehouse.id ORDER BY warehouse.id) AS central_warehouse_ids, "
            "count(*) FILTER (WHERE warehouse.is_active AND warehouse.operational_status = 'active' "
            "AND warehouse.deleted_at IS NULL) AS active_central_count "
            "FROM companies AS company JOIN warehouses AS warehouse "
            "ON warehouse.company_id = company.id AND warehouse.is_central "
            "GROUP BY company.id ORDER BY company.commercial_name, company.id"
        )
    return connection.execute(statement).mappings().all()


def _recoverable_headquarters(
    connection: sa.Connection, company_id: object
) -> list[object]:
    """Return only migration-created rows carrying its exact provenance marker."""
    prefix = f"HQ-{str(company_id).replace('-', '')[:8]}".upper()
    return list(
        connection.execute(
            sa.text(
                "SELECT id FROM branches WHERE company_id = :company_id "
                "AND code LIKE :code_prefix AND name LIKE 'Casa matriz%' "
                "AND description = :description AND is_active "
                "AND operational_status = 'active' AND deleted_at IS NULL ORDER BY id"
            ),
            {
                "company_id": company_id,
                "code_prefix": f"{prefix}%",
                "description": MIGRATION_HEADQUARTERS_DESCRIPTION,
            },
        ).scalars()
    )


def _legacy_shape_errors(connection: sa.Connection) -> list[str]:
    """Return migration preconditions that do not depend on a headquarters row."""
    unassigned = connection.execute(
        sa.text(
            "SELECT id, company_id FROM warehouses "
            "WHERE branch_id IS NULL AND NOT is_central ORDER BY company_id, id"
        )
    ).mappings().all()
    errors: list[str] = []
    if unassigned:
        ids = ", ".join(str(row["id"]) for row in unassigned)
        errors.append(f"Almacenes sin sucursal que no son centrales: {ids}.")
    return errors


def _company_address_errors(connection: sa.Connection, company_id: object) -> list[str]:
    address_missing = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM companies WHERE id = :company_id "
            "AND (address IS NULL OR btrim(address) = ''))"
        ),
        {"company_id": company_id},
    )
    if address_missing:
        return [f"{company_id}: falta dirección de la empresa (nula o vacía)."]
    return []


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

                has_column = _has_headquarters_column(connection)
                rows = _preview_rows(connection, has_column)
                plan: list[dict[str, Any]] = []
                errors: list[str] = _legacy_shape_errors(connection)
                for row in rows:
                    headquarters = list(row["headquarters_ids"] or [])
                    recoverable = (
                        _recoverable_headquarters(connection, row["company_id"])
                        if not headquarters
                        else []
                    )
                    warehouse_ids = list(row["central_warehouse_ids"] or [])
                    if int(row["active_central_count"]) > 1:
                        errors.append(
                            f"{row['company_id']}: {row['active_central_count']} bodegas centrales activas."
                        )
                    if len(headquarters) > 1:
                        errors.append(
                            f"{row['company_id']}: varias matrices activas {headquarters}."
                        )
                    if len(recoverable) > 1:
                        errors.append(
                            f"{row['company_id']}: varias matrices recuperables por marca "
                            f"de migración {recoverable}."
                        )
                    if not all(
                        row[key]
                        for key in (
                            "department_id",
                            "municipality_id",
                            "district_id",
                        )
                    ):
                        errors.append(
                            f"{row['company_id']}: falta geografía de la empresa."
                        )
                    errors.extend(_company_address_errors(connection, row["company_id"]))
                    plan.append(
                        {
                            "company_id": str(row["company_id"]),
                            "company": row["commercial_name"],
                            "central_warehouse_ids": [str(value) for value in warehouse_ids],
                            "headquarters": (
                                str(headquarters[0])
                                if len(headquarters) == 1
                                else str(recoverable[0])
                                if len(recoverable) == 1
                                else "CREAR Casa matriz (sin coordenadas inventadas)"
                            ),
                            "reuse_migration_marked_branch": len(recoverable) == 1,
                            "address_source": "domicilio registrado de la empresa",
                        }
                    )

                print(
                    json.dumps(
                        {
                            "database": actual_database,
                            "schema_already_has_is_headquarters": has_column,
                            "mode": "read-only preview; no rows were changed",
                            "mapping_by_company": plan,
                            "validation_errors": errors,
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
                return 1 if errors else 0
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
