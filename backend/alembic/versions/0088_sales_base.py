"""Add company-scoped customers, sales quotations and unfulfilled sales."""

from __future__ import annotations

from alembic import op

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_customers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            code varchar(40) NOT NULL,
            name varchar(200) NOT NULL,
            phone varchar(40),
            email varchar(320),
            is_active boolean NOT NULL DEFAULT true,
            created_by_id uuid NOT NULL,
            updated_by_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_customers_company_id UNIQUE(company_id,id),
            CONSTRAINT fk_sales_customers_created_by_company FOREIGN KEY(created_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_customers_updated_by_company FOREIGN KEY(updated_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT
        );
        CREATE UNIQUE INDEX uq_sales_customers_company_code
            ON sales_customers(company_id,lower(code));
        CREATE INDEX ix_sales_customers_company_active_name
            ON sales_customers(company_id,is_active,name);

        CREATE TABLE sales_quotations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            code varchar(48) NOT NULL,
            quotation_date date NOT NULL,
            valid_until date NOT NULL,
            currency varchar(3) NOT NULL DEFAULT 'USD',
            subtotal numeric(18,2) NOT NULL DEFAULT 0,
            total numeric(18,2) NOT NULL DEFAULT 0,
            status varchar(16) NOT NULL DEFAULT 'draft',
            version integer NOT NULL DEFAULT 1,
            notes text,
            created_by_id uuid NOT NULL,
            confirmed_by_id uuid,
            confirmed_at timestamptz,
            cancelled_by_id uuid,
            cancelled_at timestamptz,
            cancellation_reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_quotations_company_id UNIQUE(company_id,id),
            CONSTRAINT uq_sales_quotations_company_code UNIQUE(company_id,code),
            CONSTRAINT fk_sales_quotations_branch_company FOREIGN KEY(branch_id,company_id)
                REFERENCES branches(id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotations_customer_company FOREIGN KEY(company_id,customer_id)
                REFERENCES sales_customers(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotations_creator_company FOREIGN KEY(created_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotations_confirmer_company FOREIGN KEY(confirmed_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotations_canceller_company FOREIGN KEY(cancelled_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_quotations_currency_usd CHECK(currency='USD'),
            CONSTRAINT ck_sales_quotations_status CHECK(status IN ('draft','confirmed','cancelled')),
            CONSTRAINT ck_sales_quotations_dates_version CHECK(version>=1 AND valid_until>=quotation_date),
            CONSTRAINT ck_sales_quotations_totals CHECK(subtotal>=0 AND total=subtotal),
            CONSTRAINT ck_sales_quotations_confirmation CHECK(
                (confirmed_at IS NULL)=(confirmed_by_id IS NULL)
                AND (status<>'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL))
                AND (status<>'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))),
            CONSTRAINT ck_sales_quotations_cancellation CHECK(
                (status='cancelled')=(cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL))
        );
        CREATE INDEX ix_sales_quotations_company_branch_status_date
            ON sales_quotations(company_id,branch_id,status,quotation_date);
        CREATE INDEX ix_sales_quotations_company_customer
            ON sales_quotations(company_id,customer_id,quotation_date);

        CREATE TABLE sales_quotation_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            quotation_id uuid NOT NULL,
            line_number integer NOT NULL,
            product_id integer NOT NULL,
            variant_id uuid,
            inventory_item_id uuid NOT NULL,
            packaging_definition_id uuid,
            packaging_version integer,
            unit_id integer NOT NULL,
            base_unit_id integer NOT NULL,
            unit_factor numeric(18,6) NOT NULL,
            quantity numeric(18,6) NOT NULL,
            quantity_base numeric(18,6) NOT NULL,
            product_sku varchar(100) NOT NULL,
            product_name varchar(200) NOT NULL,
            unit_name varchar(120) NOT NULL,
            base_unit_name varchar(120) NOT NULL,
            unit_price numeric(18,6) NOT NULL,
            line_total numeric(18,2) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_quotation_lines_company_id UNIQUE(company_id,id),
            CONSTRAINT uq_sales_quotation_lines_number UNIQUE(company_id,quotation_id,line_number),
            CONSTRAINT fk_sales_quotation_lines_header_company FOREIGN KEY(company_id,quotation_id)
                REFERENCES sales_quotations(company_id,id) ON DELETE CASCADE,
            CONSTRAINT fk_sales_quotation_lines_product_company FOREIGN KEY(company_id,product_id)
                REFERENCES products(company_id,id_product) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotation_lines_variant_company FOREIGN KEY(company_id,product_id,variant_id)
                REFERENCES product_variants(company_id,product_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotation_lines_item_company FOREIGN KEY(company_id,inventory_item_id)
                REFERENCES inventory_items(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotation_lines_packaging FOREIGN KEY(company_id,inventory_item_id,packaging_definition_id)
                REFERENCES inventory_packaging_definitions(company_id,inventory_item_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotation_lines_unit_company FOREIGN KEY(company_id,unit_id)
                REFERENCES company_units(company_id,unit_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_quotation_lines_base_unit_company FOREIGN KEY(company_id,base_unit_id)
                REFERENCES company_units(company_id,unit_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_quotation_lines_quantities CHECK(line_number>0 AND quantity>0 AND quantity_base>0 AND unit_factor>0),
            CONSTRAINT ck_sales_quotation_lines_amounts CHECK(unit_price>=0 AND line_total>=0),
            CONSTRAINT ck_sales_quotation_lines_packaging_snapshot CHECK((packaging_definition_id IS NULL)=(packaging_version IS NULL))
        );

        CREATE TABLE sales (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            quotation_id uuid NOT NULL,
            code varchar(48) NOT NULL,
            currency varchar(3) NOT NULL DEFAULT 'USD',
            subtotal numeric(18,2) NOT NULL,
            total numeric(18,2) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'draft',
            version integer NOT NULL DEFAULT 1,
            notes text,
            created_by_id uuid NOT NULL,
            confirmed_by_id uuid,
            confirmed_at timestamptz,
            cancelled_by_id uuid,
            cancelled_at timestamptz,
            cancellation_reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_company_id UNIQUE(company_id,id),
            CONSTRAINT uq_sales_company_code UNIQUE(company_id,code),
            CONSTRAINT uq_sales_source_quotation UNIQUE(company_id,quotation_id),
            CONSTRAINT fk_sales_branch_company FOREIGN KEY(branch_id,company_id)
                REFERENCES branches(id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_customer_company FOREIGN KEY(company_id,customer_id)
                REFERENCES sales_customers(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_source_quotation_company FOREIGN KEY(company_id,quotation_id)
                REFERENCES sales_quotations(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_creator_company FOREIGN KEY(created_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_confirmer_company FOREIGN KEY(confirmed_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_canceller_company FOREIGN KEY(cancelled_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_currency_usd CHECK(currency='USD'),
            CONSTRAINT ck_sales_status CHECK(status IN ('draft','confirmed','cancelled')),
            CONSTRAINT ck_sales_totals_version CHECK(version>=1 AND subtotal>=0 AND total=subtotal),
            CONSTRAINT ck_sales_confirmation CHECK(
                (confirmed_at IS NULL)=(confirmed_by_id IS NULL)
                AND (status<>'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL))
                AND (status<>'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))),
            CONSTRAINT ck_sales_cancellation CHECK((status='cancelled')=(cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL))
        );
        CREATE INDEX ix_sales_company_branch_status_created
            ON sales(company_id,branch_id,status,created_at);

        CREATE TABLE sales_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            sale_id uuid NOT NULL,
            source_quotation_line_id uuid NOT NULL,
            line_number integer NOT NULL,
            product_id integer NOT NULL,
            variant_id uuid,
            inventory_item_id uuid NOT NULL,
            packaging_definition_id uuid,
            packaging_version integer,
            unit_id integer NOT NULL,
            base_unit_id integer NOT NULL,
            unit_factor numeric(18,6) NOT NULL,
            quantity numeric(18,6) NOT NULL,
            quantity_base numeric(18,6) NOT NULL,
            product_sku varchar(100) NOT NULL,
            product_name varchar(200) NOT NULL,
            unit_name varchar(120) NOT NULL,
            base_unit_name varchar(120) NOT NULL,
            unit_price numeric(18,6) NOT NULL,
            line_total numeric(18,2) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_lines_company_id UNIQUE(company_id,id),
            CONSTRAINT uq_sales_lines_number UNIQUE(company_id,sale_id,line_number),
            CONSTRAINT uq_sales_lines_source_quote_line UNIQUE(company_id,source_quotation_line_id),
            CONSTRAINT fk_sales_lines_header_company FOREIGN KEY(company_id,sale_id)
                REFERENCES sales(company_id,id) ON DELETE CASCADE,
            CONSTRAINT fk_sales_lines_source_quote_line FOREIGN KEY(company_id,source_quotation_line_id)
                REFERENCES sales_quotation_lines(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_product_company FOREIGN KEY(company_id,product_id)
                REFERENCES products(company_id,id_product) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_variant_company FOREIGN KEY(company_id,product_id,variant_id)
                REFERENCES product_variants(company_id,product_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_item_company FOREIGN KEY(company_id,inventory_item_id)
                REFERENCES inventory_items(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_packaging FOREIGN KEY(company_id,inventory_item_id,packaging_definition_id)
                REFERENCES inventory_packaging_definitions(company_id,inventory_item_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_unit_company FOREIGN KEY(company_id,unit_id)
                REFERENCES company_units(company_id,unit_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_lines_base_unit_company FOREIGN KEY(company_id,base_unit_id)
                REFERENCES company_units(company_id,unit_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_lines_quantities CHECK(line_number>0 AND quantity>0 AND quantity_base>0 AND unit_factor>0),
            CONSTRAINT ck_sales_lines_amounts CHECK(unit_price>=0 AND line_total>=0),
            CONSTRAINT ck_sales_lines_packaging_snapshot CHECK((packaging_definition_id IS NULL)=(packaging_version IS NULL))
        );

        CREATE TABLE sales_idempotency_commands (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            action varchar(32) NOT NULL,
            idempotency_key varchar(120) NOT NULL,
            fingerprint varchar(64) NOT NULL,
            resource_type varchar(24) NOT NULL,
            resource_id uuid NOT NULL,
            actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_idempotency_action_key UNIQUE(company_id,action,idempotency_key),
            CONSTRAINT fk_sales_idempotency_actor_company FOREIGN KEY(actor_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_idempotency_resource_type CHECK(resource_type IN ('quotation','sale'))
        );

        CREATE FUNCTION guard_sales_lines_draft() RETURNS trigger AS $$
        DECLARE doc_status varchar(16); doc_company uuid; doc_id uuid;
        BEGIN
            IF TG_OP='DELETE' THEN doc_company:=OLD.company_id; doc_id:=OLD.quotation_id;
            ELSE doc_company:=NEW.company_id; doc_id:=NEW.quotation_id; END IF;
            SELECT status INTO doc_status FROM sales_quotations
              WHERE company_id=doc_company AND id=doc_id FOR KEY SHARE;
            IF doc_status IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'sales quotation lines are immutable outside draft';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_quotation_lines_draft
          BEFORE INSERT OR UPDATE OR DELETE ON sales_quotation_lines
          FOR EACH ROW EXECUTE FUNCTION guard_sales_lines_draft();

        CREATE FUNCTION guard_sales_order_lines_draft() RETURNS trigger AS $$
        DECLARE doc_status varchar(16); doc_company uuid; doc_id uuid;
        BEGIN
            IF TG_OP='DELETE' THEN doc_company:=OLD.company_id; doc_id:=OLD.sale_id;
            ELSE doc_company:=NEW.company_id; doc_id:=NEW.sale_id; END IF;
            SELECT status INTO doc_status FROM sales
              WHERE company_id=doc_company AND id=doc_id FOR KEY SHARE;
            IF doc_status IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'sales lines are immutable outside draft';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_lines_draft
          BEFORE INSERT OR UPDATE OR DELETE ON sales_lines
          FOR EACH ROW EXECUTE FUNCTION guard_sales_order_lines_draft();
    """)
    op.execute("""
        INSERT INTO permissions(id,code,description,module,created_at)
        VALUES
          (gen_random_uuid(),'sales_customers:read','Consultar clientes de venta','customers',now()),
          (gen_random_uuid(),'sales_customers:manage','Crear, editar y desactivar clientes','customers',now()),
          (gen_random_uuid(),'sales_quotations:read','Consultar cotizaciones de venta','sales',now()),
          (gen_random_uuid(),'sales_quotations:manage','Crear y editar borradores de cotización','sales',now()),
          (gen_random_uuid(),'sales_quotations:confirm','Confirmar y cancelar cotizaciones','sales',now()),
          (gen_random_uuid(),'sales_quotations:convert','Convertir cotizaciones confirmadas en venta','sales',now()),
          (gen_random_uuid(),'sales:read','Consultar ventas','sales',now()),
          (gen_random_uuid(),'sales:manage','Editar borradores de venta','sales',now()),
          (gen_random_uuid(),'sales:confirm','Confirmar ventas','sales',now()),
          (gen_random_uuid(),'sales:cancel','Cancelar ventas con motivo','sales',now())
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions(role_id,permission_id,created_at)
        SELECT r.id,p.id,now() FROM roles r CROSS JOIN permissions p
        WHERE r.name='SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
          AND r.deleted_at IS NULL AND p.deleted_at IS NULL
          AND p.code IN ('sales_customers:read','sales_customers:manage',
            'sales_quotations:read','sales_quotations:manage','sales_quotations:confirm',
            'sales_quotations:convert','sales:read','sales:manage','sales:confirm','sales:cancel')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sales_lines_draft ON sales_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_sales_quotation_lines_draft ON sales_quotation_lines")
    op.execute("DROP FUNCTION IF EXISTS guard_sales_order_lines_draft()")
    op.execute("DROP FUNCTION IF EXISTS guard_sales_lines_draft()")
    op.execute("""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code IN ('sales_customers:read','sales_customers:manage',
            'sales_quotations:read','sales_quotations:manage','sales_quotations:confirm',
            'sales_quotations:convert','sales:read','sales:manage','sales:confirm','sales:cancel'));
        DELETE FROM permissions WHERE code IN ('sales_customers:read','sales_customers:manage',
            'sales_quotations:read','sales_quotations:manage','sales_quotations:confirm',
            'sales_quotations:convert','sales:read','sales:manage','sales:confirm','sales:cancel');
    """)
    op.execute("DROP TABLE IF EXISTS sales_idempotency_commands")
    op.execute("DROP TABLE IF EXISTS sales_lines")
    op.execute("DROP TABLE IF EXISTS sales")
    op.execute("DROP TABLE IF EXISTS sales_quotation_lines")
    op.execute("DROP TABLE IF EXISTS sales_quotations")
    op.execute("DROP TABLE IF EXISTS sales_customers")
