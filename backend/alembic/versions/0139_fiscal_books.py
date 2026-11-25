"""Libros de IVA y anexos del F-07: datos fiscales de la compra.

Revision ID: 0139
Revises: 0138

Los libros de ventas salen de los documentos fiscales sellados y no necesitan tablas. El libro y el
anexo de compras necesitan saber qué documento entregó el proveedor, que hoy la compra no guarda:

- ``purchases``: clase y tipo del documento del proveedor (manual de anexos F-07 V14, anexo de
  compras), su número (o código de generación), número de control y sello si es DTE, el
  proveedor como figura en el documento (nombre y NIT, NRC o DUI, sin guiones), y la
  clasificación de renta de la compra (tipo de operación, clasificación, sector y tipo de costo o
  gasto). Todo o nada: una compra sin datos fiscales no entra al libro y se lista como pendiente.
- ``fiscal_book_settings``: la clasificación de renta de compras que se propone por empresa.
- Permisos ``fiscal_books:read`` (ver y descargar libros y anexos) y ``fiscal_books:manage``
  (registrar los datos fiscales de las compras y los valores por defecto).
"""

from alembic import op
from sqlalchemy import text

revision = "0139"
down_revision = "0138"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("fiscal_books:read", "Ver y descargar los libros de IVA y los anexos del F-07"),
    (
        "fiscal_books:manage",
        "Registrar los datos fiscales de las compras y la renta de compras por defecto",
    ),
)

# Catálogos de renta de compras del manual F-07 V14 (iguales en la plantilla de contaportable).
_OPERATION = "(1, 2, 3, 4, 8, 9)"
_CLASSIFICATION = "(1, 2, 8, 9)"
_SECTOR = "(1, 2, 3, 4, 8, 9)"
_COST_TYPE = "(1, 2, 3, 4, 5, 6, 7, 8, 9)"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE purchases
            ADD COLUMN fiscal_document_class smallint,
            ADD COLUMN fiscal_document_type varchar(2),
            ADD COLUMN fiscal_document_number varchar(100),
            ADD COLUMN fiscal_control_number varchar(31),
            ADD COLUMN fiscal_seal varchar(100),
            ADD COLUMN fiscal_supplier_name varchar(250),
            ADD COLUMN fiscal_supplier_id_type varchar(3),
            ADD COLUMN fiscal_supplier_id varchar(14),
            ADD COLUMN renta_operation_type smallint,
            ADD COLUMN renta_classification smallint,
            ADD COLUMN renta_sector smallint,
            ADD COLUMN renta_cost_type smallint,
            ADD COLUMN fiscal_recorded_by_id uuid,
            ADD COLUMN fiscal_recorded_at timestamptz,
            ADD CONSTRAINT fk_purchases_fiscal_recorded_by
                FOREIGN KEY (fiscal_recorded_by_id) REFERENCES users (id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_purchases_fiscal_document CHECK (
                (fiscal_document_class IS NULL AND fiscal_document_type IS NULL
                 AND fiscal_document_number IS NULL AND fiscal_control_number IS NULL
                 AND fiscal_seal IS NULL AND fiscal_supplier_name IS NULL
                 AND fiscal_supplier_id_type IS NULL AND fiscal_supplier_id IS NULL
                 AND renta_operation_type IS NULL
                 AND renta_classification IS NULL AND renta_sector IS NULL
                 AND renta_cost_type IS NULL AND fiscal_recorded_by_id IS NULL
                 AND fiscal_recorded_at IS NULL)
                OR (
                    fiscal_document_class IN (1, 3, 4)
                    AND fiscal_document_type IN ('03', '05', '06', '12', '13')
                    AND length(btrim(fiscal_document_number)) BETWEEN 1 AND 100
                    AND length(btrim(fiscal_supplier_name)) BETWEEN 1 AND 250
                    AND (
                        (fiscal_supplier_id_type = 'nit' AND fiscal_supplier_id ~ '^[0-9]{{14}}$')
                        OR (fiscal_supplier_id_type = 'dui' AND fiscal_supplier_id ~ '^[0-9]{{9}}$')
                        OR (fiscal_supplier_id_type = 'nrc' AND fiscal_supplier_id ~ '^[0-9]{{1,14}}$')
                    )
                    AND renta_operation_type IN {_OPERATION}
                    AND renta_classification IN {_CLASSIFICATION}
                    AND renta_sector IN {_SECTOR}
                    AND renta_cost_type IN {_COST_TYPE}
                    AND fiscal_recorded_by_id IS NOT NULL
                    AND fiscal_recorded_at IS NOT NULL
                    AND (fiscal_document_class <> 4
                         OR (fiscal_control_number IS NOT NULL AND fiscal_seal IS NOT NULL))
                )
            );
        CREATE TABLE fiscal_book_settings (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE RESTRICT,
            purchase_operation_type smallint NOT NULL DEFAULT 1,
            purchase_classification smallint NOT NULL DEFAULT 1,
            purchase_sector smallint NOT NULL DEFAULT 2,
            purchase_cost_type smallint NOT NULL DEFAULT 5,
            updated_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_fiscal_book_settings_renta CHECK (
                purchase_operation_type IN {_OPERATION}
                AND purchase_classification IN {_CLASSIFICATION}
                AND purchase_sector IN {_SECTOR}
                AND purchase_cost_type IN {_COST_TYPE}
            )
        );
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'fiscal', now())
            ON CONFLICT DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
              AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code = '{code}'
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    recorded = (
        op.get_bind()
        .execute(text("SELECT count(*) FROM purchases WHERE fiscal_document_class IS NOT NULL"))
        .scalar()
    )
    if recorded:
        raise RuntimeError(
            f"Hay {recorded} compras con datos fiscales del documento del proveedor; la migración "
            "0139 no los borra. Respáldalos antes de revertir."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("""
        DROP TABLE fiscal_book_settings;
        ALTER TABLE purchases
            DROP CONSTRAINT ck_purchases_fiscal_document,
            DROP CONSTRAINT fk_purchases_fiscal_recorded_by,
            DROP COLUMN fiscal_recorded_at,
            DROP COLUMN fiscal_recorded_by_id,
            DROP COLUMN renta_cost_type,
            DROP COLUMN renta_sector,
            DROP COLUMN renta_classification,
            DROP COLUMN renta_operation_type,
            DROP COLUMN fiscal_supplier_id,
            DROP COLUMN fiscal_supplier_id_type,
            DROP COLUMN fiscal_supplier_name,
            DROP COLUMN fiscal_seal,
            DROP COLUMN fiscal_control_number,
            DROP COLUMN fiscal_document_number,
            DROP COLUMN fiscal_document_type,
            DROP COLUMN fiscal_document_class;
    """)
