"""Protección de datos personales: aviso de privacidad, consentimientos, solicitudes ARCO-POL y
vulneraciones, por empresa.

Revision ID: 0121
Revises: 0120

Ley para la Protección de Datos Personales (D.L. 144 de 2024, reformada por el D.L. 659 de
2026). La supresión de un cliente se resuelve anonimizándolo (``sales_customers.anonymized_at``),
porque los documentos fiscales se conservan diez años.

El downgrade se niega si hay registros de privacidad o clientes anonimizados.
"""

from alembic import op
from sqlalchemy import text

revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("privacy:read", "Consultar avisos, solicitudes de titulares y vulneraciones"),
    ("privacy:manage", "Gestionar el aviso de privacidad, solicitudes y vulneraciones"),
    ("privacy:erase", "Anonimizar clientes por cancelación u olvido"),
)
_TABLES = (
    "personal_data_incidents",
    "data_subject_requests",
    "customer_consents",
    "company_privacy_notices",
)
CHANNELS = "('in_person','phone','email','web','written')"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE company_privacy_notices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            version integer NOT NULL,
            title varchar(200) NOT NULL,
            body text NOT NULL,
            covered_elements varchar(32)[] NOT NULL,
            published_by uuid REFERENCES users (id) ON DELETE SET NULL,
            published_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_company_privacy_notices_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_company_privacy_notices_version UNIQUE (company_id, version),
            CONSTRAINT ck_company_privacy_notices_version CHECK (version >= 1),
            CONSTRAINT ck_company_privacy_notices_body CHECK (char_length(btrim(body)) >= 200)
        )
    """)
    op.execute(f"""
        CREATE TABLE customer_consents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            purpose varchar(24) NOT NULL,
            channel varchar(16) NOT NULL,
            notice_id uuid NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT now(),
            granted_by uuid REFERENCES users (id) ON DELETE SET NULL,
            revoked_at timestamptz,
            revoked_by uuid REFERENCES users (id) ON DELETE SET NULL,
            revocation_channel varchar(16),
            notes text,
            CONSTRAINT fk_customer_consents_customer FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_customer_consents_notice FOREIGN KEY (company_id, notice_id)
                REFERENCES company_privacy_notices (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_customer_consents_purpose
                CHECK (purpose IN ('marketing','profiling','third_party_sharing')),
            CONSTRAINT ck_customer_consents_channel CHECK (channel IN {CHANNELS}),
            CONSTRAINT ck_customer_consents_revocation CHECK (
                (revoked_at IS NULL) = (revocation_channel IS NULL)
                AND (revocation_channel IS NULL OR revocation_channel IN {CHANNELS})
                AND (revoked_at IS NULL OR revoked_at >= granted_at)
            )
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_customer_consents_active ON customer_consents "
        "(company_id, customer_id, purpose) WHERE revoked_at IS NULL"
    )
    op.execute("""
        CREATE TABLE data_subject_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            code varchar(16) NOT NULL,
            customer_id uuid,
            requester_name varchar(200) NOT NULL,
            requester_document varchar(30),
            response_channel varchar(200) NOT NULL,
            right_type varchar(16) NOT NULL,
            description text NOT NULL,
            received_on date NOT NULL,
            due_on date NOT NULL,
            correction_due_on date,
            extended_due_on date,
            extension_reason text,
            status varchar(24) NOT NULL DEFAULT 'received',
            assignee_id uuid REFERENCES users (id) ON DELETE SET NULL,
            resolution text,
            closed_at timestamptz,
            closed_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_data_subject_requests_code UNIQUE (company_id, code),
            CONSTRAINT fk_data_subject_requests_customer FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_data_subject_requests_right CHECK (right_type IN
                ('access','rectification','cancellation','opposition','portability',
                 'erasure','restriction')),
            CONSTRAINT ck_data_subject_requests_status CHECK (status IN
                ('received','in_progress','awaiting_correction','extended','resolved','denied',
                 'returned','archived')),
            CONSTRAINT ck_data_subject_requests_due CHECK (due_on >= received_on),
            CONSTRAINT ck_data_subject_requests_extension CHECK (
                (extended_due_on IS NULL) = (extension_reason IS NULL)
                AND (extended_due_on IS NULL OR extended_due_on > due_on)
            ),
            CONSTRAINT ck_data_subject_requests_closed CHECK (
                (status IN ('resolved','denied','returned','archived'))
                = (closed_at IS NOT NULL AND resolution IS NOT NULL)
            ),
            CONSTRAINT ck_data_subject_requests_text CHECK (
                char_length(btrim(requester_name)) >= 3 AND char_length(btrim(description)) >= 5
            )
        )
    """)
    op.execute(
        "CREATE INDEX ix_data_subject_requests_open ON data_subject_requests "
        "(company_id, status, due_on)"
    )
    op.execute("""
        CREATE TABLE personal_data_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            code varchar(16) NOT NULL,
            discovered_at timestamptz NOT NULL,
            occurred_at timestamptz,
            description text NOT NULL,
            data_categories text NOT NULL,
            affected_count integer,
            measures text,
            notified_ace_at timestamptz,
            ace_reference varchar(200),
            notified_prosecutor_at timestamptz,
            prosecutor_reference varchar(200),
            notified_subjects_at timestamptz,
            subjects_reference varchar(200),
            subjects_not_required_reason text,
            status varchar(16) NOT NULL DEFAULT 'open',
            closed_at timestamptz,
            closed_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_personal_data_incidents_code UNIQUE (company_id, code),
            CONSTRAINT ck_personal_data_incidents_status CHECK (status IN ('open','closed')),
            CONSTRAINT ck_personal_data_incidents_affected
                CHECK (affected_count IS NULL OR affected_count >= 0),
            CONSTRAINT ck_personal_data_incidents_occurred
                CHECK (occurred_at IS NULL OR occurred_at <= discovered_at),
            CONSTRAINT ck_personal_data_incidents_closed CHECK (
                (status = 'closed') = (closed_at IS NOT NULL)
                AND (status <> 'closed' OR (
                    notified_ace_at IS NOT NULL AND notified_prosecutor_at IS NOT NULL
                    AND (notified_subjects_at IS NOT NULL
                         OR subjects_not_required_reason IS NOT NULL)
                ))
            )
        )
    """)
    op.execute("""
        ALTER TABLE sales_customers
            ADD COLUMN anonymized_at timestamptz,
            ADD CONSTRAINT ck_sales_customers_anonymized
                CHECK (anonymized_at IS NULL OR (NOT is_active AND NOT is_generic))
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'privacy', now())
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
    counts = " + ".join(f"(SELECT count(*) FROM {table})" for table in _TABLES)
    stored = (
        op.get_bind()
        .execute(
            text(
                f"SELECT {counts} + "
                "(SELECT count(*) FROM sales_customers WHERE anonymized_at IS NOT NULL)"
            )
        )
        .scalar()
    )
    if stored:
        raise RuntimeError(
            f"Hay {stored} registros de protección de datos que se perderían; "
            "la bitácora legal no se descarta al revertir la migración 0121."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("ALTER TABLE sales_customers DROP COLUMN anonymized_at")
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
