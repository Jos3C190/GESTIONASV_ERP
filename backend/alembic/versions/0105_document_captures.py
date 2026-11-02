"""Guided document capture: state and outbox, license back category and override permission."""

from alembic import op
from sqlalchemy import text

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None

_OVERRIDE = "drivers:license_override"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE document_captures (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
          kind varchar(32) NOT NULL,
          owner_type varchar(32) NOT NULL,
          owner_id uuid NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'draft',
          front_document_id uuid,
          back_document_id uuid,
          extracted jsonb,
          attempts integer NOT NULL DEFAULT 0,
          failure_code varchar(64),
          started_at timestamptz,
          expires_at timestamptz NOT NULL,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          confirmed_by uuid REFERENCES users(id) ON DELETE SET NULL,
          confirmed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_document_captures_kind CHECK (kind IN ('driver_license')),
          CONSTRAINT ck_document_captures_status CHECK (status IN
            ('draft','pending','processing','ready','failed','confirmed','cancelled','expired')),
          CONSTRAINT ck_document_captures_attempts CHECK (attempts >= 0),
          CONSTRAINT fk_document_captures_front
            FOREIGN KEY (front_document_id) REFERENCES document_assets(id) ON DELETE SET NULL,
          CONSTRAINT fk_document_captures_back
            FOREIGN KEY (back_document_id) REFERENCES document_assets(id) ON DELETE SET NULL
        );
        COMMENT ON TABLE document_captures IS
          'Guided captures not yet confirmed; their photos stay out of document_records.';
        CREATE UNIQUE INDEX uq_document_captures_active ON document_captures
          (company_id, kind, owner_type, owner_id)
          WHERE status IN ('draft','pending','processing','ready','failed');
        CREATE INDEX ix_document_captures_pending ON document_captures (updated_at)
          WHERE status IN ('pending','processing');
        CREATE INDEX ix_document_captures_expires ON document_captures (expires_at)
          WHERE status IN ('draft','pending','processing','ready','failed');
    """)
    op.execute("""
        INSERT INTO document_categories (id, company_id, module, code, name, group_name,
          sort_order, is_active, requires_expiry, compliance_required, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, 'employees', 'driver_license_back',
          'Reverso de licencia de conducir', 'Conducción', 49, true, false, false, now(), now()
        FROM companies c
        ON CONFLICT (company_id, module, code) DO NOTHING;
    """)
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{_OVERRIDE}',
                'Confirmar licencias que no coinciden con el empleado', 'drivers', now())
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE p.code = '{_OVERRIDE}' AND p.deleted_at IS NULL AND r.deleted_at IS NULL
          AND ((r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL)
               OR r.name = 'ADMINISTRADOR DE OPERACIONES')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    connection = op.get_bind()
    in_use = connection.scalar(
        text("""
            SELECT (SELECT count(*) FROM document_captures)
                 + (SELECT count(*) FROM document_records r
                    JOIN document_categories c ON c.id = r.category_id
                    WHERE c.code = 'driver_license_back')
        """)
    )
    if in_use:
        raise RuntimeError(
            "Hay capturas o reversos de licencia registrados; no se revierte para no perderlos."
        )
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{_OVERRIDE}');
        DELETE FROM permissions WHERE code = '{_OVERRIDE}';
        DELETE FROM document_categories WHERE code = 'driver_license_back';
        DROP TABLE document_captures;
    """)
