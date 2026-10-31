BEGIN;

-- Running upgrade 0078 -> 0079

ALTER TABLE retaceos ADD COLUMN applied_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE retaceos ADD COLUMN applied_by UUID;

ALTER TABLE retaceos ADD CONSTRAINT ck_retaceos_application CHECK ((applied_at IS NULL AND applied_by IS NULL) OR (applied_at IS NOT NULL AND applied_by IS NOT NULL AND status IN ('verified', 'closed')));

ALTER TABLE inventory_movement_lines ADD CONSTRAINT uq_inventory_movement_lines_company_id UNIQUE (company_id, id);

CREATE TABLE inventory_valuation_settings (
    company_id UUID NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    opened_by UUID NOT NULL, 
    opening_reference VARCHAR(500) NOT NULL, 
    opening_fingerprint VARCHAR(64) NOT NULL, 
    physical_snapshot JSONB NOT NULL, 
    PRIMARY KEY (company_id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT, 
    FOREIGN KEY(currency) REFERENCES currencies (code) ON DELETE RESTRICT
);

CREATE TABLE inventory_cost_averages (
    company_id UUID NOT NULL, 
    inventory_item_id UUID NOT NULL, 
    quantity_base NUMERIC(24, 6) NOT NULL, 
    inventory_value NUMERIC(24, 6) NOT NULL, 
    average_unit_cost NUMERIC(24, 6) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (company_id, inventory_item_id), 
    FOREIGN KEY(company_id) REFERENCES inventory_valuation_settings (company_id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, inventory_item_id) REFERENCES inventory_items (company_id, id) ON DELETE RESTRICT, 
    CONSTRAINT ck_cost_average_nonnegative CHECK (quantity_base >= 0 AND inventory_value >= 0 AND average_unit_cost >= 0), 
    CONSTRAINT ck_cost_average_zero_balance CHECK (quantity_base > 0 OR inventory_value = 0)
);

CREATE TABLE inventory_valuation_entries (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    company_id UUID NOT NULL, 
    inventory_item_id UUID NOT NULL, 
    sequence INTEGER NOT NULL, 
    kind VARCHAR(24) NOT NULL, 
    quantity_base NUMERIC(24, 6) NOT NULL, 
    source_value NUMERIC(24, 6) NOT NULL, 
    original_entry_id UUID, 
    movement_line_id UUID, 
    purchase_detail_id UUID, 
    retaceo_id UUID, 
    source_reference VARCHAR(500) NOT NULL, 
    idempotency_key VARCHAR(160) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    operational_date DATE NOT NULL, 
    accounting_date DATE NOT NULL, 
    posted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    posted_by UUID NOT NULL, 
    inventory_delta NUMERIC(24, 6) NOT NULL, 
    balance_quantity NUMERIC(24, 6) NOT NULL, 
    balance_value NUMERIC(24, 6) NOT NULL, 
    average_unit_cost NUMERIC(24, 6) NOT NULL, 
    cost_breakdown JSONB NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_valuation_entry_company_id UNIQUE (company_id, id), 
    CONSTRAINT uq_valuation_entry_sequence UNIQUE (company_id, sequence), 
    CONSTRAINT uq_valuation_entry_key UNIQUE (company_id, idempotency_key), 
    CONSTRAINT uq_valuation_movement_line UNIQUE (movement_line_id), 
    FOREIGN KEY(company_id) REFERENCES inventory_valuation_settings (company_id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, inventory_item_id) REFERENCES inventory_items (company_id, id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, original_entry_id) REFERENCES inventory_valuation_entries (company_id, id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, movement_line_id) REFERENCES inventory_movement_lines (company_id, id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, purchase_detail_id) REFERENCES purchase_details (company_id, id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, retaceo_id) REFERENCES retaceos (company_id, id) ON DELETE RESTRICT, 
    CONSTRAINT ck_valuation_entry_kind CHECK (kind IN ('opening','receipt','issue','supplier_return','customer_return','adjustment_in','adjustment_out','cost_adjustment','supplier_credit')), 
    CONSTRAINT ck_valuation_entry_nonnegative CHECK (quantity_base >= 0 AND balance_quantity >= 0 AND balance_value >= 0)
);

CREATE INDEX ix_valuation_item_sequence ON inventory_valuation_entries (company_id, inventory_item_id, sequence);

CREATE TABLE inventory_retaceo_applications (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    company_id UUID NOT NULL, 
    retaceo_id UUID NOT NULL, 
    purchase_id UUID NOT NULL, 
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    applied_by UUID NOT NULL, 
    summary JSONB NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_retaceo_application_retaceo UNIQUE (company_id, retaceo_id), 
    CONSTRAINT uq_retaceo_application_purchase UNIQUE (company_id, purchase_id), 
    FOREIGN KEY(company_id, retaceo_id) REFERENCES retaceos (company_id, id) ON DELETE RESTRICT, 
    FOREIGN KEY(company_id, purchase_id) REFERENCES purchases (company_id, id) ON DELETE RESTRICT
);

CREATE FUNCTION guard_inventory_valuation_history() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Valuation history is immutable; append a documented adjustment';
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER immutable_inventory_valuation_entries BEFORE UPDATE OR DELETE ON inventory_valuation_entries FOR EACH ROW EXECUTE FUNCTION guard_inventory_valuation_history();

CREATE TRIGGER immutable_inventory_retaceo_applications BEFORE UPDATE OR DELETE ON inventory_retaceo_applications FOR EACH ROW EXECUTE FUNCTION guard_inventory_valuation_history();

CREATE TRIGGER immutable_inventory_valuation_settings BEFORE UPDATE OR DELETE ON inventory_valuation_settings FOR EACH ROW EXECUTE FUNCTION guard_inventory_valuation_history();

INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), 'inventory:valuation', 'Consultar y aprobar valoración de inventario', 'inventory', now())
        ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE
        AND r.company_id IS NULL AND r.deleted_at IS NULL
        AND p.deleted_at IS NULL AND p.code = 'inventory:valuation'
        ON CONFLICT DO NOTHING;

UPDATE alembic_version SET version_num='0079' WHERE alembic_version.version_num = '0078';

COMMIT;

