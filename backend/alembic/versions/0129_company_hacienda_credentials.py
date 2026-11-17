"""Credenciales de Hacienda de cada empresa.

Revision ID: 0129
Revises: 0128

Bloque V3d del área de Ventas. Cada empresa guarda la contraseña de la API de Hacienda, la
contraseña de su llave privada y su certificado ``{nit}.crt``, todo cifrado con AES-GCM (clave de
datos protegidos). El ERP los entrega al servicio DTE al registrar a la empresa. Nada secreto se
devuelve por la API; se guarda la huella del certificado, su NIT y el resultado de la última
prueba de conexión.
"""

from alembic import op
from sqlalchemy import text

revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE company_hacienda_credentials (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
            api_password_encrypted bytea NOT NULL,
            private_key_password_encrypted bytea NOT NULL,
            certificate_encrypted bytea NOT NULL,
            certificate_sha256 varchar(64) NOT NULL,
            certificate_nit varchar(14) NOT NULL,
            last_test_at timestamptz,
            last_test_ok boolean,
            last_test_error text,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_company_hacienda_credentials_nit
                CHECK (certificate_nit ~ '^([0-9]{9}|[0-9]{14})$'),
            CONSTRAINT ck_company_hacienda_credentials_sha
                CHECK (certificate_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_company_hacienda_credentials_test CHECK (
                (last_test_at IS NULL) = (last_test_ok IS NULL)
                AND (last_test_ok IS NOT FALSE OR last_test_error IS NOT NULL)
            )
        )
    """)


def downgrade() -> None:
    stored = (
        op.get_bind().execute(text("SELECT count(*) FROM company_hacienda_credentials")).scalar()
    )
    if stored:
        raise RuntimeError(
            f"Hay {stored} credenciales de Hacienda guardadas; la migración 0129 no las borra. "
            "Respáldalas antes de revertir."
        )
    op.execute("DROP TABLE company_hacienda_credentials")
