"""Associate each company's central warehouse with an explicit headquarters branch.

The data update is transactional. It creates an administrative branch only for
companies that currently have a central warehouse and uses the company's
existing legal address/geography without inventing physical coordinates.
"""

from __future__ import annotations

import logging
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")
MIGRATION_HEADQUARTERS_DESCRIPTION = (
    "Recepción y distribución. Dirección y geografía tomadas del domicilio "
    "de la empresa; coordenadas físicas no registradas."
)


def _active_headquarters(bind: sa.Connection, company_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        bind.execute(
            sa.text(
                "SELECT id FROM branches WHERE company_id = :company_id "
                "AND is_headquarters AND is_active AND operational_status = 'active' "
                "AND deleted_at IS NULL ORDER BY id"
            ),
            {"company_id": company_id},
        ).scalars()
    )


def _unique_branch_name(bind: sa.Connection, company_id: uuid.UUID) -> str:
    existing = {
        value.casefold()
        for value in bind.execute(
            sa.text("SELECT name FROM branches WHERE company_id = :company_id AND deleted_at IS NULL"),
            {"company_id": company_id},
        ).scalars()
    }
    candidate = "Casa matriz"
    suffix = 2
    while candidate.casefold() in existing:
        candidate = f"Casa matriz ({suffix})"
        suffix += 1
    return candidate


def _unique_branch_code(bind: sa.Connection, company_id: uuid.UUID) -> str:
    existing = {
        value.casefold()
        for value in bind.execute(
            sa.text("SELECT code FROM branches WHERE company_id = :company_id AND deleted_at IS NULL AND code IS NOT NULL"),
            {"company_id": company_id},
        ).scalars()
    }
    prefix = f"HQ-{company_id.hex[:8]}".upper()
    candidate = prefix
    suffix = 2
    while candidate.casefold() in existing:
        candidate = f"{prefix[:29]}-{suffix}"
        suffix += 1
    return candidate


def _recoverable_migration_headquarters(
    bind: sa.Connection, company_id: uuid.UUID
) -> list[uuid.UUID]:
    """Find only a prior row created by this migration's exact provenance marker."""
    prefix = f"HQ-{company_id.hex[:8]}".upper()
    return list(
        bind.execute(
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


def _validate_before_writes(bind: sa.Connection) -> list[sa.RowMapping]:
    duplicate_active_centrals = bind.execute(
        sa.text(
            "SELECT company_id, count(*) AS central_count "
            "FROM warehouses WHERE is_central AND is_active "
            "AND operational_status = 'active' AND deleted_at IS NULL "
            "GROUP BY company_id HAVING count(*) > 1 ORDER BY company_id"
        )
    ).mappings().all()
    if duplicate_active_centrals:
        details = ", ".join(
            f"{row['company_id']} ({row['central_count']} bodegas)"
            for row in duplicate_active_centrals
        )
        raise RuntimeError(
            "B01 requiere resolver bodegas centrales activas duplicadas antes de migrar: "
            f"{details}. No se aplicaron cambios."
        )

    invalid_unassigned = bind.execute(
        sa.text(
            "SELECT id, company_id FROM warehouses "
            "WHERE branch_id IS NULL AND NOT is_central ORDER BY company_id, id"
        )
    ).mappings().all()
    if invalid_unassigned:
        details = ", ".join(str(row["id"]) for row in invalid_unassigned)
        raise RuntimeError(
            "Hay almacenes sin sucursal que no están marcados como centrales: "
            f"{details}. No se aplicaron cambios."
        )

    invalid_companies = bind.execute(
        sa.text(
            "SELECT DISTINCT warehouse.company_id FROM warehouses AS warehouse "
            "LEFT JOIN companies AS company ON company.id = warehouse.company_id "
            "WHERE warehouse.is_central AND (company.id IS NULL OR company.address IS NULL "
            "OR btrim(company.address) = '' "
            "OR company.department_id IS NULL OR company.municipality_id IS NULL "
            "OR company.district_id IS NULL) ORDER BY warehouse.company_id"
        )
    ).scalars().all()
    if invalid_companies:
        raise RuntimeError(
            "No se puede crear la matriz mínima sin dirección/geografía válida de la empresa: "
            f"{', '.join(map(str, invalid_companies))}. No se aplicaron cambios."
        )

    return bind.execute(
        sa.text(
            "SELECT company.id AS company_id, company.address, company.department_id, "
            "company.municipality_id, company.district_id, "
            "array_agg(warehouse.id ORDER BY warehouse.id) AS warehouse_ids "
            "FROM companies AS company JOIN warehouses AS warehouse "
            "ON warehouse.company_id = company.id AND warehouse.is_central "
            "GROUP BY company.id ORDER BY company.id"
        )
    ).mappings().all()


def _install_integrity_triggers() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION enforce_central_warehouse_headquarters() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.is_central AND NOT EXISTS (
                    SELECT 1 FROM branches AS headquarters
                    WHERE headquarters.id = NEW.branch_id
                      AND headquarters.company_id = NEW.company_id
                      AND headquarters.is_headquarters
                      AND headquarters.is_active
                      AND headquarters.operational_status = 'active'
                      AND headquarters.deleted_at IS NULL
                ) THEN
                    RAISE EXCEPTION 'La bodega central debe pertenecer a la matriz activa de su empresa.'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_warehouses_central_headquarters
            BEFORE INSERT OR UPDATE ON warehouses
            FOR EACH ROW EXECUTE FUNCTION enforce_central_warehouse_headquarters()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_headquarters_with_central_warehouse() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.is_headquarters AND (
                    NOT NEW.is_headquarters OR NOT NEW.is_active
                    OR NEW.operational_status <> 'active' OR NEW.deleted_at IS NOT NULL
                ) AND EXISTS (
                    SELECT 1 FROM warehouses
                    WHERE company_id = OLD.company_id AND branch_id = OLD.id AND is_central
                ) THEN
                    RAISE EXCEPTION 'No se puede desactivar o cambiar la matriz mientras tenga la bodega central asociada.'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_branches_protect_central_headquarters
            BEFORE UPDATE OF is_headquarters, is_active, operational_status, deleted_at ON branches
            FOR EACH ROW EXECUTE FUNCTION protect_headquarters_with_central_warehouse()
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    # Preflight all data before changing schema or records. PostgreSQL also
    # wraps this migration in a transaction, so any later failure rolls back.
    company_rows = _validate_before_writes(bind)

    op.add_column(
        "branches",
        sa.Column("is_headquarters", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "uq_branches_company_active_headquarters",
        "branches",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_headquarters AND is_active AND operational_status = 'active' AND deleted_at IS NULL"
        ),
    )

    # The legacy central-warehouse check requires branch_id to remain NULL.
    # Remove the obsolete shape constraints after preflight but before mapping;
    # the migration transaction protects the temporary interval until the new
    # branch-required constraint is installed below.
    legacy_check_names = {
        row["name"] for row in sa.inspect(bind).get_check_constraints("warehouses")
    }
    if "ck_warehouses_central_must_be_unassigned" in legacy_check_names:
        op.drop_constraint(
            "ck_warehouses_central_must_be_unassigned", "warehouses", type_="check"
        )
    if "ck_warehouses_unassigned_must_be_central" in legacy_check_names:
        op.drop_constraint(
            "ck_warehouses_unassigned_must_be_central", "warehouses", type_="check"
        )

    migration_map: list[dict[str, str | list[str]]] = []
    for row in company_rows:
        company_id = row["company_id"]
        active_headquarters = _active_headquarters(bind, company_id)
        if len(active_headquarters) > 1:
            raise RuntimeError(
                f"La empresa {company_id} tiene varias matrices activas: "
                f"{', '.join(map(str, active_headquarters))}. No se aplicaron cambios."
            )

        if active_headquarters:
            headquarters_id = active_headquarters[0]
            created = False
        else:
            recoverable = _recoverable_migration_headquarters(bind, company_id)
            if len(recoverable) > 1:
                raise RuntimeError(
                    f"La empresa {company_id} tiene varias matrices con marca de migración: "
                    f"{', '.join(map(str, recoverable))}. No se aplicaron cambios."
                )
            if recoverable:
                headquarters_id = recoverable[0]
                created = False
                bind.execute(
                    sa.text(
                        "UPDATE branches SET is_headquarters = true, updated_at = now() "
                        "WHERE id = :id"
                    ),
                    {"id": headquarters_id},
                )
            else:
                headquarters_id = uuid.uuid4()
                created = True
                bind.execute(
                    sa.text(
                        "INSERT INTO branches (id, company_id, name, code, address, department_id, "
                        "municipality_id, district_id, latitude, longitude, operational_status, "
                        "description, is_headquarters, is_active, created_at, updated_at) "
                        "VALUES (:id, :company_id, :name, :code, :address, :department_id, "
                        ":municipality_id, :district_id, NULL, NULL, 'active', :description, "
                        "true, true, now(), now())"
                    ),
                    {
                        "id": headquarters_id,
                        "company_id": company_id,
                        "name": _unique_branch_name(bind, company_id),
                        "code": _unique_branch_code(bind, company_id),
                        "address": row["address"],
                        "department_id": row["department_id"],
                        "municipality_id": row["municipality_id"],
                        "district_id": row["district_id"],
                        "description": MIGRATION_HEADQUARTERS_DESCRIPTION,
                    },
                )

        bind.execute(
            sa.text(
                "UPDATE warehouses SET branch_id = :headquarters_id, updated_at = now() "
                "WHERE company_id = :company_id AND is_central"
            ),
            {"headquarters_id": headquarters_id, "company_id": company_id},
        )
        warehouse_ids = [str(item) for item in row["warehouse_ids"]]
        migration_map.append(
            {
                "company_id": str(company_id),
                "headquarters_branch_id": str(headquarters_id),
                "created_branch": created,
                "reused_migration_marked_branch": not created and not active_headquarters,
                "central_warehouse_ids": warehouse_ids,
            }
        )

    remaining_unassigned = bind.scalar(
        sa.text("SELECT count(*) FROM warehouses WHERE branch_id IS NULL")
    )
    if remaining_unassigned:
        raise RuntimeError(
            f"Quedaron {remaining_unassigned} almacenes sin sucursal después del mapeo. "
            "La transacción completa se revertirá."
        )

    op.alter_column("warehouses", "branch_id", existing_type=sa.Uuid(), nullable=False)

    logger.info("B01 matriz por empresa (UUIDs): %s", migration_map)

    inspector = sa.inspect(bind)
    index_names = {row["name"] for row in inspector.get_indexes("warehouses")}
    if "uq_warehouses_company_active_central_unassigned" in index_names:
        op.drop_index("uq_warehouses_company_active_central_unassigned", table_name="warehouses")
    op.create_index(
        "uq_warehouses_company_active_central",
        "warehouses",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_central AND is_active AND operational_status = 'active' AND deleted_at IS NULL"
        ),
    )
    _install_integrity_triggers()


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TRIGGER IF EXISTS trg_branches_protect_central_headquarters ON branches")
    op.execute("DROP TRIGGER IF EXISTS trg_warehouses_central_headquarters ON warehouses")
    op.execute("DROP FUNCTION IF EXISTS protect_headquarters_with_central_warehouse()")
    op.execute("DROP FUNCTION IF EXISTS enforce_central_warehouse_headquarters()")

    index_names = {row["name"] for row in sa.inspect(bind).get_indexes("warehouses")}
    if "uq_warehouses_company_active_central" in index_names:
        op.drop_index("uq_warehouses_company_active_central", table_name="warehouses")

    # Restore the prior company-level representation. This changes only the
    # central warehouse's organizational link; inventory and document IDs,
    # quantities and history remain untouched.
    op.alter_column("warehouses", "branch_id", existing_type=sa.Uuid(), nullable=True)
    op.execute("UPDATE warehouses SET branch_id = NULL WHERE is_central")
    op.create_check_constraint(
        "ck_warehouses_unassigned_must_be_central",
        "warehouses",
        "branch_id IS NOT NULL OR is_central",
    )
    op.create_check_constraint(
        "ck_warehouses_central_must_be_unassigned",
        "warehouses",
        "NOT is_central OR branch_id IS NULL",
    )
    op.create_index(
        "uq_warehouses_company_active_central_unassigned",
        "warehouses",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text(
            "branch_id IS NULL AND is_central AND is_active "
            "AND operational_status = 'active' AND deleted_at IS NULL"
        ),
    )
    op.drop_index("uq_branches_company_active_headquarters", table_name="branches")
    op.drop_column("branches", "is_headquarters")
