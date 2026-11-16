"""Base fiscal del emisor: catálogos de Hacienda, perfil de emisor, establecimientos,
puntos de venta y documentos habilitados por empresa.

Revision ID: 0118
Revises: 0117

Los catálogos de Hacienda (versión 1.1, julio de 2026) son globales; los demás datos son
de cada empresa, que es la unidad de aislamiento del emisor. La geografía existente recibe
el código de Hacienda de cada departamento, municipio y distrito: los códigos de municipio
y distrito solo son únicos dentro de su departamento.

El downgrade se niega si alguna empresa ya configuró su emisor.
"""

import sqlalchemy as sa
from alembic import op
from app.infrastructure.catalogs.hacienda_dte import CATALOG_VERSION, CATALOGS
from app.infrastructure.catalogs.hacienda_geography import (
    DEPARTMENT_CODES,
    DISTRICT_CODES,
    MUNICIPALITY_CODES,
)
from sqlalchemy import text

revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("fiscal_settings:read", "Consultar la configuración fiscal del emisor"),
    ("fiscal_settings:manage", "Configurar el emisor, establecimientos y documentos"),
)
DOCUMENT_TYPES = ("01", "03", "04", "05", "06", "07", "08", "09", "11", "14", "15", "17", "18")
_DOCUMENT_TYPES_SQL = ",".join(f"'{code}'" for code in DOCUMENT_TYPES)
_GEOGRAPHY_TABLES = ("districts", "municipalities", "geographic_departments")
_ISSUER_TABLES = (
    "company_dte_document_types",
    "fiscal_points_of_sale",
    "fiscal_establishments",
    "company_economic_activities",
    "company_fiscal_profiles",
)


def upgrade() -> None:
    _create_catalog_items()
    _add_geography_codes()
    _create_issuer_tables()
    _grant_permissions()


def _create_catalog_items() -> None:
    op.execute("""
        CREATE TABLE hacienda_catalog_items (
            catalog_code varchar(7) NOT NULL,
            group_code varchar(16) NOT NULL DEFAULT '',
            code varchar(16) NOT NULL,
            name text NOT NULL,
            sort_order integer NOT NULL,
            catalog_version varchar(8) NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            PRIMARY KEY (catalog_code, group_code, code),
            CONSTRAINT ck_hacienda_catalog_items_catalog CHECK (catalog_code ~ '^CAT-[0-9]{3}$'),
            CONSTRAINT ck_hacienda_catalog_items_name CHECK (char_length(btrim(name)) > 0)
        )
    """)
    table = sa.table(
        "hacienda_catalog_items",
        sa.column("catalog_code", sa.String),
        sa.column("group_code", sa.String),
        sa.column("code", sa.String),
        sa.column("name", sa.Text),
        sa.column("sort_order", sa.Integer),
        sa.column("catalog_version", sa.String),
    )
    rows = [
        {
            "catalog_code": catalog,
            "group_code": group,
            "code": code,
            "name": name,
            "sort_order": position,
            "catalog_version": CATALOG_VERSION,
        }
        for catalog, (_, items) in CATALOGS.items()
        for position, (group, code, name) in enumerate(items, start=1)
    ]
    op.bulk_insert(table, rows)


def _add_geography_codes() -> None:
    for table in _GEOGRAPHY_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN hacienda_code varchar(2)")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_hacienda_code "
            "CHECK (hacienda_code IS NULL OR hacienda_code ~ '^[0-9]{2}$')"
        )
    connection = op.get_bind()
    for department, code in DEPARTMENT_CODES.items():
        connection.execute(
            text("UPDATE geographic_departments SET hacienda_code = :code WHERE name = :name"),
            {"code": code, "name": department},
        )
    for (department, municipality), code in MUNICIPALITY_CODES.items():
        connection.execute(
            text("""
                UPDATE municipalities m SET hacienda_code = :code
                  FROM geographic_departments d
                 WHERE m.department_id = d.id AND d.name = :department AND m.name = :name
            """),
            {"code": code, "department": department, "name": municipality},
        )
    for (department, municipality, district), code in DISTRICT_CODES.items():
        connection.execute(
            text("""
                UPDATE districts x SET hacienda_code = :code
                  FROM municipalities m JOIN geographic_departments d ON d.id = m.department_id
                 WHERE x.municipality_id = m.id AND d.name = :department
                   AND m.name = :municipality AND x.name = :name
            """),
            {
                "code": code,
                "department": department,
                "municipality": municipality,
                "name": district,
            },
        )
    op.execute(
        "CREATE UNIQUE INDEX uq_geographic_departments_hacienda_code "
        "ON geographic_departments (hacienda_code) WHERE hacienda_code IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_municipalities_department_hacienda_code "
        "ON municipalities (department_id, hacienda_code) WHERE hacienda_code IS NOT NULL"
    )


def _create_issuer_tables() -> None:
    op.execute("""
        CREATE TABLE company_fiscal_profiles (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
            taxpayer_category varchar(16) NOT NULL DEFAULT 'other',
            person_type varchar(1) NOT NULL DEFAULT '2',
            operating_mode varchar(16) NOT NULL DEFAULT 'simulated',
            dte_email varchar(100),
            dte_phone varchar(30),
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_company_fiscal_profiles_category
                CHECK (taxpayer_category IN ('large','medium','other')),
            CONSTRAINT ck_company_fiscal_profiles_person_type CHECK (person_type IN ('1','2')),
            CONSTRAINT ck_company_fiscal_profiles_mode
                CHECK (operating_mode IN ('simulated','test','production')),
            CONSTRAINT ck_company_fiscal_profiles_email
                CHECK (dte_email IS NULL OR char_length(dte_email) >= 6),
            CONSTRAINT ck_company_fiscal_profiles_phone
                CHECK (dte_phone IS NULL OR char_length(dte_phone) >= 8)
        )
    """)
    op.execute("""
        CREATE TABLE company_economic_activities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            activity_code varchar(6) NOT NULL,
            is_primary boolean NOT NULL DEFAULT false,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_company_economic_activities_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_company_economic_activities_code UNIQUE (company_id, activity_code),
            CONSTRAINT ck_company_economic_activities_code CHECK (activity_code ~ '^[0-9]{5,6}$')
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_company_economic_activities_primary "
        "ON company_economic_activities (company_id) WHERE is_primary"
    )
    op.execute("""
        CREATE TABLE fiscal_establishments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            establishment_type varchar(2) NOT NULL,
            code varchar(4) NOT NULL,
            activity_id uuid,
            is_active boolean NOT NULL DEFAULT true,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_fiscal_establishments_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_fiscal_establishments_code UNIQUE (company_id, code),
            CONSTRAINT uq_fiscal_establishments_branch UNIQUE (company_id, branch_id),
            CONSTRAINT fk_fiscal_establishments_branch_company FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_fiscal_establishments_activity FOREIGN KEY (company_id, activity_id)
                REFERENCES company_economic_activities (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_fiscal_establishments_type
                CHECK (establishment_type IN ('01','02','04','07')),
            CONSTRAINT ck_fiscal_establishments_code CHECK (code ~ '^[MSBP][0-9]{3}$'),
            CONSTRAINT ck_fiscal_establishments_code_matches_type CHECK (
                (establishment_type = '02' AND left(code, 1) = 'M')
                OR (establishment_type = '01' AND left(code, 1) = 'S')
                OR (establishment_type = '04' AND left(code, 1) = 'B')
                OR (establishment_type = '07' AND left(code, 1) = 'P')
            )
        )
    """)
    op.execute("""
        CREATE TABLE fiscal_points_of_sale (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            establishment_id uuid NOT NULL,
            code varchar(4) NOT NULL,
            name varchar(120) NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_fiscal_points_of_sale_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_fiscal_points_of_sale_code UNIQUE (establishment_id, code),
            CONSTRAINT fk_fiscal_points_of_sale_establishment
                FOREIGN KEY (company_id, establishment_id)
                REFERENCES fiscal_establishments (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_fiscal_points_of_sale_code CHECK (code ~ '^P[0-9]{3}$'),
            CONSTRAINT ck_fiscal_points_of_sale_name CHECK (char_length(btrim(name)) >= 2)
        )
    """)
    op.execute(f"""
        CREATE TABLE company_dte_document_types (
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_type varchar(2) NOT NULL,
            is_enabled boolean NOT NULL DEFAULT false,
            certification_status varchar(16) NOT NULL DEFAULT 'pending',
            certified_at timestamptz,
            notes text,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (company_id, document_type),
            CONSTRAINT ck_company_dte_document_types_type
                CHECK (document_type IN ({_DOCUMENT_TYPES_SQL})),
            CONSTRAINT ck_company_dte_document_types_status
                CHECK (certification_status IN ('pending','in_progress','approved')),
            CONSTRAINT ck_company_dte_document_types_certified
                CHECK ((certification_status = 'approved') = (certified_at IS NOT NULL))
        )
    """)


def _grant_permissions() -> None:
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
    configured = (
        op.get_bind()
        .execute(
            text("""
                SELECT (SELECT count(*) FROM company_fiscal_profiles)
                     + (SELECT count(*) FROM company_economic_activities)
                     + (SELECT count(*) FROM fiscal_establishments)
                     + (SELECT count(*) FROM company_dte_document_types)
            """)
        )
        .scalar()
    )
    if configured:
        raise RuntimeError(
            f"Hay {configured} registros de configuración fiscal del emisor que se perderían; "
            "elimínalos antes de revertir la migración 0118."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    for table in _ISSUER_TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP INDEX uq_municipalities_department_hacienda_code")
    op.execute("DROP INDEX uq_geographic_departments_hacienda_code")
    for table in _GEOGRAPHY_TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN hacienda_code")
    op.execute("DROP TABLE hacienda_catalog_items")
