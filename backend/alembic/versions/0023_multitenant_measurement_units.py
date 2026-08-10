"""Introduce standard and company-owned measurement units.

Revision ID: 0023
Revises: 0022
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


UNIT_PERMISSIONS = (
    ("units:read", "Consultar unidades de medida"),
    ("units:create", "Crear unidades personalizadas"),
    ("units:update", "Editar unidades personalizadas"),
    ("units:activate", "Activar unidades para una empresa"),
    ("units:deactivate", "Desactivar unidades para una empresa"),
    ("units:manage_global", "Administrar el catálogo global de unidades"),
)


def upgrade() -> None:
    op.add_column("units", sa.Column("owner_company_id", UUID(as_uuid=True), nullable=True))
    op.add_column("units", sa.Column("code", sa.String(40), nullable=True))
    op.add_column("units", sa.Column("symbol", sa.String(20), nullable=True))
    op.add_column("units", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "units", sa.Column("is_standard", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "units", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_foreign_key(
        "fk_units_owner_company_id_companies",
        "units",
        "companies",
        ["owner_company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Preserve identifiers and derive stable codes/symbols for existing standards.
    op.execute(
        """
        UPDATE units
        SET code = 'UNIT-' || lpad(id_unit::text, 4, '0'),
            symbol = COALESCE(NULLIF(substring(name from '\\(([^)]+)\\)'), ''), left(name, 20)),
            is_standard = true,
            version = 1
        """
    )
    op.alter_column("units", "code", nullable=False)
    op.alter_column("units", "symbol", nullable=False)
    op.create_check_constraint(
        "ck_units_scope",
        "units",
        "(is_standard AND owner_company_id IS NULL) OR (NOT is_standard AND owner_company_id IS NOT NULL)",
    )
    op.create_index("ix_units_owner_company_id", "units", ["owner_company_id"])
    op.create_index("ix_units_standard_active", "units", ["is_standard", "is_active"])
    op.execute(
        "CREATE UNIQUE INDEX uq_units_global_code ON units (lower(code)) "
        "WHERE owner_company_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_units_company_code ON units (owner_company_id, lower(code)) "
        "WHERE owner_company_id IS NOT NULL"
    )

    op.create_table(
        "company_units",
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(100), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id_unit"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("company_id", "unit_id", name="company_units_pkey"),
    )
    op.create_index("ix_company_units_company_enabled", "company_units", ["company_id", "is_enabled"])
    op.execute(
        """
        CREATE FUNCTION validate_company_unit_scope() RETURNS trigger AS $$
        DECLARE unit_owner uuid;
        BEGIN
          SELECT owner_company_id INTO unit_owner FROM units WHERE id_unit = NEW.unit_id;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'Measurement unit does not exist';
          END IF;
          IF unit_owner IS NOT NULL AND unit_owner <> NEW.company_id THEN
            RAISE EXCEPTION 'Custom measurement unit belongs to another company';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_company_units_validate_scope "
        "BEFORE INSERT OR UPDATE ON company_units FOR EACH ROW EXECUTE FUNCTION validate_company_unit_scope()"
    )
    op.execute(
        "INSERT INTO company_units (company_id, unit_id) "
        "SELECT c.id, u.id_unit FROM companies c CROSS JOIN units u"
    )
    op.execute(
        """
        CREATE FUNCTION assign_standard_units_to_company() RETURNS trigger AS $$
        BEGIN
          INSERT INTO company_units (company_id, unit_id)
          SELECT NEW.id, id_unit FROM units
          WHERE is_standard = true AND is_active = true
          ON CONFLICT DO NOTHING;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_companies_assign_standard_units "
        "AFTER INSERT ON companies FOR EACH ROW EXECUTE FUNCTION assign_standard_units_to_company()"
    )

    # Permissions are data required by deployed environments where AUTO_SEED is disabled.
    for code, description in UNIT_PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, module) "
                "VALUES (gen_random_uuid(), :code, :description, 'units') "
                "ON CONFLICT (code) DO UPDATE SET description=EXCLUDED.description, module='units'"
            ).bindparams(code=code, description=description)
        )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT DISTINCT rp.role_id, target.id
        FROM role_permissions rp
        JOIN permissions source ON source.id = rp.permission_id
        CROSS JOIN permissions target
        WHERE source.code = 'reference_data:read' AND target.code = 'units:read'
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT DISTINCT rp.role_id, target.id
        FROM role_permissions rp
        JOIN permissions source ON source.id = rp.permission_id
        CROSS JOIN permissions target
        WHERE source.code = 'products:manage'
          AND target.code IN ('units:create','units:update','units:activate','units:deactivate')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'SUPER_ADMIN' AND p.code = 'units:manage_global'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code LIKE 'units:%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'units:%'")
    op.execute("DROP TRIGGER IF EXISTS trg_companies_assign_standard_units ON companies")
    op.execute("DROP FUNCTION IF EXISTS assign_standard_units_to_company()")
    op.execute("DROP TRIGGER IF EXISTS trg_company_units_validate_scope ON company_units")
    op.execute("DROP FUNCTION IF EXISTS validate_company_unit_scope()")
    op.drop_index("ix_company_units_company_enabled", table_name="company_units")
    op.drop_table("company_units")
    op.execute("DROP INDEX uq_units_company_code")
    op.execute("DROP INDEX uq_units_global_code")
    op.drop_index("ix_units_standard_active", table_name="units")
    op.drop_index("ix_units_owner_company_id", table_name="units")
    op.drop_constraint("ck_units_scope", "units", type_="check")
    op.drop_constraint("fk_units_owner_company_id_companies", "units", type_="foreignkey")
    for column in ("version", "is_standard", "description", "symbol", "code", "owner_company_id"):
        op.drop_column("units", column)
