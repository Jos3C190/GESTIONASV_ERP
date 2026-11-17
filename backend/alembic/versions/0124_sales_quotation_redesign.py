"""Cotización rediseñada: documento fiscal, precios de lista, descuentos, impuestos y autorización.

Revision ID: 0124
Revises: 0123

Bloque V2d del área de Ventas. La cotización del bloque B06 se rehace en su lugar: estados
Borrador, Por autorizar, Emitida, Aceptada, Rechazada y Cancelada; ``confirmed_*`` pasa a
``issued_*``; cada línea guarda el precio de lista, el descuento, los montos fiscales, el costo
y el margen del momento; la cotización guarda los totales del motor fiscal.

Para no perder documentos, la migración se niega a correr (en ambos sentidos) si ya hay
cotizaciones guardadas.
"""

from alembic import op
from sqlalchemy import text

revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sales_discounts:authorize", "Autorizar descuentos fuera de tope y ventas bajo costo"),
    ("sales_prices:override", "Cambiar el precio de lista en una cotización"),
)
_STATUSES = "('draft','pending_authorization','issued','accepted','rejected','cancelled')"


def _refuse_if_quotations(direction: str) -> None:
    stored = op.get_bind().execute(text("SELECT count(*) FROM sales_quotations")).scalar()
    if stored:
        raise RuntimeError(
            f"Hay {stored} cotizaciones guardadas; la migración 0124 no las convierte "
            f"({direction}). Respáldalas y elimínalas, o conviértelas a mano, antes de seguir."
        )


def upgrade() -> None:
    _refuse_if_quotations("upgrade")
    op.execute("""
        ALTER TABLE sales_quotations
            DROP CONSTRAINT ck_sales_quotations_status,
            DROP CONSTRAINT ck_sales_quotations_totals,
            DROP CONSTRAINT ck_sales_quotations_confirmation
    """)
    op.execute("ALTER TABLE sales_quotations RENAME COLUMN confirmed_at TO issued_at")
    op.execute("ALTER TABLE sales_quotations RENAME COLUMN confirmed_by_id TO issued_by_id")
    op.execute(
        "ALTER TABLE sales_quotations RENAME CONSTRAINT fk_sales_quotations_confirmer_company "
        "TO fk_sales_quotations_issuer_company"
    )
    op.execute(f"""
        ALTER TABLE sales_quotations
            ALTER COLUMN status TYPE varchar(24),
            ADD COLUMN document_type varchar(2) NOT NULL,
            ADD COLUMN price_list_id uuid,
            ADD COLUMN prices_include_vat boolean NOT NULL,
            ADD COLUMN global_discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            ADD COLUMN total_not_subject numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN total_exempt numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN total_taxed numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN subtotal_sales numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN total_discount numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN vat numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN vat_perceived numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN vat_withheld numeric(18, 2) NOT NULL DEFAULT 0,
            ADD COLUMN total_in_words varchar(400) NOT NULL DEFAULT 'CERO 00/100 DÓLARES',
            ADD COLUMN requires_authorization boolean NOT NULL DEFAULT false,
            ADD COLUMN authorization_reasons varchar(40)[] NOT NULL DEFAULT '{{}}',
            ADD COLUMN authorized_by_id uuid,
            ADD COLUMN authorized_at timestamptz,
            ADD COLUMN authorization_note text,
            ADD COLUMN customer_response_by_id uuid,
            ADD COLUMN customer_response_at timestamptz,
            ADD COLUMN rejection_reason text,
            ADD CONSTRAINT fk_sales_quotations_price_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_sales_quotations_authorizer_company
                FOREIGN KEY (authorized_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_sales_quotations_responder_company
                FOREIGN KEY (customer_response_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_quotations_status CHECK (status IN {_STATUSES}),
            ADD CONSTRAINT ck_sales_quotations_document CHECK (document_type IN ('01','03')),
            ADD CONSTRAINT ck_sales_quotations_global_discount
                CHECK (global_discount_percent >= 0 AND global_discount_percent <= 100),
            ADD CONSTRAINT ck_sales_quotations_totals CHECK (
                total_not_subject >= 0 AND total_exempt >= 0 AND total_taxed >= 0
                AND subtotal_sales >= 0 AND total_discount >= 0 AND subtotal >= 0
                AND vat >= 0 AND vat_perceived >= 0 AND vat_withheld >= 0 AND total >= 0
            ),
            ADD CONSTRAINT ck_sales_quotations_issue CHECK (
                (issued_at IS NULL) = (issued_by_id IS NULL)
                AND (status NOT IN ('issued','accepted','rejected') OR issued_at IS NOT NULL)
                AND (status NOT IN ('draft','pending_authorization') OR issued_at IS NULL)
            ),
            ADD CONSTRAINT ck_sales_quotations_authorization CHECK (
                (authorized_at IS NULL) = (authorized_by_id IS NULL)
            ),
            ADD CONSTRAINT ck_sales_quotations_response CHECK (
                (customer_response_at IS NULL) = (customer_response_by_id IS NULL)
                AND (status IN ('accepted','rejected')) = (customer_response_at IS NOT NULL)
                AND (status = 'rejected') = (rejection_reason IS NOT NULL)
            )
    """)
    op.execute("""
        ALTER TABLE sales_quotation_lines
            DROP CONSTRAINT ck_sales_quotation_lines_amounts,
            ALTER COLUMN unit_price TYPE numeric(19, 8),
            ALTER COLUMN line_total TYPE numeric(19, 8),
            ADD COLUMN price_list_id uuid,
            ADD COLUMN list_price numeric(19, 8),
            ADD COLUMN price_overridden boolean NOT NULL DEFAULT false,
            ADD COLUMN discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            ADD COLUMN suggested_discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            ADD COLUMN suggested_discount_source varchar(16) NOT NULL DEFAULT 'none',
            ADD COLUMN tax_treatment varchar(16) NOT NULL,
            ADD COLUMN item_type varchar(1) NOT NULL,
            ADD COLUMN document_unit_price numeric(19, 8) NOT NULL,
            ADD COLUMN discount_amount numeric(19, 8) NOT NULL DEFAULT 0,
            ADD COLUMN not_subject numeric(19, 8) NOT NULL DEFAULT 0,
            ADD COLUMN exempt numeric(19, 8) NOT NULL DEFAULT 0,
            ADD COLUMN taxed numeric(19, 8) NOT NULL DEFAULT 0,
            ADD COLUMN vat_item numeric(19, 8),
            ADD COLUMN cost numeric(19, 8),
            ADD COLUMN margin_percent numeric(7, 2),
            ADD COLUMN authorization_reasons varchar(40)[] NOT NULL DEFAULT '{}',
            ADD CONSTRAINT fk_sales_quotation_lines_price_list
                FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_quotation_lines_amounts CHECK (
                unit_price >= 0 AND line_total >= 0 AND document_unit_price >= 0
                AND discount_amount >= 0 AND not_subject >= 0 AND exempt >= 0 AND taxed >= 0
                AND (list_price IS NULL OR list_price >= 0)
                AND (cost IS NULL OR cost >= 0)
            ),
            ADD CONSTRAINT ck_sales_quotation_lines_discounts CHECK (
                discount_percent >= 0 AND discount_percent <= 100
                AND suggested_discount_percent >= 0 AND suggested_discount_percent <= 100
                AND suggested_discount_source IN ('none','customer','volume')
            ),
            ADD CONSTRAINT ck_sales_quotation_lines_tax CHECK (
                tax_treatment IN ('taxed','exempt','not_subject') AND item_type IN ('1','2','3')
            ),
            ADD CONSTRAINT ck_sales_quotation_lines_price_source CHECK (
                price_overridden OR list_price IS NOT NULL
            )
    """)
    op.execute("""
        CREATE TABLE sales_settings (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE RESTRICT,
            quotation_validity_days integer NOT NULL DEFAULT 15,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_sales_settings_validity
                CHECK (quotation_validity_days BETWEEN 1 AND 365)
        )
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'sales', now())
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
    _refuse_if_quotations("downgrade")
    settings = op.get_bind().execute(text("SELECT count(*) FROM sales_settings")).scalar()
    if settings:
        raise RuntimeError(
            f"Hay {settings} configuraciones de ventas que se perderían; "
            "elimínalas antes de revertir la migración 0124."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("DROP TABLE sales_settings")
    op.execute("""
        ALTER TABLE sales_quotation_lines
            DROP CONSTRAINT ck_sales_quotation_lines_amounts,
            DROP CONSTRAINT ck_sales_quotation_lines_discounts,
            DROP CONSTRAINT ck_sales_quotation_lines_tax,
            DROP CONSTRAINT ck_sales_quotation_lines_price_source,
            DROP CONSTRAINT fk_sales_quotation_lines_price_list,
            DROP COLUMN price_list_id,
            DROP COLUMN list_price,
            DROP COLUMN price_overridden,
            DROP COLUMN discount_percent,
            DROP COLUMN suggested_discount_percent,
            DROP COLUMN suggested_discount_source,
            DROP COLUMN tax_treatment,
            DROP COLUMN item_type,
            DROP COLUMN document_unit_price,
            DROP COLUMN discount_amount,
            DROP COLUMN not_subject,
            DROP COLUMN exempt,
            DROP COLUMN taxed,
            DROP COLUMN vat_item,
            DROP COLUMN cost,
            DROP COLUMN margin_percent,
            DROP COLUMN authorization_reasons,
            ALTER COLUMN unit_price TYPE numeric(18, 6),
            ALTER COLUMN line_total TYPE numeric(18, 2),
            ADD CONSTRAINT ck_sales_quotation_lines_amounts
                CHECK (unit_price >= 0 AND line_total >= 0)
    """)
    op.execute("""
        ALTER TABLE sales_quotations
            DROP CONSTRAINT ck_sales_quotations_status,
            DROP CONSTRAINT ck_sales_quotations_document,
            DROP CONSTRAINT ck_sales_quotations_global_discount,
            DROP CONSTRAINT ck_sales_quotations_totals,
            DROP CONSTRAINT ck_sales_quotations_issue,
            DROP CONSTRAINT ck_sales_quotations_authorization,
            DROP CONSTRAINT ck_sales_quotations_response,
            DROP CONSTRAINT fk_sales_quotations_price_list,
            DROP CONSTRAINT fk_sales_quotations_authorizer_company,
            DROP CONSTRAINT fk_sales_quotations_responder_company,
            DROP COLUMN document_type,
            DROP COLUMN price_list_id,
            DROP COLUMN prices_include_vat,
            DROP COLUMN global_discount_percent,
            DROP COLUMN total_not_subject,
            DROP COLUMN total_exempt,
            DROP COLUMN total_taxed,
            DROP COLUMN subtotal_sales,
            DROP COLUMN total_discount,
            DROP COLUMN vat,
            DROP COLUMN vat_perceived,
            DROP COLUMN vat_withheld,
            DROP COLUMN total_in_words,
            DROP COLUMN requires_authorization,
            DROP COLUMN authorization_reasons,
            DROP COLUMN authorized_by_id,
            DROP COLUMN authorized_at,
            DROP COLUMN authorization_note,
            DROP COLUMN customer_response_by_id,
            DROP COLUMN customer_response_at,
            DROP COLUMN rejection_reason,
            ALTER COLUMN status TYPE varchar(16)
    """)
    op.execute(
        "ALTER TABLE sales_quotations RENAME CONSTRAINT fk_sales_quotations_issuer_company "
        "TO fk_sales_quotations_confirmer_company"
    )
    op.execute("ALTER TABLE sales_quotations RENAME COLUMN issued_by_id TO confirmed_by_id")
    op.execute("ALTER TABLE sales_quotations RENAME COLUMN issued_at TO confirmed_at")
    op.execute("""
        ALTER TABLE sales_quotations
            ADD CONSTRAINT ck_sales_quotations_status
                CHECK (status IN ('draft','confirmed','cancelled')),
            ADD CONSTRAINT ck_sales_quotations_totals CHECK (subtotal >= 0 AND total = subtotal),
            ADD CONSTRAINT ck_sales_quotations_confirmation CHECK (
                (confirmed_at IS NULL) = (confirmed_by_id IS NULL)
                AND (status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL))
                AND (status <> 'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))
            )
    """)
