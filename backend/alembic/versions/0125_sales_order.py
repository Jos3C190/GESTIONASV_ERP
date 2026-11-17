"""Pedido de venta: la venta B06 pasa a pedido con impuestos, entrega y reserva comercial.

Revision ID: 0125
Revises: 0124

Bloque V2e del área de Ventas. Las tablas ``sales`` y ``sales_lines`` se conservan porque las
entregas y devoluciones ya apuntan a ellas; en la interfaz el documento se llama «Pedido».

- La cotización de origen pasa a ser opcional: el pedido puede armarse directo.
- Estados: Borrador, Por autorizar, Confirmado y Cancelado.
- La cabecera y las líneas guardan los mismos datos fiscales y de autorización que la
  cotización, más la fecha comprometida, el lugar de entrega y la condición de pago.

Para no perder documentos, la migración se niega a correr (en ambos sentidos) si ya hay
ventas, entregas o devoluciones guardadas.
"""

from alembic import op
from sqlalchemy import text

revision = "0125"
down_revision = "0124"
branch_labels = None
depends_on = None

_STATUSES = "('draft','pending_authorization','confirmed','cancelled')"
_GUARDED = ("sales", "sales_deliveries", "sales_returns")


def _refuse_if_documents(direction: str) -> None:
    bind = op.get_bind()
    counts = {
        table: bind.execute(text(f"SELECT count(*) FROM {table}")).scalar() for table in _GUARDED
    }
    if any(counts.values()):
        detail = ", ".join(f"{table}: {count}" for table, count in counts.items() if count)
        raise RuntimeError(
            f"Hay ventas, entregas o devoluciones guardadas ({detail}); la migración 0125 no las "
            f"convierte ({direction}). Respáldalas y elimínalas antes de seguir."
        )


def _line_guards(width: int) -> None:
    """Los triggers que congelan líneas leen el estado del documento en una variable."""

    for function, table, key, message in (
        ("guard_sales_lines_draft", "sales_quotations", "quotation_id", "sales quotation lines"),
        ("guard_sales_order_lines_draft", "sales", "sale_id", "sales lines"),
    ):
        op.execute(f"""
            CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE doc_status varchar({width}); doc_company uuid; doc_id uuid;
            BEGIN
                IF TG_OP='DELETE' THEN doc_company:=OLD.company_id; doc_id:=OLD.{key};
                ELSE doc_company:=NEW.company_id; doc_id:=NEW.{key}; END IF;
                SELECT status INTO doc_status FROM {table}
                  WHERE company_id=doc_company AND id=doc_id FOR KEY SHARE;
                IF doc_status IS DISTINCT FROM 'draft' THEN
                    RAISE EXCEPTION '{message} are immutable outside draft';
                END IF;
                IF TG_OP='DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END; $$
        """)


def upgrade() -> None:
    _refuse_if_documents("upgrade")
    op.execute("""
        ALTER TABLE sales_customer_delivery_addresses
            ADD CONSTRAINT uq_sales_customer_delivery_addresses_owner
                UNIQUE (company_id, customer_id, id)
    """)
    op.execute(f"""
        ALTER TABLE sales
            DROP CONSTRAINT ck_sales_status,
            DROP CONSTRAINT ck_sales_totals_version,
            DROP CONSTRAINT ck_sales_confirmation,
            ALTER COLUMN quotation_id DROP NOT NULL,
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
            ADD COLUMN promised_date date NOT NULL,
            ADD COLUMN delivery_mode varchar(16) NOT NULL,
            ADD COLUMN delivery_address_id uuid,
            ADD COLUMN delivery_address_text varchar(400),
            ADD COLUMN payment_terms varchar(8) NOT NULL,
            ADD COLUMN credit_days integer NOT NULL DEFAULT 0,
            ADD CONSTRAINT fk_sales_price_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_sales_authorizer_company FOREIGN KEY (authorized_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_sales_delivery_address
                FOREIGN KEY (company_id, customer_id, delivery_address_id)
                REFERENCES sales_customer_delivery_addresses (company_id, customer_id, id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_status CHECK (status IN {_STATUSES}),
            ADD CONSTRAINT ck_sales_document CHECK (document_type IN ('01','03')),
            ADD CONSTRAINT ck_sales_global_discount
                CHECK (global_discount_percent >= 0 AND global_discount_percent <= 100),
            ADD CONSTRAINT ck_sales_totals_version CHECK (
                version >= 1
                AND total_not_subject >= 0 AND total_exempt >= 0 AND total_taxed >= 0
                AND subtotal_sales >= 0 AND total_discount >= 0 AND subtotal >= 0
                AND vat >= 0 AND vat_perceived >= 0 AND vat_withheld >= 0 AND total >= 0
            ),
            ADD CONSTRAINT ck_sales_confirmation CHECK (
                (confirmed_at IS NULL) = (confirmed_by_id IS NULL)
                AND (status <> 'confirmed' OR confirmed_at IS NOT NULL)
                AND (status NOT IN ('draft','pending_authorization') OR confirmed_at IS NULL)
            ),
            ADD CONSTRAINT ck_sales_authorization CHECK (
                (authorized_at IS NULL) = (authorized_by_id IS NULL)
            ),
            ADD CONSTRAINT ck_sales_delivery CHECK (
                delivery_mode IN ('pickup','delivery')
                AND (delivery_mode = 'delivery') = (delivery_address_id IS NOT NULL)
                AND (delivery_address_id IS NULL) = (delivery_address_text IS NULL)
            ),
            ADD CONSTRAINT ck_sales_payment CHECK (
                payment_terms IN ('cash','credit')
                AND credit_days BETWEEN 0 AND 365
                AND (payment_terms = 'credit' OR credit_days = 0)
            )
    """)
    op.execute("""
        ALTER TABLE sales_lines
            DROP CONSTRAINT ck_sales_lines_amounts,
            ALTER COLUMN source_quotation_line_id DROP NOT NULL,
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
            ADD CONSTRAINT fk_sales_lines_price_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_lines_amounts CHECK (
                unit_price >= 0 AND line_total >= 0 AND document_unit_price >= 0
                AND discount_amount >= 0 AND not_subject >= 0 AND exempt >= 0 AND taxed >= 0
                AND (list_price IS NULL OR list_price >= 0)
                AND (cost IS NULL OR cost >= 0)
            ),
            ADD CONSTRAINT ck_sales_lines_discounts CHECK (
                discount_percent >= 0 AND discount_percent <= 100
                AND suggested_discount_percent >= 0 AND suggested_discount_percent <= 100
                AND suggested_discount_source IN ('none','customer','volume')
            ),
            ADD CONSTRAINT ck_sales_lines_tax CHECK (
                tax_treatment IN ('taxed','exempt','not_subject') AND item_type IN ('1','2','3')
            ),
            ADD CONSTRAINT ck_sales_lines_price_source CHECK (
                price_overridden OR list_price IS NOT NULL
            )
    """)
    _line_guards(24)
    op.execute("""
        CREATE INDEX ix_sales_lines_reservation
            ON sales_lines (company_id, inventory_item_id, sale_id)
    """)


def downgrade() -> None:
    _refuse_if_documents("downgrade")
    op.execute("DROP INDEX ix_sales_lines_reservation")
    _line_guards(16)
    op.execute("""
        ALTER TABLE sales_lines
            DROP CONSTRAINT ck_sales_lines_amounts,
            DROP CONSTRAINT ck_sales_lines_discounts,
            DROP CONSTRAINT ck_sales_lines_tax,
            DROP CONSTRAINT ck_sales_lines_price_source,
            DROP CONSTRAINT fk_sales_lines_price_list,
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
            ALTER COLUMN source_quotation_line_id SET NOT NULL,
            ADD CONSTRAINT ck_sales_lines_amounts CHECK (unit_price >= 0 AND line_total >= 0)
    """)
    op.execute("""
        ALTER TABLE sales
            DROP CONSTRAINT ck_sales_status,
            DROP CONSTRAINT ck_sales_document,
            DROP CONSTRAINT ck_sales_global_discount,
            DROP CONSTRAINT ck_sales_totals_version,
            DROP CONSTRAINT ck_sales_confirmation,
            DROP CONSTRAINT ck_sales_authorization,
            DROP CONSTRAINT ck_sales_delivery,
            DROP CONSTRAINT ck_sales_payment,
            DROP CONSTRAINT fk_sales_price_list,
            DROP CONSTRAINT fk_sales_authorizer_company,
            DROP CONSTRAINT fk_sales_delivery_address,
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
            DROP COLUMN promised_date,
            DROP COLUMN delivery_mode,
            DROP COLUMN delivery_address_id,
            DROP COLUMN delivery_address_text,
            DROP COLUMN payment_terms,
            DROP COLUMN credit_days,
            ALTER COLUMN status TYPE varchar(16),
            ALTER COLUMN quotation_id SET NOT NULL,
            ADD CONSTRAINT ck_sales_status CHECK (status IN ('draft','confirmed','cancelled')),
            ADD CONSTRAINT ck_sales_totals_version
                CHECK (version >= 1 AND subtotal >= 0 AND total = subtotal),
            ADD CONSTRAINT ck_sales_confirmation CHECK (
                (confirmed_at IS NULL) = (confirmed_by_id IS NULL)
                AND (status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL))
                AND (status <> 'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))
            )
    """)
    op.execute("""
        ALTER TABLE sales_customer_delivery_addresses
            DROP CONSTRAINT uq_sales_customer_delivery_addresses_owner
    """)
