"""The headquarters migration preserves physical and historical inventory data."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect
from psycopg.sql import SQL, Identifier

pytestmark = pytest.mark.e2e


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL_SYNC"])
    return config


def _company_table_rows(connection, table: str, company_id: uuid.UUID) -> list[tuple[object, ...]]:
    order_column = {
        "inventory_valuation_settings": "company_id",
        "inventory_cost_averages": "inventory_item_id",
    }.get(table, "id")
    statement = SQL("SELECT * FROM {} WHERE company_id = %s ORDER BY {}").format(
        Identifier(table), Identifier(order_column)
    )
    return connection.execute(statement, (company_id,)).fetchall()


def test_migration_preserves_central_warehouse_inventory_and_purchase_history() -> None:
    config = _alembic_config()
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    command.downgrade(config, "0083")
    try:
        with connect(dsn) as connection:
            company_id = connection.execute(
                "SELECT id FROM companies WHERE is_active AND deleted_at IS NULL ORDER BY id LIMIT 1"
            ).fetchone()[0]
            category_id = connection.execute(
                "SELECT id FROM warehouse_categories WHERE company_id = %s "
                "AND is_active AND deleted_at IS NULL ORDER BY id LIMIT 1",
                (company_id,),
            ).fetchone()[0]
            now = datetime.now(UTC)
            product_row = connection.execute(
                "SELECT product.id_product, product.purchase_unit "
                "FROM products AS product JOIN company_units AS company_unit "
                "ON company_unit.company_id = product.company_id "
                "AND company_unit.unit_id = product.purchase_unit "
                "WHERE product.company_id = %s AND product.is_active "
                "AND product.deleted_at IS NULL AND company_unit.is_enabled "
                "ORDER BY product.id_product LIMIT 1",
                (company_id,),
            ).fetchone()
            assert product_row is not None, "El seed E2E requiere un producto y unidad base."
            product_id, unit_id = product_row
            item_row = connection.execute(
                "SELECT id FROM inventory_items WHERE company_id = %s AND product_id = %s "
                "AND base_unit_id = %s AND is_active ORDER BY id LIMIT 1",
                (company_id, product_id, unit_id),
            ).fetchone()
            if item_row is None:
                item_id = uuid.uuid4()
                connection.execute(
                    "INSERT INTO inventory_items (id, company_id, product_id, variant_id, "
                    "base_unit_id, is_active, created_at, updated_at) "
                    "VALUES (%s, %s, %s, NULL, %s, true, %s, %s)",
                    (item_id, company_id, product_id, unit_id, now, now),
                )
            else:
                item_id = item_row[0]
            existing_central = connection.execute(
                "SELECT id FROM warehouses WHERE company_id = %s AND is_central "
                "AND deleted_at IS NULL ORDER BY id LIMIT 1",
                (company_id,),
            ).fetchone()

            if existing_central is None:
                warehouse_id = uuid.uuid4()
                connection.execute(
                    "INSERT INTO warehouses (id, company_id, branch_id, warehouse_category_id, "
                    "name, code, warehouse_type, is_central, operational_status, created_at, updated_at) "
                    "VALUES (%s, %s, NULL, %s, %s, %s, 'general', true, 'active', %s, %s)",
                    (
                        warehouse_id,
                        company_id,
                        category_id,
                        f"Bodega central migración {warehouse_id.hex[:6]}",
                        f"B01-{warehouse_id.hex[:10]}",
                        now,
                        now,
                    ),
                )
            else:
                warehouse_id = existing_central[0]

            location_id = uuid.uuid4()
            handling_unit_id = uuid.uuid4()
            movement_id = uuid.uuid4()
            movement_line_id = uuid.uuid4()
            purchase_id = uuid.uuid4()
            purchase_detail_id = uuid.uuid4()
            quotation_id = uuid.uuid4()
            quotation_detail_id = uuid.uuid4()
            purchase_order_id = uuid.uuid4()
            purchase_order_detail_id = uuid.uuid4()
            location_code = f"B01-{location_id.hex[:10]}"
            connection.execute(
                "INSERT INTO locations (id, warehouse_id, code, aisle, rack, level, position, "
                "created_at, updated_at) VALUES (%s, %s, %s, 'A', 'R01', 'N01', 'P01', %s, %s)",
                (location_id, warehouse_id, location_code, now, now),
            )
            connection.execute(
                "INSERT INTO inventory_handling_units (id, company_id, warehouse_id, location_id, "
                "inventory_item_id, code, quantity_base, occupied_weight_kg, occupied_volume_m3, "
                "stock_status, measurement_status, measurement_source, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, 2.5, 0.5, 0.25, 'available', 'verified', 'master', %s, %s)",
                (
                    handling_unit_id,
                    company_id,
                    warehouse_id,
                    location_id,
                    item_id,
                    f"HU-B01-{handling_unit_id.hex[:12]}",
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO inventory_balances (id, company_id, warehouse_id, location_id, "
                "inventory_item_id, stock_status, quantity_base, occupied_weight_kg, "
                "occupied_volume_m3) VALUES (%s, %s, %s, %s, %s, 'available', 2.5, 0.5, 0.25)",
                (uuid.uuid4(), company_id, warehouse_id, location_id, item_id),
            )
            connection.execute(
                "INSERT INTO inventory_movements (id, company_id, movement_type, idempotency_key, "
                "request_fingerprint, source_reference, posted_at, created_at) "
                "VALUES (%s, %s, 'receipt', %s, %s, 'B01-migration-test', %s, %s)",
                (
                    movement_id,
                    company_id,
                    f"b01-{movement_id.hex}",
                    "a" * 64,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO inventory_movement_lines (id, company_id, movement_id, line_number, "
                "inventory_item_id, handling_unit_id, to_warehouse_id, to_location_id, "
                "to_stock_status, quantity_base, occupied_weight_kg, occupied_volume_m3, "
                "measurement_status) VALUES (%s, %s, %s, 1, %s, %s, %s, %s, 'available', "
                "2.5, 0.5, 0.25, 'verified')",
                (
                    movement_line_id,
                    company_id,
                    movement_id,
                    item_id,
                    handling_unit_id,
                    warehouse_id,
                    location_id,
                ),
            )

            purchase_refs = connection.execute(
                "SELECT supplier.id_supplier, app_user.id, currency.code "
                "FROM suppliers AS supplier CROSS JOIN users AS app_user "
                "CROSS JOIN currencies AS currency "
                "WHERE supplier.company_id = %s AND supplier.is_active "
                "AND supplier.supplier_status = 'approved' AND app_user.is_active "
                "AND currency.is_active ORDER BY supplier.id_supplier, app_user.id, currency.code "
                "LIMIT 1",
                (company_id,),
            ).fetchone()
            assert purchase_refs is not None, "El seed E2E requiere proveedor, usuario y moneda."
            supplier_id, user_id, currency = purchase_refs
            connection.execute(
                "INSERT INTO purchase_quotations (id, company_id, code, supplier_id, "
                "quotation_date, currency, subtotal, discount, tax, total, status, "
                "version_number, created_by_id, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, 8, 0, 0, 8, 'selected', 1, %s, %s, %s)",
                (
                    quotation_id,
                    company_id,
                    f"B01-Q-{quotation_id.hex[:8]}",
                    supplier_id,
                    now,
                    currency,
                    user_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO purchase_quotation_details (id, company_id, purchase_quotation_id, "
                "product_id, unit_id, quantity, offered_quantity, available_quantity, unit_price, "
                "discount, subtotal, tax_rate, tax_amount, total, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 2, 2, 2, 4, 0, 8, 0, 0, 8, %s, %s)",
                (
                    quotation_detail_id,
                    company_id,
                    quotation_id,
                    product_id,
                    unit_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO purchase_orders (id, company_id, code, supplier_id, branch_id, "
                "warehouse_id, purchase_quotation_id, created_by_id, order_date, currency, "
                "subtotal, discount, tax, additional_expenses, total, status, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, 8, 0, 0, 0, 8, 'sent', %s, %s)",
                (
                    purchase_order_id,
                    company_id,
                    f"B01-PO-{purchase_order_id.hex[:8]}",
                    supplier_id,
                    warehouse_id,
                    quotation_id,
                    user_id,
                    now,
                    currency,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO purchase_order_details (id, company_id, purchase_order_id, "
                "purchase_quotation_detail_id, product_id, quantity, unit_id, unit_price, "
                "discount, subtotal, tax_rate, tax_amount, total, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 2, %s, 4, 0, 8, 0, 0, 8, %s, %s)",
                (
                    purchase_order_detail_id,
                    company_id,
                    purchase_order_id,
                    quotation_detail_id,
                    product_id,
                    unit_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO purchases (id, company_id, code, purchase_order_id, supplier_id, "
                "branch_id, warehouse_id, created_by_id, currency, subtotal, discount, tax, total, "
                "status, purchase_date, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, NULL, "
                "%s, %s, %s, 8, 0, 0, 8, 'received', %s, %s, %s)",
                (
                    purchase_id,
                    company_id,
                    f"B01-R-{purchase_id.hex[:8]}",
                    purchase_order_id,
                    supplier_id,
                    warehouse_id,
                    user_id,
                    currency,
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO purchase_details (id, company_id, purchase_id, "
                "purchase_order_detail_id, product_id, quantity_ordered, quantity_received, "
                "unit_id, unit_price, discount, subtotal, tax_rate, tax_amount, total, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 2, 2, %s, 4, 0, 8, 0, 0, 8, %s, %s)",
                (
                    purchase_detail_id,
                    company_id,
                    purchase_id,
                    purchase_order_detail_id,
                    product_id,
                    unit_id,
                    now,
                    now,
                ),
            )
            retaceo_id = uuid.uuid4()
            valuation_entry_id = uuid.uuid4()
            retaceo_application_id = uuid.uuid4()
            connection.execute(
                "INSERT INTO inventory_valuation_settings (company_id, currency, opened_at, "
                "opened_by, opening_reference, opening_fingerprint, physical_snapshot) "
                "VALUES (%s, %s, %s, %s, %s, %s, '[]'::jsonb)",
                (
                    company_id,
                    currency,
                    now,
                    user_id,
                    "B01 migration preservation test",
                    "c" * 64,
                ),
            )
            connection.execute(
                "INSERT INTO inventory_cost_averages (company_id, inventory_item_id, "
                "quantity_base, inventory_value, average_unit_cost, updated_at) "
                "VALUES (%s, %s, 2.5, 10, 4, %s)",
                (company_id, item_id, now),
            )
            connection.execute(
                "INSERT INTO inventory_valuation_entries (id, company_id, inventory_item_id, "
                "sequence, kind, quantity_base, source_value, movement_line_id, purchase_detail_id, "
                "source_reference, idempotency_key, fingerprint, operational_date, accounting_date, "
                "posted_at, posted_by, inventory_delta, balance_quantity, balance_value, "
                "average_unit_cost, cost_breakdown) "
                "VALUES (%s, %s, %s, 1, 'receipt', 2.5, 10, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, 10, 2.5, 10, 4, '[]'::jsonb)",
                (
                    valuation_entry_id,
                    company_id,
                    item_id,
                    movement_line_id,
                    purchase_detail_id,
                    f"b01-valuation:{purchase_id}",
                    f"b01-valuation:{purchase_id}",
                    "d" * 64,
                    now.date(),
                    now.date(),
                    now,
                    user_id,
                ),
            )
            connection.execute(
                "INSERT INTO retaceos (id, company_id, code, purchase_id, created_by_id, currency, "
                "total_fob, total_freight, total_expenses, total_dai, import_vat, total_cost, "
                "status, applied_at, applied_by, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, 8, 2, 0, 0, 0, 10, 'closed', %s, %s, %s, %s)",
                (
                    retaceo_id,
                    company_id,
                    f"B01-RC-{retaceo_id.hex[:8]}",
                    purchase_id,
                    user_id,
                    currency,
                    now,
                    user_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO inventory_retaceo_applications (id, company_id, retaceo_id, "
                "purchase_id, applied_at, applied_by, summary) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
                (
                    retaceo_application_id,
                    company_id,
                    retaceo_id,
                    purchase_id,
                    now,
                    user_id,
                    '{"B01":"preserve"}',
                ),
            )
            connection.commit()

            warehouse_before = connection.execute(
                "SELECT to_jsonb(warehouse) - 'branch_id' - 'updated_at' "
                "FROM warehouses AS warehouse WHERE id = %s",
                (warehouse_id,),
            ).fetchone()[0]
            location_before = connection.execute(
                "SELECT * FROM locations WHERE id = %s", (location_id,)
            ).fetchone()
            preserved_tables = (
                "inventory_handling_units",
                "inventory_balances",
                "inventory_movements",
                "inventory_movement_lines",
                "purchase_quotations",
                "purchase_quotation_details",
                "purchase_orders",
                "purchase_order_details",
                "purchases",
                "purchase_details",
                "inventory_lots",
                "inventory_lot_details",
                "inventory_valuation_settings",
                "inventory_cost_averages",
                "inventory_valuation_entries",
                "inventory_retaceo_applications",
                "retaceos",
            )
            rows_before = {
                table: _company_table_rows(connection, table, company_id)
                for table in preserved_tables
            }

        command.upgrade(config, "0084")

        with connect(dsn) as connection:
            mapped = connection.execute(
                "SELECT warehouse.branch_id, branch.company_id, branch.is_headquarters "
                "FROM warehouses AS warehouse JOIN branches AS branch ON branch.id = warehouse.branch_id "
                "WHERE warehouse.id = %s",
                (warehouse_id,),
            ).fetchone()
            assert mapped is not None
            assert mapped[0] is not None
            assert mapped[1:] == (company_id, True)
            assert connection.execute(
                "SELECT to_jsonb(warehouse) - 'branch_id' - 'updated_at' "
                "FROM warehouses AS warehouse WHERE id = %s",
                (warehouse_id,),
            ).fetchone()[0] == warehouse_before
            assert connection.execute(
                "SELECT quantity_base FROM inventory_handling_units WHERE id = %s",
                (handling_unit_id,),
            ).fetchone()[0] == 2.5
            assert connection.execute(
                "SELECT quantity_base FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s",
                (warehouse_id, location_id),
            ).fetchone()[0] == 2.5
            assert connection.execute(
                "SELECT * FROM locations WHERE id = %s", (location_id,)
            ).fetchone() == location_before
            assert connection.execute(
                "SELECT to_warehouse_id FROM inventory_movement_lines WHERE movement_id = %s",
                (movement_id,),
            ).fetchone()[0] == warehouse_id
            assert connection.execute(
                "SELECT warehouse_id, branch_id FROM purchases WHERE id = %s", (purchase_id,)
            ).fetchone() == (warehouse_id, None)
            assert {
                table: _company_table_rows(connection, table, company_id)
                for table in preserved_tables
            } == rows_before

        mapped_headquarters_id = mapped[0]
        command.downgrade(config, "0083")
        command.upgrade(config, "0084")
        with connect(dsn) as connection:
            repeated_mapping = connection.execute(
                "SELECT branch_id FROM warehouses WHERE id = %s", (warehouse_id,)
            ).fetchone()
            active_headquarters_count = connection.execute(
                "SELECT count(*) FROM branches WHERE company_id = %s AND is_headquarters "
                "AND is_active AND operational_status = 'active' AND deleted_at IS NULL",
                (company_id,),
            ).fetchone()[0]
            central_warehouse_count = connection.execute(
                "SELECT count(*) FROM warehouses WHERE company_id = %s AND is_central "
                "AND is_active AND operational_status = 'active' AND deleted_at IS NULL",
                (company_id,),
            ).fetchone()[0]
            assert repeated_mapping == (mapped_headquarters_id,)
            assert active_headquarters_count == 1
            assert central_warehouse_count == 1
    finally:
        command.upgrade(config, "head")


def test_duplicate_central_warehouses_fail_without_partial_migration() -> None:
    config = _alembic_config()
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    command.downgrade(config, "0083")
    duplicate_ids = (uuid.uuid4(), uuid.uuid4())
    try:
        with connect(dsn) as connection:
            company_id = connection.execute(
                "SELECT id FROM companies WHERE is_active AND deleted_at IS NULL ORDER BY id LIMIT 1"
            ).fetchone()[0]
            category_id = connection.execute(
                "SELECT id FROM warehouse_categories WHERE company_id = %s "
                "AND is_active AND deleted_at IS NULL ORDER BY id LIMIT 1",
                (company_id,),
            ).fetchone()[0]
            now = datetime.now(UTC)
            connection.execute("DROP INDEX uq_warehouses_company_active_central_unassigned")
            for warehouse_id in duplicate_ids:
                connection.execute(
                    "INSERT INTO warehouses (id, company_id, branch_id, warehouse_category_id, "
                    "name, code, is_central, operational_status, created_at, updated_at) "
                    "VALUES (%s, %s, NULL, %s, %s, %s, true, 'active', %s, %s)",
                    (
                        warehouse_id,
                        company_id,
                        category_id,
                        f"Central ambiguo {warehouse_id.hex[:6]}",
                        f"B01-{warehouse_id.hex[:10]}",
                        now,
                        now,
                    ),
                )
            connection.commit()

        with pytest.raises(RuntimeError, match="bodegas centrales activas duplicadas"):
            command.upgrade(config, "0084")

        with connect(dsn) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("0083",)
            assert connection.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'branches' "
                "AND column_name = 'is_headquarters'"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM warehouses WHERE id = ANY(%s) AND branch_id IS NULL",
                (list(duplicate_ids),),
            ).fetchone()[0] == 2
            connection.execute(
                "DELETE FROM warehouses WHERE id = ANY(%s)", (list(duplicate_ids),)
            )
            connection.execute(
                "CREATE UNIQUE INDEX uq_warehouses_company_active_central_unassigned "
                "ON warehouses (company_id) WHERE branch_id IS NULL AND is_central "
                "AND is_active AND operational_status = 'active' AND deleted_at IS NULL"
            )
            connection.commit()
    finally:
        with connect(dsn) as connection:
            connection.execute("DELETE FROM warehouses WHERE id = ANY(%s)", (list(duplicate_ids),))
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_warehouses_company_active_central_unassigned "
                "ON warehouses (company_id) WHERE branch_id IS NULL AND is_central "
                "AND is_active AND operational_status = 'active' AND deleted_at IS NULL"
            )
        command.upgrade(config, "head")


def test_mid_mapping_failure_rolls_back_schema_headquarters_and_warehouse_link() -> None:
    config = _alembic_config()
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    command.downgrade(config, "0083")
    test_warehouse_id = uuid.uuid4()
    inserted_warehouse = False
    try:
        with connect(dsn) as connection:
            company_id = connection.execute(
                "SELECT id FROM companies WHERE is_active AND deleted_at IS NULL ORDER BY id LIMIT 1"
            ).fetchone()[0]
            category_id = connection.execute(
                "SELECT id FROM warehouse_categories WHERE company_id = %s "
                "AND is_active AND deleted_at IS NULL ORDER BY id LIMIT 1",
                (company_id,),
            ).fetchone()[0]
            central_id = connection.execute(
                "SELECT id FROM warehouses WHERE company_id = %s AND is_central "
                "AND is_active AND operational_status = 'active' AND deleted_at IS NULL "
                "ORDER BY id LIMIT 1",
                (company_id,),
            ).fetchone()
            if central_id is None:
                now = datetime.now(UTC)
                connection.execute(
                    "INSERT INTO warehouses (id, company_id, branch_id, warehouse_category_id, "
                    "name, code, warehouse_type, is_central, operational_status, created_at, updated_at) "
                    "VALUES (%s, %s, NULL, %s, %s, %s, 'general', true, 'active', %s, %s)",
                    (
                        test_warehouse_id,
                        company_id,
                        category_id,
                        f"Bodega para rollback B01 {test_warehouse_id.hex[:6]}",
                        f"B01-RB-{test_warehouse_id.hex[:8]}",
                        now,
                        now,
                    ),
                )
                inserted_warehouse = True
            else:
                test_warehouse_id = central_id[0]
            branch_count_before = connection.execute(
                "SELECT count(*) FROM branches WHERE company_id = %s", (company_id,)
            ).fetchone()[0]
            connection.execute(
                "CREATE FUNCTION b01_test_fail_after_matrix_insert() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "IF OLD.is_central AND NEW.branch_id IS NOT NULL THEN "
                "RAISE EXCEPTION 'B01_TEST_FAIL_AFTER_MATRIX_INSERT'; "
                "END IF; RETURN NEW; END; $$"
            )
            connection.execute(
                "CREATE TRIGGER b01_test_fail_after_matrix_insert "
                "BEFORE UPDATE OF branch_id ON warehouses FOR EACH ROW "
                "EXECUTE FUNCTION b01_test_fail_after_matrix_insert()"
            )
            connection.commit()

        with pytest.raises(Exception, match="B01_TEST_FAIL_AFTER_MATRIX_INSERT"):
            command.upgrade(config, "0084")

        with connect(dsn) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "0083",
            )
            assert connection.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'branches' "
                "AND column_name = 'is_headquarters'"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT branch_id FROM warehouses WHERE id = %s", (test_warehouse_id,)
            ).fetchone() == (None,)
            assert connection.execute(
                "SELECT count(*) FROM branches WHERE company_id = %s", (company_id,)
            ).fetchone()[0] == branch_count_before
            connection.execute(
                "DROP TRIGGER IF EXISTS b01_test_fail_after_matrix_insert ON warehouses"
            )
            connection.execute("DROP FUNCTION IF EXISTS b01_test_fail_after_matrix_insert()")
            if inserted_warehouse:
                connection.execute("DELETE FROM warehouses WHERE id = %s", (test_warehouse_id,))
            connection.commit()
    finally:
        with connect(dsn) as connection:
            connection.execute(
                "DROP TRIGGER IF EXISTS b01_test_fail_after_matrix_insert ON warehouses"
            )
            connection.execute("DROP FUNCTION IF EXISTS b01_test_fail_after_matrix_insert()")
            if inserted_warehouse:
                connection.execute("DELETE FROM warehouses WHERE id = %s", (test_warehouse_id,))
        command.upgrade(config, "head")
