"""Create retaceo landed-cost allocations and reconcile RBAC permissions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("retaceos:read", "Ver retaceos y costos landed", "retaceos"),
    ("retaceos:manage", "Crear, editar y cancelar retaceos", "retaceos"),
    ("retaceos:calculate", "Calcular distribución de costos de retaceo", "retaceos"),
    ("retaceos:verify", "Verificar y cerrar retaceos", "retaceos"),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.create_table(
        "retaceos",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("purchase_id", UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total_fob", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_freight", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_expenses", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_dai", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("import_vat", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_retaceos_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            name="fk_retaceos_purchase_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_retaceos_branch_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_retaceos_created_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currencies.code"],
            name="fk_retaceos_currency_currencies",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('draft','calculated','verified','cancelled','closed')",
            name="ck_retaceos_status",
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_retaceos_currency",
        ),
        sa.CheckConstraint("total_fob > 0", name="ck_retaceos_fob_positive"),
        sa.CheckConstraint(
            "total_freight >= 0 AND total_expenses >= 0 AND total_dai >= 0 "
            "AND import_vat >= 0 AND total_cost >= 0",
            name="ck_retaceos_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "total_cost = total_fob + total_freight + total_expenses + total_dai",
            name="ck_retaceos_total_cost",
        ),
    )
    op.create_index(
        "uq_retaceos_id_company",
        "retaceos",
        ["id", "company_id"],
        unique=True,
    )
    op.create_index(
        "uq_retaceos_company_code",
        "retaceos",
        ["company_id", "code"],
        unique=True,
    )
    op.create_index(
        "ix_retaceos_company_status_created",
        "retaceos",
        ["company_id", "status", "created_at"],
    )
    op.create_index(
        "ix_retaceos_purchase_created",
        "retaceos",
        ["purchase_id", "created_at"],
    )
    op.create_index(
        "ix_retaceos_branch_created",
        "retaceos",
        ["branch_id", "created_at"],
    )

    op.create_table(
        "retaceo_details",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("retaceo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_detail_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_fob", sa.Numeric(18, 6), nullable=False),
        sa.Column("freight", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("expenses", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("dai", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["retaceo_id", "company_id"],
            ["retaceos.id", "retaceos.company_id"],
            name="fk_retaceo_details_retaceo_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_retaceo_details_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_retaceo_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_retaceo_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_retaceo_details_quantity_positive"),
        sa.CheckConstraint(
            "cost_fob >= 0 AND freight >= 0 AND expenses >= 0 AND dai >= 0 "
            "AND total_cost >= 0 AND unit_cost >= 0",
            name="ck_retaceo_details_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "total_cost = cost_fob + freight + expenses + dai",
            name="ck_retaceo_details_total_cost",
        ),
    )
    op.create_index(
        "uq_retaceo_details_id_company",
        "retaceo_details",
        ["id", "company_id"],
        unique=True,
    )
    op.create_index(
        "uq_retaceo_details_retaceo_purchase_detail",
        "retaceo_details",
        ["retaceo_id", "purchase_detail_id"],
        unique=True,
    )
    op.create_index(
        "ix_retaceo_details_retaceo_created",
        "retaceo_details",
        ["retaceo_id", "created_at"],
    )
    op.create_index(
        "ix_retaceo_details_company_purchase_detail",
        "retaceo_details",
        ["company_id", "purchase_detail_id"],
    )

    for code, description, module in PERMISSIONS:
        op.execute(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            f"VALUES (gen_random_uuid(), {_sql_literal(code)}, "
            f"{_sql_literal(description)}, {_sql_literal(module)}, now()) "
            "ON CONFLICT DO NOTHING"
        )

    permission_codes = ",".join(_sql_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code IN ({permission_codes}) "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("retaceo_details")
    op.drop_table("retaceos")
