"""Persist customer returns linked to delivery allocations and original issues."""

from __future__ import annotations

from alembic import op

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_returns (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          branch_id uuid NOT NULL,
          sale_id uuid NOT NULL,
          code varchar(48) NOT NULL,
          status varchar(20) NOT NULL DEFAULT 'draft',
          notes text,
          created_by_id uuid NOT NULL,
          received_by_id uuid,
          received_at timestamptz,
          updated_by_id uuid NOT NULL,
          cancelled_by_id uuid,
          cancelled_at timestamptz,
          cancellation_reason varchar(500),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_returns_company_id UNIQUE(company_id,id),
          CONSTRAINT uq_sales_returns_company_code UNIQUE(company_id,code),
          CONSTRAINT fk_sales_returns_branch_company FOREIGN KEY(branch_id,company_id)
            REFERENCES branches(id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_returns_sale_company FOREIGN KEY(company_id,sale_id)
            REFERENCES sales(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_returns_creator_company FOREIGN KEY(created_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_returns_receiver_company FOREIGN KEY(received_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_returns_updater_company FOREIGN KEY(updated_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_returns_canceller_company FOREIGN KEY(cancelled_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_returns_status CHECK(status IN
            ('draft','received','under_review','accepted','rejected','mixed','cancelled')),
          CONSTRAINT ck_sales_returns_received_state CHECK(
            (status IN ('draft','cancelled')) = (received_at IS NULL AND received_by_id IS NULL)),
          CONSTRAINT ck_sales_returns_cancellation CHECK(
            (status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL))
        );
        CREATE INDEX ix_sales_returns_sale_status ON sales_returns(company_id,sale_id,status);

        CREATE TABLE sales_return_lines (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          return_id uuid NOT NULL,
          sale_id uuid NOT NULL,
          delivery_id uuid NOT NULL,
          delivery_line_id uuid NOT NULL,
          delivery_allocation_id uuid NOT NULL,
          inventory_item_id uuid NOT NULL,
          source_valuation_entry_id uuid NOT NULL,
          source_handling_unit_id uuid NOT NULL,
          source_warehouse_id uuid NOT NULL,
          source_location_id uuid NOT NULL,
          inventory_lot_detail_id uuid,
          line_number integer NOT NULL,
          product_sku varchar(100) NOT NULL,
          product_name varchar(200) NOT NULL,
          unit_name varchar(120) NOT NULL,
          base_unit_name varchar(120) NOT NULL,
          lot_code varchar(120),
          expiry_date date,
          quantity_received_base numeric(18,6) NOT NULL,
          reason varchar(500) NOT NULL,
          declared_condition varchar(24) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_return_lines_company_id UNIQUE(company_id,id),
          CONSTRAINT uq_sales_return_lines_number UNIQUE(return_id,line_number),
          CONSTRAINT fk_sales_return_lines_header FOREIGN KEY(company_id,return_id)
            REFERENCES sales_returns(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_sale FOREIGN KEY(company_id,sale_id)
            REFERENCES sales(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_delivery FOREIGN KEY(company_id,delivery_id)
            REFERENCES sales_deliveries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_delivery_line FOREIGN KEY(company_id,delivery_line_id)
            REFERENCES sales_delivery_lines(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_allocation FOREIGN KEY(company_id,delivery_allocation_id)
            REFERENCES sales_delivery_allocations(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_item FOREIGN KEY(company_id,inventory_item_id)
            REFERENCES inventory_items(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_source_valuation FOREIGN KEY(company_id,source_valuation_entry_id)
            REFERENCES inventory_valuation_entries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_source_hu FOREIGN KEY(company_id,inventory_item_id,source_handling_unit_id)
            REFERENCES inventory_handling_units(company_id,inventory_item_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_lot_detail FOREIGN KEY(company_id,inventory_lot_detail_id)
            REFERENCES inventory_lot_details(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_lines_source_location FOREIGN KEY(source_location_id,source_warehouse_id)
            REFERENCES locations(id,warehouse_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_return_lines_quantity CHECK(line_number > 0 AND quantity_received_base > 0),
          CONSTRAINT ck_sales_return_lines_condition CHECK(declared_condition IN
            ('resalable','damaged','wrong_item','other'))
        );
        CREATE INDEX ix_sales_return_lines_source ON sales_return_lines(company_id,delivery_allocation_id);

        CREATE TABLE sales_return_events (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          return_id uuid NOT NULL,
          return_line_id uuid NOT NULL,
          decision varchar(16) NOT NULL,
          quantity_base numeric(18,6) NOT NULL,
          condition varchar(24) NOT NULL,
          reason varchar(500) NOT NULL,
          destination_location_id uuid,
          movement_id uuid,
          movement_line_id uuid,
          valuation_entry_id uuid,
          actor_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_return_events_company_id UNIQUE(company_id,id),
          CONSTRAINT fk_sales_return_events_header FOREIGN KEY(company_id,return_id)
            REFERENCES sales_returns(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_line FOREIGN KEY(company_id,return_line_id)
            REFERENCES sales_return_lines(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_movement FOREIGN KEY(company_id,movement_id)
            REFERENCES inventory_movements(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_movement_line FOREIGN KEY(company_id,movement_line_id)
            REFERENCES inventory_movement_lines(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_valuation FOREIGN KEY(company_id,valuation_entry_id)
            REFERENCES inventory_valuation_entries(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_destination FOREIGN KEY(destination_location_id)
            REFERENCES locations(id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_events_actor_company FOREIGN KEY(actor_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_return_event_decision CHECK(decision IN ('accepted','rejected')),
          CONSTRAINT ck_sales_return_event_quantity CHECK(quantity_base > 0),
          CONSTRAINT ck_sales_return_event_condition CHECK(condition IN ('resalable','damaged','wrong_item','other')),
          CONSTRAINT ck_sales_return_event_inventory_link CHECK(
            (decision = 'accepted') = (destination_location_id IS NOT NULL AND movement_id IS NOT NULL AND movement_line_id IS NOT NULL AND valuation_entry_id IS NOT NULL))
        );
        CREATE INDEX ix_sales_return_events_line ON sales_return_events(company_id,return_line_id);

        CREATE TABLE sales_return_commands (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          action varchar(16) NOT NULL,
          idempotency_key varchar(120) NOT NULL,
          fingerprint varchar(64) NOT NULL,
          return_id uuid NOT NULL,
          actor_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_sales_return_command_key UNIQUE(company_id,action,idempotency_key),
          CONSTRAINT fk_sales_return_command_document FOREIGN KEY(company_id,return_id)
            REFERENCES sales_returns(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_command_actor FOREIGN KEY(actor_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
          CONSTRAINT ck_sales_return_command_action CHECK(action IN ('create','receive','resolve','cancel'))
        );

        CREATE TABLE sales_return_documents (
          company_id uuid NOT NULL,
          return_id uuid NOT NULL,
          document_id uuid NOT NULL,
          attached_by_id uuid NOT NULL,
          attached_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT pk_sales_return_documents PRIMARY KEY(company_id,return_id,document_id),
          CONSTRAINT fk_sales_return_documents_return FOREIGN KEY(company_id,return_id)
            REFERENCES sales_returns(company_id,id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_documents_asset FOREIGN KEY(document_id,company_id)
            REFERENCES document_assets(id,company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_sales_return_documents_actor FOREIGN KEY(attached_by_id,company_id)
            REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_sales_return_documents_return ON sales_return_documents(company_id,return_id);

        CREATE FUNCTION guard_sales_return_document() RETURNS trigger AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Sales returns are append-only documents' USING ERRCODE='23514';
          END IF;
          IF OLD.status IN ('accepted','rejected','mixed','cancelled') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'A final sales return is immutable' USING ERRCODE='23514';
          END IF;
          IF OLD.status='draft' AND NEW.status NOT IN ('draft','received','cancelled') THEN
            RAISE EXCEPTION 'Invalid sales return state transition' USING ERRCODE='23514';
          END IF;
          IF OLD.status='received' AND NEW.status NOT IN ('received','under_review','accepted','rejected','mixed') THEN
            RAISE EXCEPTION 'Invalid sales return state transition' USING ERRCODE='23514';
          END IF;
          IF OLD.status='under_review' AND NEW.status NOT IN ('under_review','accepted','rejected','mixed') THEN
            RAISE EXCEPTION 'Invalid sales return state transition' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_return_document_immutable
          BEFORE UPDATE OR DELETE ON sales_returns
          FOR EACH ROW EXECUTE FUNCTION guard_sales_return_document();

        CREATE FUNCTION guard_sales_return_child_draft() RETURNS trigger AS $$
        DECLARE v_company_id uuid; v_return_id uuid; v_status varchar(20);
        BEGIN
          IF TG_OP='DELETE' THEN v_company_id := OLD.company_id; v_return_id := OLD.return_id;
          ELSE v_company_id := NEW.company_id; v_return_id := NEW.return_id; END IF;
          SELECT status INTO v_status FROM sales_returns
            WHERE company_id=v_company_id AND id=v_return_id;
          IF v_status IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'Only draft return lines can change' USING ERRCODE='23514';
          END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_return_lines_draft
          BEFORE INSERT OR UPDATE OR DELETE ON sales_return_lines
          FOR EACH ROW EXECUTE FUNCTION guard_sales_return_child_draft();

        CREATE FUNCTION guard_sales_return_event_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'Sales return decisions are append-only' USING ERRCODE='23514';
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_sales_return_events_append_only
          BEFORE UPDATE OR DELETE ON sales_return_events
          FOR EACH ROW EXECUTE FUNCTION guard_sales_return_event_append_only();
        CREATE TRIGGER trg_sales_return_commands_append_only
          BEFORE UPDATE OR DELETE ON sales_return_commands
          FOR EACH ROW EXECUTE FUNCTION guard_sales_return_event_append_only();

        INSERT INTO permissions(id,code,description,module,created_at)
        VALUES
          (gen_random_uuid(),'sales_returns:read','Consultar devoluciones de venta','sales',now()),
          (gen_random_uuid(),'sales_returns:manage','Registrar devoluciones de venta','sales',now()),
          (gen_random_uuid(),'sales_returns:receive','Registrar recepción de devoluciones','sales',now()),
          (gen_random_uuid(),'sales_returns:resolve','Aceptar o rechazar mercancía devuelta','sales',now()),
          (gen_random_uuid(),'sales_returns:cancel','Cancelar borradores de devolución','sales',now())
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions(role_id,permission_id,created_at)
        SELECT r.id,p.id,now() FROM roles r CROSS JOIN permissions p
        WHERE r.name='SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
          AND r.deleted_at IS NULL AND p.deleted_at IS NULL
          AND p.code IN ('sales_returns:read','sales_returns:manage','sales_returns:receive',
            'sales_returns:resolve','sales_returns:cancel')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code LIKE 'sales_returns:%');
        DELETE FROM permissions WHERE code LIKE 'sales_returns:%';
        DROP TABLE IF EXISTS sales_return_documents;
        DROP TRIGGER IF EXISTS trg_sales_return_commands_append_only ON sales_return_commands;
        DROP TRIGGER IF EXISTS trg_sales_return_events_append_only ON sales_return_events;
        DROP TRIGGER IF EXISTS trg_sales_return_lines_draft ON sales_return_lines;
        DROP TRIGGER IF EXISTS trg_sales_return_document_immutable ON sales_returns;
        DROP FUNCTION IF EXISTS guard_sales_return_event_append_only();
        DROP FUNCTION IF EXISTS guard_sales_return_child_draft();
        DROP FUNCTION IF EXISTS guard_sales_return_document();
        DROP TABLE IF EXISTS sales_return_commands;
        DROP TABLE IF EXISTS sales_return_events;
        DROP TABLE IF EXISTS sales_return_lines;
        DROP TABLE IF EXISTS sales_returns;
    """)
