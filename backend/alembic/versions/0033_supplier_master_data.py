"""Extend the supplier master for international purchasing.

Tax identifiers are deliberately generic and optional.  This revision keeps
the legacy supplier columns intact while adding normalized, company-scoped
catalogues and sensitive bank-account storage.  The downgrade is fail-closed:
it refuses to remove data that was entered after the migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, UUID

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

SEED_CURRENCIES = {
    "USD": ("Dólar estadounidense", "$", 2),
    "EUR": ("Euro", "€", 2),
    "GBP": ("Libra esterlina", "£", 2),
    "MXN": ("Peso mexicano", "$", 2),
    "GTQ": ("Quetzal guatemalteco", "Q", 2),
    "HNL": ("Lempira hondureño", "L", 2),
    "NIO": ("Córdoba nicaragüense", "C$", 2),
    "CRC": ("Colón costarricense", "₡", 2),
    "PAB": ("Balboa panameño", "B/.", 2),
    "CAD": ("Dólar canadiense", "C$", 2),
    "CNY": ("Yuan chino", "¥", 2),
    "JPY": ("Yen japonés", "¥", 0),
    "BRL": ("Real brasileño", "R$", 2),
    "COP": ("Peso colombiano", "$", 2),
}
SUPPLIER_PERMISSIONS = (
    ("suppliers:tax_identifiers", "Gestionar identificadores fiscales", "suppliers"),
    ("suppliers:addresses", "Gestionar direcciones de proveedores", "suppliers"),
    ("suppliers:bank_accounts", "Gestionar cuentas bancarias enmascaradas", "suppliers"),
)


def _assert_table_empty(bind: sa.Connection, table: str) -> None:
    count = int(bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())
    if count:
        raise RuntimeError(
            f"No se puede hacer downgrade 0033: {table} contiene {count} registros. "
            "Exporte o elimine esos datos de forma controlada antes de revertir."
        )


def upgrade() -> None:
    connection = op.get_bind()
    for code, description, module in SUPPLIER_PERMISSIONS:
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, module, created_at) "
                "VALUES (gen_random_uuid(), :code, :description, :module, now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"code": code, "description": description, "module": module},
        )
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("symbol", sa.String(8), nullable=False),
        sa.Column("decimal_places", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("code = upper(code) AND char_length(code) = 3", name="ck_currencies_iso_code"),
        sa.CheckConstraint("decimal_places BETWEEN 0 AND 6", name="ck_currencies_decimal_places"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_currencies_active_code", "currencies", ["is_active", "code"])
    op.bulk_insert(
        sa.table(
            "currencies",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("symbol", sa.String),
            sa.column("decimal_places", sa.SmallInteger),
        ),
        [
            {"code": code, "name": name, "symbol": symbol, "decimal_places": places}
            for code, (name, symbol, places) in SEED_CURRENCIES.items()
        ],
    )

    op.create_table(
        "supplier_groups",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_supplier_groups_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_supplier_groups_company_code"),
    )
    op.create_index("ix_supplier_groups_company_active", "supplier_groups", ["company_id", "is_active"])

    op.create_table(
        "payment_terms",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("net_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_payment_terms_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_payment_terms_company_code"),
        sa.CheckConstraint("net_days >= 0", name="ck_payment_terms_net_days"),
        sa.CheckConstraint("discount_days BETWEEN 0 AND net_days", name="ck_payment_terms_discount_days"),
        sa.CheckConstraint("discount_percent BETWEEN 0 AND 100", name="ck_payment_terms_discount_percent"),
    )
    op.create_index("ix_payment_terms_company_active", "payment_terms", ["company_id", "is_active"])

    op.add_column("suppliers", sa.Column("legal_name", sa.String(240), nullable=True))
    op.add_column("suppliers", sa.Column("supplier_group_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "suppliers",
        sa.Column("supplier_status", sa.String(24), nullable=False, server_default="approved"),
    )
    op.add_column("suppliers", sa.Column("hold_reason", sa.String(500), nullable=True))
    op.add_column("suppliers", sa.Column("hold_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("suppliers", sa.Column("hold_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("suppliers", sa.Column("default_currency_code", sa.String(3), nullable=True))
    op.add_column("suppliers", sa.Column("payment_terms_id", UUID(as_uuid=True), nullable=True))
    op.add_column("suppliers", sa.Column("default_payment_method", sa.String(32), nullable=True))
    op.add_column("suppliers", sa.Column("external_reference", sa.String(120), nullable=True))
    op.create_foreign_key(
        "fk_suppliers_supplier_group_company",
        "suppliers",
        "supplier_groups",
        ["supplier_group_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_suppliers_payment_terms_company",
        "suppliers",
        "payment_terms",
        ["payment_terms_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_suppliers_default_currency",
        "suppliers",
        "currencies",
        ["default_currency_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_suppliers_status",
        "suppliers",
        "supplier_status IN ('pending_review', 'approved', 'on_hold', 'suspended', 'rejected', 'retired')",
    )
    op.create_check_constraint(
        "ck_suppliers_hold_range",
        "suppliers",
        "hold_until IS NULL OR hold_from IS NULL OR hold_until >= hold_from",
    )
    op.create_index("ix_suppliers_company_status", "suppliers", ["company_id", "supplier_status"])

    op.create_table(
        "supplier_tax_identifiers",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("identifier_type", sa.String(40), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("normalized_value", sa.String(200), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id_supplier"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id_country"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "country_id", "identifier_type", "normalized_value", name="uq_supplier_tax_identifier_value"),
        sa.CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_supplier_tax_identifier_dates"),
    )
    op.create_index("ix_supplier_tax_identifiers_supplier", "supplier_tax_identifiers", ["supplier_id"])
    op.create_index(
        "uq_supplier_tax_identifiers_primary_country",
        "supplier_tax_identifiers",
        ["supplier_id", "country_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "supplier_addresses",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("address_type", sa.String(24), nullable=False, server_default="other"),
        sa.Column("line1", sa.String(240), nullable=False),
        sa.Column("line2", sa.String(240), nullable=True),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("state_region", sa.String(120), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("postal_code", sa.String(32), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id_supplier"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id_country"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("address_type IN ('fiscal', 'billing', 'delivery', 'return', 'office', 'other')", name="ck_supplier_addresses_type"),
    )
    op.create_index("ix_supplier_addresses_supplier", "supplier_addresses", ["supplier_id"])
    op.create_index(
        "uq_supplier_addresses_primary_type",
        "supplier_addresses",
        ["supplier_id", "address_type"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "supplier_bank_accounts",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("bank_name", sa.String(160), nullable=False),
        sa.Column("account_holder", sa.String(200), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("account_type", sa.String(32), nullable=True),
        sa.Column("account_ciphertext", BYTEA(), nullable=False),
        sa.Column("iban_ciphertext", BYTEA(), nullable=True),
        sa.Column("encryption_key_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id_supplier"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id_country"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("char_length(last_four) = 4", name="ck_supplier_bank_last_four"),
        sa.CheckConstraint("status IN ('active', 'blocked', 'closed')", name="ck_supplier_bank_status"),
    )
    op.create_index("ix_supplier_bank_accounts_supplier", "supplier_bank_accounts", ["supplier_id"])
    op.create_index(
        "uq_supplier_bank_accounts_primary",
        "supplier_bank_accounts",
        ["supplier_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    # Preserve legacy free-text addresses without guessing legal/tax data.
    op.execute(
        sa.text(
            "INSERT INTO supplier_addresses (supplier_id, address_type, line1, is_primary) "
            "SELECT id_supplier, 'other', address, true FROM suppliers "
            "WHERE address IS NOT NULL AND btrim(address) <> ''"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "supplier_tax_identifiers",
        "supplier_addresses",
        "supplier_bank_accounts",
        "supplier_groups",
        "payment_terms",
    ):
        _assert_table_empty(bind, table)
    populated = bind.execute(
        sa.text(
            "SELECT count(*) FROM suppliers WHERE legal_name IS NOT NULL OR supplier_group_id IS NOT NULL "
            "OR supplier_status <> 'approved' OR hold_reason IS NOT NULL OR hold_from IS NOT NULL "
            "OR hold_until IS NOT NULL OR default_currency_code IS NOT NULL OR payment_terms_id IS NOT NULL "
            "OR default_payment_method IS NOT NULL OR external_reference IS NOT NULL"
        )
    ).scalar_one()
    if int(populated):
        raise RuntimeError("No se puede revertir 0033: hay datos maestros de proveedores en uso.")
    allowed_codes = ", ".join(f"'{code}'" for code in SEED_CURRENCIES)
    extra_currency = bind.execute(
        sa.text(f"SELECT count(*) FROM currencies WHERE code NOT IN ({allowed_codes})")
    ).scalar_one()
    if int(extra_currency):
        raise RuntimeError("No se puede revertir 0033: hay monedas agregadas por la empresa.")

    op.drop_index("uq_supplier_bank_accounts_primary", table_name="supplier_bank_accounts")
    op.drop_index("ix_supplier_bank_accounts_supplier", table_name="supplier_bank_accounts")
    op.drop_table("supplier_bank_accounts")
    op.drop_index("uq_supplier_addresses_primary_type", table_name="supplier_addresses")
    op.drop_index("ix_supplier_addresses_supplier", table_name="supplier_addresses")
    op.drop_table("supplier_addresses")
    op.drop_index("uq_supplier_tax_identifiers_primary_country", table_name="supplier_tax_identifiers")
    op.drop_index("ix_supplier_tax_identifiers_supplier", table_name="supplier_tax_identifiers")
    op.drop_table("supplier_tax_identifiers")
    op.drop_index("ix_suppliers_company_status", table_name="suppliers")
    op.drop_constraint("ck_suppliers_hold_range", "suppliers", type_="check")
    op.drop_constraint("ck_suppliers_status", "suppliers", type_="check")
    op.drop_constraint("fk_suppliers_default_currency", "suppliers", type_="foreignkey")
    op.drop_constraint("fk_suppliers_payment_terms_company", "suppliers", type_="foreignkey")
    op.drop_constraint("fk_suppliers_supplier_group_company", "suppliers", type_="foreignkey")
    for column in (
        "external_reference",
        "default_payment_method",
        "payment_terms_id",
        "default_currency_code",
        "hold_until",
        "hold_from",
        "hold_reason",
        "supplier_status",
        "supplier_group_id",
        "legal_name",
    ):
        op.drop_column("suppliers", column)
    op.drop_index("ix_payment_terms_company_active", table_name="payment_terms")
    op.drop_table("payment_terms")
    op.drop_index("ix_supplier_groups_company_active", table_name="supplier_groups")
    op.drop_table("supplier_groups")
    op.drop_index("ix_currencies_active_code", table_name="currencies")
    op.drop_table("currencies")
