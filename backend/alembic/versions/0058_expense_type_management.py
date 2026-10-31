"""Add expense-type management permission and starter company catalogs."""

from __future__ import annotations

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

PERMISSION_CODE = "expense_types:manage"
PERMISSION_DESCRIPTION = "Administrar tipos de gasto de compras"
PERMISSION_MODULE = "purchase_orders"

STARTER_TYPES = (
    ("Flete", "Transporte relacionado con la orden. Evita registrarlo dos veces si también se distribuirá en retaceo."),
    ("Seguro", "Seguro asociado al pedido o transporte."),
    ("Agente aduanal", "Servicio de gestión aduanera asociado a la compra."),
    ("Manejo y descarga", "Manipulación y descarga de la mercancía."),
    ("Almacenamiento", "Almacenamiento temporal relacionado con la orden."),
    ("Otros", "Otro cargo documentado que corresponda a esta orden."),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        "INSERT INTO permissions (id, code, description, module, created_at) "
        f"VALUES (gen_random_uuid(), {_sql_literal(PERMISSION_CODE)}, "
        f"{_sql_literal(PERMISSION_DESCRIPTION)}, {_sql_literal(PERMISSION_MODULE)}, now()) "
        "ON CONFLICT DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code = {_sql_literal(PERMISSION_CODE)} "
        "ON CONFLICT DO NOTHING"
    )

    for name, description in STARTER_TYPES:
        op.execute(
            "INSERT INTO expense_types (id, company_id, name, description, is_active, created_at, updated_at) "
            "SELECT gen_random_uuid(), c.id, "
            f"{_sql_literal(name)}, {_sql_literal(description)}, TRUE, now(), now() "
            "FROM companies c "
            "WHERE c.deleted_at IS NULL AND NOT EXISTS ("
            "SELECT 1 FROM expense_types e WHERE e.company_id = c.id "
            f"AND lower(e.name) = lower({_sql_literal(name)})"
            ") ON CONFLICT DO NOTHING"
        )


def downgrade() -> None:
    """Keep permission and catalog records to avoid damaging user data."""
    pass
