"""Guided capture of the circulation card: back category and chassis and engine numbers.

Revision ID: 0113
Revises: 0112
"""

from alembic import op
from sqlalchemy import text

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE document_captures DROP CONSTRAINT ck_document_captures_kind;
        ALTER TABLE document_captures ADD CONSTRAINT ck_document_captures_kind
          CHECK (kind IN ('driver_license','circulation_card'));
        ALTER TABLE fleet_vehicles
          ADD COLUMN chassis_number varchar(32),
          ADD COLUMN engine_number varchar(32);
        INSERT INTO document_categories (id, company_id, module, code, name, group_name,
          sort_order, is_active, requires_expiry, compliance_required, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, 'fleet', 'circulation_card_back',
          'Reverso de tarjeta de circulación', 'Documentos legales', 2, true, false, false,
          now(), now()
        FROM companies c
        ON CONFLICT (company_id, module, code) DO NOTHING;
    """)


def downgrade() -> None:
    in_use = op.get_bind().scalar(
        text("""
            SELECT (SELECT count(*) FROM document_captures WHERE kind = 'circulation_card')
                 + (SELECT count(*) FROM document_records r
                    JOIN document_categories c ON c.id = r.category_id
                    WHERE c.code = 'circulation_card_back')
                 + (SELECT count(*) FROM fleet_vehicles
                    WHERE chassis_number IS NOT NULL OR engine_number IS NOT NULL)
        """)
    )
    if in_use:
        raise RuntimeError(
            "Hay capturas de tarjeta o números de chasis y motor; no se revierte para no perderlos."
        )
    op.execute("""
        DELETE FROM document_categories WHERE code = 'circulation_card_back';
        ALTER TABLE fleet_vehicles DROP COLUMN chassis_number, DROP COLUMN engine_number;
        ALTER TABLE document_captures DROP CONSTRAINT ck_document_captures_kind;
        ALTER TABLE document_captures ADD CONSTRAINT ck_document_captures_kind
          CHECK (kind IN ('driver_license'));
    """)
