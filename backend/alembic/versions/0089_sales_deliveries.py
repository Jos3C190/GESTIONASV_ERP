"""Persist sales deliveries, HU allocations and their inventory/valuation links."""

from __future__ import annotations

from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales_lines
          ADD CONSTRAINT uq_sales_lines_company_sale_id UNIQUE(company_id,sale_id,id);

        CREATE TABLE sales_deliveries (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          branch_id uuid NOT NULL,
          sale_id uuid NOT NULL,
          code varchar(48) NOT NULL,
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
          CONSTRAINT uq_sales_deliveries_company_id UNIQUE(company_id,id),
          CONSTRAINT uq_sales_deliveries_company_code UNIQUE(company_id,code),
          CONSTRAINT fk_sales_deliveries_branch_company FOREIGN KEY(branch_id,company_id)
            REFERENCES branches(id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_deliveries_sale_company FOREIGN KEY(company_id,sale_id)
            REFERENCES sales(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_deliveries_creator_company FOREIGN KEY(created_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_deliveries_confirmer_company FOREIGN KEY(confirmed_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_deliveries_canceller_company FOREIGN KEY(cancelled_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_deliveries_status CHECK(status IN ('draft','confirmed','cancelled')),
          CONSTRAINT ck_sales_deliveries_version CHECK(version >= 1),
          CONSTRAINT ck_sales_deliveries_confirmation CHECK(
            (status='confirmed') = (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL)),
          CONSTRAINT ck_sales_deliveries_cancellation CHECK(
            (status='cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL))
        );
        CREATE INDEX ix_sales_deliveries_sale_status ON sales_deliveries(company_id,sale_id,status);

        CREATE TABLE sales_delivery_lines (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          delivery_id uuid NOT NULL,
          sale_id uuid NOT NULL,
          sale_line_id uuid NOT NULL,
          inventory_item_id uuid NOT NULL,
          line_number integer NOT NULL,
          quantity_base numeric(18,6) NOT NULL,
          unit_factor numeric(18,6) NOT NULL,
          product_sku varchar(100) NOT NULL,
          product_name varchar(200) NOT NULL,
          unit_name varchar(120) NOT NULL,
          base_unit_name varchar(120) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_delivery_lines_company_id UNIQUE(company_id,id),
          CONSTRAINT uq_sales_delivery_lines_source UNIQUE(company_id,delivery_id,sale_line_id),
          CONSTRAINT uq_sales_delivery_lines_number UNIQUE(delivery_id,line_number),
          CONSTRAINT fk_sales_delivery_lines_header_company FOREIGN KEY(company_id,delivery_id)
            REFERENCES sales_deliveries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_lines_sale_line FOREIGN KEY(company_id,sale_id,sale_line_id)
            REFERENCES sales_lines(company_id,sale_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_lines_item_company FOREIGN KEY(company_id,inventory_item_id)
            REFERENCES inventory_items(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_delivery_lines_quantity CHECK(line_number > 0 AND quantity_base > 0 AND unit_factor > 0)
        );
        CREATE INDEX ix_sales_delivery_lines_sale ON sales_delivery_lines(company_id,sale_id,sale_line_id);

        CREATE TABLE sales_delivery_allocations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          delivery_line_id uuid NOT NULL,
          inventory_item_id uuid NOT NULL,
          handling_unit_id uuid NOT NULL,
          warehouse_id uuid NOT NULL,
          location_id uuid NOT NULL,
          inventory_lot_detail_id uuid,
          lot_code varchar(120),
          expiry_date date,
          quantity_base numeric(18,6) NOT NULL,
          packaging_snapshot jsonb,
          movement_line_id uuid,
          valuation_entry_id uuid,
          applied_total_cost numeric(24,6),
          applied_unit_cost numeric(24,6),
          CONSTRAINT uq_sales_delivery_allocations_company_id UNIQUE(company_id,id),
          CONSTRAINT uq_sales_delivery_allocation_unit UNIQUE(company_id,delivery_line_id,handling_unit_id),
          CONSTRAINT uq_sales_delivery_allocation_movement_line UNIQUE(movement_line_id),
          CONSTRAINT fk_sales_delivery_allocation_line FOREIGN KEY(company_id,delivery_line_id)
            REFERENCES sales_delivery_lines(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_allocation_unit FOREIGN KEY(company_id,inventory_item_id,handling_unit_id)
            REFERENCES inventory_handling_units(company_id,inventory_item_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_allocation_location FOREIGN KEY(location_id,warehouse_id)
            REFERENCES locations(id,warehouse_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_allocation_lot FOREIGN KEY(company_id,inventory_lot_detail_id)
            REFERENCES inventory_lot_details(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_allocation_movement_line FOREIGN KEY(company_id,movement_line_id)
            REFERENCES inventory_movement_lines(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_allocation_valuation_entry FOREIGN KEY(company_id,valuation_entry_id)
            REFERENCES inventory_valuation_entries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_delivery_allocation_quantity CHECK(quantity_base > 0),
          CONSTRAINT ck_sales_delivery_allocation_posted_cost CHECK(
            (movement_line_id IS NULL AND valuation_entry_id IS NULL AND applied_total_cost IS NULL AND applied_unit_cost IS NULL)
            OR (movement_line_id IS NOT NULL AND valuation_entry_id IS NOT NULL AND applied_total_cost IS NOT NULL AND applied_unit_cost IS NOT NULL)),
          CONSTRAINT ck_sales_delivery_allocation_cost_nonnegative CHECK(applied_total_cost IS NULL OR applied_total_cost >= 0)
        );
        CREATE INDEX ix_sales_delivery_allocation_unit ON sales_delivery_allocations(company_id,handling_unit_id);

        CREATE TABLE sales_delivery_commands (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          action varchar(16) NOT NULL,
          idempotency_key varchar(120) NOT NULL,
          fingerprint varchar(64) NOT NULL,
          delivery_id uuid NOT NULL,
          actor_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_delivery_command_key UNIQUE(company_id,action,idempotency_key),
          CONSTRAINT fk_sales_delivery_command_document FOREIGN KEY(company_id,delivery_id)
            REFERENCES sales_deliveries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_delivery_command_actor FOREIGN KEY(actor_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_delivery_command_action CHECK(action IN ('create','confirm'))
        );

        CREATE FUNCTION guard_sales_delivery_document() RETURNS trigger AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            IF OLD.status <> 'draft' THEN
              RAISE EXCEPTION 'Only a draft delivery can be deleted' USING ERRCODE='23514';
            END IF;
            RETURN OLD;
          END IF;
          IF OLD.status <> 'draft' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'A confirmed or cancelled delivery is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_delivery_document_immutable
          BEFORE UPDATE OR DELETE ON sales_deliveries
          FOR EACH ROW EXECUTE FUNCTION guard_sales_delivery_document();

        CREATE FUNCTION guard_sales_delivery_child_draft() RETURNS trigger AS $$
        DECLARE v_company_id uuid; v_delivery_id uuid; v_status varchar(16);
        BEGIN
          IF TG_OP='DELETE' THEN v_company_id := OLD.company_id;
            IF TG_TABLE_NAME='sales_delivery_lines' THEN v_delivery_id := OLD.delivery_id;
            ELSE SELECT delivery_id INTO v_delivery_id FROM sales_delivery_lines
              WHERE company_id=OLD.company_id AND id=OLD.delivery_line_id; END IF;
          ELSE v_company_id := NEW.company_id;
            IF TG_TABLE_NAME='sales_delivery_lines' THEN v_delivery_id := NEW.delivery_id;
            ELSE SELECT delivery_id INTO v_delivery_id FROM sales_delivery_lines
              WHERE company_id=NEW.company_id AND id=NEW.delivery_line_id; END IF;
          END IF;
          SELECT status INTO v_status FROM sales_deliveries
            WHERE company_id=v_company_id AND id=v_delivery_id;
          IF v_status IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'Only draft delivery lines and allocations can change' USING ERRCODE='23514';
          END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_delivery_lines_draft
          BEFORE INSERT OR UPDATE OR DELETE ON sales_delivery_lines
          FOR EACH ROW EXECUTE FUNCTION guard_sales_delivery_child_draft();
        CREATE TRIGGER trg_sales_delivery_allocations_draft
          BEFORE INSERT OR UPDATE OR DELETE ON sales_delivery_allocations
          FOR EACH ROW EXECUTE FUNCTION guard_sales_delivery_child_draft();

        INSERT INTO permissions(id,code,description,module,created_at)
        VALUES
          (gen_random_uuid(),'sales_deliveries:read','Consultar entregas de venta','sales',now()),
          (gen_random_uuid(),'sales_deliveries:manage','Preparar entregas de venta','sales',now()),
          (gen_random_uuid(),'sales_deliveries:confirm','Confirmar entregas y descontar inventario','sales',now()),
          (gen_random_uuid(),'sales_deliveries:cancel','Cancelar borradores de entrega','sales',now())
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions(role_id,permission_id,created_at)
        SELECT r.id,p.id,now() FROM roles r CROSS JOIN permissions p
        WHERE r.name='SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
          AND r.deleted_at IS NULL AND p.deleted_at IS NULL
          AND p.code IN ('sales_deliveries:read','sales_deliveries:manage',
            'sales_deliveries:confirm','sales_deliveries:cancel')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS trg_sales_delivery_allocations_draft ON sales_delivery_allocations;
        DROP TRIGGER IF EXISTS trg_sales_delivery_lines_draft ON sales_delivery_lines;
        DROP TRIGGER IF EXISTS trg_sales_delivery_document_immutable ON sales_deliveries;
        DROP FUNCTION IF EXISTS guard_sales_delivery_child_draft();
        DROP FUNCTION IF EXISTS guard_sales_delivery_document();
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code IN ('sales_deliveries:read','sales_deliveries:manage',
            'sales_deliveries:confirm','sales_deliveries:cancel'));
        DELETE FROM permissions WHERE code IN ('sales_deliveries:read','sales_deliveries:manage',
          'sales_deliveries:confirm','sales_deliveries:cancel');
        DROP TABLE IF EXISTS sales_delivery_commands;
        DROP TABLE IF EXISTS sales_delivery_allocations;
        DROP TABLE IF EXISTS sales_delivery_lines;
        DROP TABLE IF EXISTS sales_deliveries;
        ALTER TABLE sales_lines DROP CONSTRAINT IF EXISTS uq_sales_lines_company_sale_id;
    """)
