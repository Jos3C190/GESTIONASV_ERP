"""Correo saliente propio de cada empresa.

Revision ID: 0128
Revises: 0127

Bloque V3c del área de Ventas. Cada empresa puede enviar los documentos a sus clientes desde su
propio servidor SMTP y su propio dominio. La contraseña se guarda cifrada (AES-GCM con la clave de
datos protegidos) y nunca se devuelve. El dominio y su DNS son responsabilidad de la empresa.
"""

from alembic import op
from sqlalchemy import text

revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE company_email_settings (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
            host varchar(255) NOT NULL,
            port integer NOT NULL,
            security varchar(8) NOT NULL,
            username varchar(255),
            password_encrypted bytea,
            from_address varchar(254) NOT NULL,
            from_name varchar(150),
            is_enabled boolean NOT NULL DEFAULT true,
            last_test_at timestamptz,
            last_test_ok boolean,
            last_test_error text,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_company_email_settings_port CHECK (port BETWEEN 1 AND 65535),
            CONSTRAINT ck_company_email_settings_security
                CHECK (security IN ('none','starttls','ssl')),
            CONSTRAINT ck_company_email_settings_host CHECK (length(btrim(host)) > 0),
            CONSTRAINT ck_company_email_settings_from CHECK (from_address LIKE '%_@_%._%'),
            CONSTRAINT ck_company_email_settings_password
                CHECK (password_encrypted IS NULL OR username IS NOT NULL),
            CONSTRAINT ck_company_email_settings_test CHECK (
                (last_test_at IS NULL) = (last_test_ok IS NULL)
                AND (last_test_ok IS NOT FALSE OR last_test_error IS NOT NULL)
            )
        )
    """)


def downgrade() -> None:
    stored = op.get_bind().execute(text("SELECT count(*) FROM company_email_settings")).scalar()
    if stored:
        raise RuntimeError(
            f"Hay {stored} configuraciones de correo de empresas; la migración 0128 no las borra. "
            "Respáldalas antes de revertir."
        )
    op.execute("DROP TABLE company_email_settings")
