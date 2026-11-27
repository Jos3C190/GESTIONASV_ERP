"""Vitrina del punto de venta: existencia suelta por sucursal, unidades abiertas y conteo de merma.

Revision ID: 0147
Revises: 0146

Bloque V6b.

- Tipo de ubicación ``showcase``: la vitrina. La crea el punto de venta, nunca el formulario de
  ubicaciones; un disparador impide cambiarle el tipo, desactivarla o borrarla mientras una
  sucursal la usa.
- ``pos_showcases``: una vitrina por sucursal, en una ubicación de una bodega de esa sucursal (llaves
  compuestas).
- ``inventory_handling_units.opened_at`` / ``opened_by_id``: una unidad que pasó a vitrina está
  abierta; desde ella se vende por pieza.
- ``pos_showcase_counts`` y ``pos_showcase_count_lines``: el conteo de cierre de la vitrina. La merma
  es lo que el sistema tiene y no se contó; contar de más no crea existencia. Solo se agregan.
"""

from alembic import op
from sqlalchemy import text

revision = "0147"
down_revision = "0146"
branch_labels = None
depends_on = None

_TYPES_BEFORE = (
    "'standard','bulk','receiving','reserve','picking','staging','quality','packing','shipping',"
    "'returns','virtual','vehicle'"
)
_TYPES_AFTER = _TYPES_BEFORE + ",'showcase'"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE locations DROP CONSTRAINT ck_locations_type;
        ALTER TABLE locations ADD CONSTRAINT ck_locations_type
            CHECK (location_type IN ({_TYPES_AFTER}));
        ALTER TABLE warehouses
            ADD CONSTRAINT uq_warehouses_id_branch_company UNIQUE (id, branch_id, company_id);

        CREATE TABLE pos_showcases (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            warehouse_id uuid NOT NULL,
            location_id uuid NOT NULL,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_pos_showcases_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_showcases_company_id_branch UNIQUE (company_id, id, branch_id),
            CONSTRAINT uq_pos_showcases_branch UNIQUE (company_id, branch_id),
            CONSTRAINT uq_pos_showcases_location UNIQUE (location_id),
            CONSTRAINT fk_pos_showcases_warehouse FOREIGN KEY (warehouse_id, branch_id, company_id)
                REFERENCES warehouses (id, branch_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_showcases_location FOREIGN KEY (location_id, warehouse_id)
                REFERENCES locations (id, warehouse_id) ON DELETE RESTRICT
        );

        CREATE FUNCTION guard_pos_showcase_location() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE' AND NEW.location_type <> OLD.location_type
             AND 'showcase' IN (OLD.location_type, NEW.location_type) THEN
            RAISE EXCEPTION 'A POS showcase location keeps its type' USING ERRCODE = '23514';
          END IF;
          IF OLD.location_type = 'showcase'
             AND EXISTS (SELECT 1 FROM pos_showcases s WHERE s.location_id = OLD.id)
             AND (TG_OP = 'DELETE' OR NEW.deleted_at IS NOT NULL OR NOT NEW.is_active
                  OR NEW.lifecycle_status <> 'active' OR NEW.warehouse_id <> OLD.warehouse_id) THEN
            RAISE EXCEPTION 'A POS showcase in use cannot be retired' USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_locations_pos_showcase BEFORE UPDATE OR DELETE ON locations
          FOR EACH ROW EXECUTE FUNCTION guard_pos_showcase_location();

        ALTER TABLE inventory_handling_units
            ADD COLUMN opened_at timestamptz,
            ADD COLUMN opened_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_inventory_handling_units_opened
                CHECK ((opened_at IS NULL) = (opened_by_id IS NULL));

        CREATE TABLE pos_showcase_counts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            showcase_id uuid NOT NULL,
            branch_id uuid NOT NULL,
            number integer NOT NULL CHECK (number >= 1),
            notes varchar(300),
            movement_id uuid,
            waste_cost numeric(18, 6) NOT NULL DEFAULT 0 CHECK (waste_cost >= 0),
            counted_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            counted_at timestamptz NOT NULL DEFAULT now(),
            idempotency_key varchar(120) NOT NULL CHECK (char_length(idempotency_key) >= 8),
            CONSTRAINT uq_pos_showcase_counts_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_pos_showcase_counts_number UNIQUE (company_id, number),
            CONSTRAINT uq_pos_showcase_counts_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_pos_showcase_counts_showcase FOREIGN KEY (company_id, showcase_id, branch_id)
                REFERENCES pos_showcases (company_id, id, branch_id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_showcase_counts_movement FOREIGN KEY (company_id, movement_id)
                REFERENCES inventory_movements (company_id, id) ON DELETE RESTRICT
        );

        CREATE TABLE pos_showcase_count_lines (
            company_id uuid NOT NULL,
            count_id uuid NOT NULL,
            inventory_item_id uuid NOT NULL,
            system_quantity numeric(18, 6) NOT NULL CHECK (system_quantity >= 0),
            counted_quantity numeric(18, 6) NOT NULL CHECK (counted_quantity >= 0),
            waste_quantity numeric(18, 6) NOT NULL,
            reason varchar(200),
            PRIMARY KEY (company_id, count_id, inventory_item_id),
            CONSTRAINT fk_pos_showcase_count_lines_count FOREIGN KEY (company_id, count_id)
                REFERENCES pos_showcase_counts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_pos_showcase_count_lines_item FOREIGN KEY (company_id, inventory_item_id)
                REFERENCES inventory_items (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_pos_showcase_count_lines_waste CHECK (
                counted_quantity <= system_quantity
                AND waste_quantity = system_quantity - counted_quantity
            ),
            CONSTRAINT ck_pos_showcase_count_lines_reason CHECK (
                waste_quantity = 0 OR char_length(btrim(coalesce(reason, ''))) >= 3
            )
        );

        CREATE TRIGGER trg_pos_showcase_counts_append_only
          BEFORE UPDATE OR DELETE ON pos_showcase_counts
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
        CREATE TRIGGER trg_pos_showcase_count_lines_append_only
          BEFORE UPDATE OR DELETE ON pos_showcase_count_lines
          FOR EACH ROW EXECUTE FUNCTION guard_pos_append_only();
    """)


def downgrade() -> None:
    bind = op.get_bind()
    showcases = bind.execute(text("SELECT count(*) FROM pos_showcases")).scalar() or 0
    opened = (
        bind.execute(
            text("SELECT count(*) FROM inventory_handling_units WHERE opened_at IS NOT NULL")
        ).scalar()
        or 0
    )
    if showcases or opened:
        raise RuntimeError(
            f"Hay {showcases} vitrinas y {opened} unidades abiertas en vitrina; la migración 0147 no "
            "las borra. Respáldalas antes de revertir."
        )
    op.execute(f"""
        DROP TABLE pos_showcase_count_lines;
        DROP TABLE pos_showcase_counts;
        ALTER TABLE inventory_handling_units
            DROP CONSTRAINT ck_inventory_handling_units_opened,
            DROP COLUMN opened_by_id,
            DROP COLUMN opened_at;
        DROP TRIGGER trg_locations_pos_showcase ON locations;
        DROP FUNCTION guard_pos_showcase_location();
        DROP TABLE pos_showcases;
        ALTER TABLE warehouses DROP CONSTRAINT uq_warehouses_id_branch_company;
        ALTER TABLE locations DROP CONSTRAINT ck_locations_type;
        ALTER TABLE locations ADD CONSTRAINT ck_locations_type
            CHECK (location_type IN ({_TYPES_BEFORE}));
    """)
