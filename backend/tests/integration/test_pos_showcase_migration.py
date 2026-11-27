"""0147: vitrina por sucursal, unidad abierta, conteo de merma y guarda de la ubicación."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import Connection, connect, errors

pytestmark = pytest.mark.integration


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _location(connection: Connection, warehouse: uuid.UUID, code: str, kind: str) -> uuid.UUID:
    [location] = connection.execute(
        "INSERT INTO locations (id, warehouse_id, code, aisle, rack, level, position, "
        "location_type, created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, 'V', '1', '1', "
        "%s, %s, now(), now()) RETURNING id",
        (warehouse, code, code, kind),
    ).fetchone()
    return location


def test_showcase_schema_and_guards(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            company, branch, warehouse = connection.execute(
                "SELECT company_id, branch_id, id FROM warehouses WHERE deleted_at IS NULL "
                "ORDER BY created_at LIMIT 1"
            ).fetchone()
            [other_branch] = connection.execute(
                "SELECT id FROM branches WHERE company_id = %s AND id <> %s LIMIT 1",
                (company, branch),
            ).fetchone()
            [user] = connection.execute("SELECT id FROM users LIMIT 1").fetchone()
            showcase_location = _location(connection, warehouse, "VIT-TEST", "showcase")
            insert = (
                "INSERT INTO pos_showcases (company_id, branch_id, warehouse_id, location_id, "
                "created_by_id) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            )
            with pytest.raises(errors.ForeignKeyViolation):  # bodega de otra sucursal
                connection.execute(
                    insert, (company, other_branch, warehouse, showcase_location, user)
                )
            [showcase] = connection.execute(
                insert, (company, branch, warehouse, showcase_location, user)
            ).fetchone()
            second = _location(connection, warehouse, "VIT-TEST-2", "showcase")
            with pytest.raises(errors.UniqueViolation):  # una vitrina por sucursal
                connection.execute(insert, (company, branch, warehouse, second, user))

            # La ubicación de una vitrina en uso conserva su tipo y no se retira.
            for change in (
                "location_type = 'standard'",
                "is_active = false",
                "lifecycle_status = 'retired'",
                "deleted_at = now()",
            ):
                with pytest.raises(errors.CheckViolation):
                    connection.execute(
                        f"UPDATE locations SET {change} WHERE id = %s",  # noqa: S608
                        (showcase_location,),
                    )
            standard = _location(connection, warehouse, "STD-TEST", "standard")
            with pytest.raises(errors.CheckViolation):  # una ubicación común no se vuelve vitrina
                connection.execute(
                    "UPDATE locations SET location_type = 'showcase' WHERE id = %s", (standard,)
                )
            connection.execute(
                "UPDATE locations SET notes = 'Vitrina principal' WHERE id = %s",
                (showcase_location,),
            )

            # Conteo: contar de más no crea existencia; la merma pide motivo; solo se agrega.
            item = uuid.uuid4()  # sin claves foráneas: solo se prueban las reglas
            [count] = connection.execute(
                "INSERT INTO pos_showcase_counts (company_id, showcase_id, branch_id, number, "
                "counted_by_id, idempotency_key) VALUES (%s, %s, %s, 1, %s, 'conteo-01') RETURNING id",
                (company, showcase, branch, user),
            ).fetchone()
            line = "INSERT INTO pos_showcase_count_lines VALUES (%s, %s, %s, %s, %s, %s, %s)"
            connection.execute("SET session_replication_role = replica")
            with pytest.raises(errors.CheckViolation):
                connection.execute(line, (company, count, item, 5, 6, -1, None))
            with pytest.raises(errors.CheckViolation):
                connection.execute(line, (company, count, item, 5, 3, 2, None))
            connection.execute(line, (company, count, item, 5, 3, 2, "Pan aplastado"))
            connection.execute("SET session_replication_role = origin")
            with pytest.raises(errors.CheckViolation, match="append-only"):
                connection.execute("UPDATE pos_showcase_count_lines SET reason = 'x'")
            # Una unidad abierta siempre dice quién la abrió.
            [definition] = connection.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_inventory_handling_units_opened'"
            ).fetchone()
            assert "opened_at IS NULL" in definition
            assert "opened_by_id IS NULL" in definition
        with pytest.raises(RuntimeError, match="1 vitrinas"):
            command.downgrade(config, "0146")
        rebuild_test_database(seed=False)
        command.downgrade(config, "0146")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
