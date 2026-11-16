"""Clientes con datos fiscales, condiciones comerciales y direcciones de entrega.

Revision ID: 0119
Revises: 0118

``sales_customers`` se amplía (no se reemplaza) para conservar las llaves de cotizaciones y
ventas. La base solo garantiza formatos y combinaciones; los requisitos completos para que
un cliente reciba crédito fiscal los calcula el dominio, porque un contribuyente puede
registrarse incompleto y completarse después.

El downgrade se niega si hay datos que se perderían.
"""

from alembic import op
from sqlalchemy import text

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    "customer_type",
    "taxpayer_category",
    "is_withholding_agent",
    "person_type",
    "commercial_name",
    "document_type",
    "document_number",
    "nrc",
    "activity_code",
    "department_id",
    "municipality_id",
    "district_id",
    "address_line",
    "country_code",
    "credit_days",
    "credit_limit",
    "seller_employee_id",
    "is_generic",
    "branch_id",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales_customers
            ADD COLUMN customer_type varchar(16) NOT NULL DEFAULT 'final_consumer',
            ADD COLUMN taxpayer_category varchar(16),
            ADD COLUMN is_withholding_agent boolean NOT NULL DEFAULT false,
            ADD COLUMN person_type varchar(1) NOT NULL DEFAULT '1',
            ADD COLUMN commercial_name varchar(200),
            ADD COLUMN document_type varchar(2),
            ADD COLUMN document_number varchar(20),
            ADD COLUMN nrc varchar(8),
            ADD COLUMN activity_code varchar(6),
            ADD COLUMN department_id uuid REFERENCES geographic_departments (id) ON DELETE RESTRICT,
            ADD COLUMN municipality_id uuid REFERENCES municipalities (id) ON DELETE RESTRICT,
            ADD COLUMN district_id uuid REFERENCES districts (id) ON DELETE RESTRICT,
            ADD COLUMN address_line varchar(200),
            ADD COLUMN country_code varchar(4),
            ADD COLUMN credit_days integer NOT NULL DEFAULT 0,
            ADD COLUMN credit_limit numeric(18, 2),
            ADD COLUMN seller_employee_id uuid REFERENCES employees (id) ON DELETE SET NULL,
            ADD COLUMN is_generic boolean NOT NULL DEFAULT false,
            ADD COLUMN branch_id uuid,
            ADD CONSTRAINT fk_sales_customers_generic_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_customers_type
                CHECK (customer_type IN ('final_consumer','taxpayer','foreign')),
            ADD CONSTRAINT ck_sales_customers_taxpayer_category CHECK (
                (customer_type = 'taxpayer' AND taxpayer_category IS NOT NULL
                 AND taxpayer_category IN ('large','medium','other'))
                OR (customer_type <> 'taxpayer' AND taxpayer_category IS NULL)
            ),
            ADD CONSTRAINT ck_sales_customers_person_type CHECK (person_type IN ('1','2')),
            ADD CONSTRAINT ck_sales_customers_document CHECK (
                (document_type IS NULL) = (document_number IS NULL)
                AND (document_type IS NULL OR document_type IN ('36','13','02','03','37'))
                AND (document_number IS NULL OR char_length(btrim(document_number)) >= 3)
            ),
            ADD CONSTRAINT ck_sales_customers_nrc CHECK (nrc IS NULL OR nrc ~ '^[0-9]{2,8}$'),
            ADD CONSTRAINT ck_sales_customers_activity
                CHECK (activity_code IS NULL OR activity_code ~ '^[0-9]{5,6}$'),
            ADD CONSTRAINT ck_sales_customers_geography CHECK (
                (department_id IS NULL) = (municipality_id IS NULL)
                AND (municipality_id IS NULL) = (district_id IS NULL)
            ),
            ADD CONSTRAINT ck_sales_customers_foreign CHECK (
                (customer_type = 'foreign') = (country_code IS NOT NULL)
                AND (customer_type <> 'foreign' OR department_id IS NULL)
            ),
            ADD CONSTRAINT ck_sales_customers_credit CHECK (
                credit_days BETWEEN 0 AND 365 AND (credit_limit IS NULL OR credit_limit >= 0)
            ),
            ADD CONSTRAINT ck_sales_customers_generic CHECK (
                is_generic = (branch_id IS NOT NULL)
                AND (NOT is_generic OR (customer_type = 'final_consumer'
                     AND document_type IS NULL AND nrc IS NULL))
            )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_customers_generic_branch "
        "ON sales_customers (company_id, branch_id) WHERE is_generic"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_customers_document "
        "ON sales_customers (company_id, document_type, document_number) "
        "WHERE document_number IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_customers_nrc ON sales_customers (company_id, nrc) "
        "WHERE nrc IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_sales_customers_company_type "
        "ON sales_customers (company_id, customer_type, is_active)"
    )
    op.execute("""
        CREATE TABLE sales_customer_delivery_addresses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            label varchar(80) NOT NULL,
            address_line varchar(200) NOT NULL,
            department_id uuid REFERENCES geographic_departments (id) ON DELETE RESTRICT,
            municipality_id uuid REFERENCES municipalities (id) ON DELETE RESTRICT,
            district_id uuid REFERENCES districts (id) ON DELETE RESTRICT,
            latitude numeric(9, 6),
            longitude numeric(9, 6),
            contact_name varchar(120),
            phone varchar(30),
            is_default boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_customer_delivery_addresses_customer
                FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE CASCADE,
            CONSTRAINT ck_sales_customer_delivery_addresses_label
                CHECK (char_length(btrim(label)) >= 2),
            CONSTRAINT ck_sales_customer_delivery_addresses_line
                CHECK (char_length(btrim(address_line)) >= 3),
            CONSTRAINT ck_sales_customer_delivery_addresses_geography CHECK (
                (department_id IS NULL) = (municipality_id IS NULL)
                AND (municipality_id IS NULL) = (district_id IS NULL)
            ),
            CONSTRAINT ck_sales_customer_delivery_addresses_coordinates CHECK (
                (latitude IS NULL) = (longitude IS NULL)
                AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)
                AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)
            ),
            CONSTRAINT ck_sales_customer_delivery_addresses_default
                CHECK (NOT is_default OR is_active)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_customer_delivery_addresses_default "
        "ON sales_customer_delivery_addresses (customer_id) WHERE is_default"
    )
    op.execute(
        "CREATE INDEX ix_sales_customer_delivery_addresses_customer "
        "ON sales_customer_delivery_addresses (company_id, customer_id)"
    )


def downgrade() -> None:
    blocked = (
        op.get_bind()
        .execute(
            text("""
                SELECT (SELECT count(*) FROM sales_customer_delivery_addresses)
                     + (SELECT count(*) FROM sales_customers
                         WHERE is_generic OR customer_type <> 'final_consumer'
                            OR document_number IS NOT NULL OR nrc IS NOT NULL
                            OR address_line IS NOT NULL OR credit_limit IS NOT NULL)
            """)
        )
        .scalar()
    )
    if blocked:
        raise RuntimeError(
            f"Hay {blocked} clientes o direcciones con datos fiscales que se perderían; "
            "elimínalos antes de revertir la migración 0119."
        )
    op.execute("DROP TABLE sales_customer_delivery_addresses")
    for index in (
        "ix_sales_customers_company_type",
        "uq_sales_customers_nrc",
        "uq_sales_customers_document",
        "uq_sales_customers_generic_branch",
    ):
        op.execute(f"DROP INDEX {index}")
    op.execute("ALTER TABLE sales_customers DROP CONSTRAINT fk_sales_customers_generic_branch")
    op.execute(
        "ALTER TABLE sales_customers "
        + ", ".join(f"DROP COLUMN {column}" for column in _NEW_COLUMNS)
    )
