"""0146: cajas, turnos y efectivo del punto de venta; permisos, roles y guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.application.rbac.catalogue import (
    ALL_PERMISSION_CODES,
    POS_CASHIER_PERMISSIONS,
    POS_SUPERVISOR_PERMISSIONS,
)
from psycopg import Connection, connect, errors

pytestmark = pytest.mark.integration

_REGISTER = (
    "INSERT INTO pos_registers (company_id, branch_id, establishment_id, point_of_sale_id, code, "
    "name, created_by_id, updated_by_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_SHIFT = (
    "INSERT INTO pos_shifts (company_id, branch_id, register_id, cashier_id, number, "
    "opening_float, idempotency_key) VALUES (%s, %s, %s, %s, %s, 50, %s) RETURNING id"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _points_of_sale(connection: Connection) -> list[tuple[uuid.UUID, ...]]:
    """Crea un establecimiento y un punto de venta en dos sucursales de la misma empresa."""
    branches = connection.execute(
        "SELECT company_id, id FROM branches WHERE deleted_at IS NULL "
        "AND company_id = (SELECT company_id FROM branches WHERE deleted_at IS NULL "
        "GROUP BY company_id HAVING count(*) >= 2 LIMIT 1) ORDER BY code LIMIT 2"
    ).fetchall()
    assert len(branches) == 2, "La siembra debe traer una empresa con dos sucursales"
    result = []
    for index, (company, branch) in enumerate(branches, start=1):
        [establishment] = connection.execute(
            "INSERT INTO fiscal_establishments (id, company_id, branch_id, establishment_type, "
            "code, created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, '01', %s, now(), "
            "now()) RETURNING id",
            (company, branch, f"S{900 + index}"),
        ).fetchone()
        [point] = connection.execute(
            "INSERT INTO fiscal_points_of_sale (id, company_id, establishment_id, code, name, "
            "created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, 'P001', 'Caja', now(), "
            "now()) RETURNING id",
            (company, establishment),
        ).fetchone()
        result.append((company, branch, establishment, point))
    return result


def _users(connection: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    rows = connection.execute("SELECT id FROM users ORDER BY created_at LIMIT 2").fetchall()
    assert len(rows) == 2
    return rows[0][0], rows[1][0]


def test_pos_schema_roles_and_guard(rebuild_test_database: Callable[..., None]) -> None:  # noqa: PLR0915
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            (company, branch_a, est_a, pos_a), (_, branch_b, est_b, pos_b) = _points_of_sale(
                connection
            )
            cashier, supervisor = _users(connection)

            # La caja no puede usar el punto de venta ni el establecimiento de otra sucursal.
            with pytest.raises(errors.ForeignKeyViolation):
                connection.execute(
                    _REGISTER,
                    (company, branch_a, est_a, pos_b, "CAJA-X", "Caja", cashier, cashier),
                )
            with pytest.raises(errors.ForeignKeyViolation):
                connection.execute(
                    _REGISTER,
                    (company, branch_a, est_b, pos_b, "CAJA-X", "Caja", cashier, cashier),
                )
            with pytest.raises(errors.CheckViolation):  # código en minúsculas
                connection.execute(
                    _REGISTER,
                    (company, branch_a, est_a, pos_a, "caja-1", "Caja", cashier, cashier),
                )
            [register] = connection.execute(
                _REGISTER, (company, branch_a, est_a, pos_a, "CAJA-01", "Caja 1", cashier, cashier)
            ).fetchone()
            with pytest.raises(errors.UniqueViolation):  # un punto de venta, una caja
                connection.execute(
                    _REGISTER,
                    (company, branch_a, est_a, pos_a, "CAJA-02", "Caja 2", cashier, cashier),
                )

            # Un turno sin cerrar por caja y por cajero; nunca en otra sucursal.
            with pytest.raises(errors.ForeignKeyViolation):
                connection.execute(_SHIFT, (company, branch_b, register, cashier, 1, "turno-xx-1"))
            [shift] = connection.execute(
                _SHIFT, (company, branch_a, register, cashier, 1, "turno-ok-1")
            ).fetchone()
            with pytest.raises(errors.UniqueViolation):
                connection.execute(
                    _SHIFT, (company, branch_a, register, supervisor, 2, "turno-ok-2")
                )

            # Movimientos: motivo obligatorio, nunca se editan.
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    "INSERT INTO pos_cash_movements (company_id, shift_id, kind, amount, reason, "
                    "created_by_id, idempotency_key) VALUES (%s, %s, 'cash_out', 5, 'x', %s, "
                    "'movimiento-1')",
                    (company, shift, cashier),
                )
            connection.execute(
                "INSERT INTO pos_cash_movements (company_id, shift_id, kind, amount, reason, "
                "created_by_id, idempotency_key) VALUES (%s, %s, 'cash_in', 5, 'Cambio de monedas', "
                "%s, 'movimiento-2')",
                (company, shift, cashier),
            )
            with pytest.raises(errors.CheckViolation, match="append-only"):
                connection.execute("UPDATE pos_cash_movements SET amount = 6")

            # Denominaciones válidas en USD.
            [count] = connection.execute(
                "INSERT INTO pos_shift_counts (company_id, shift_id, kind, sequence, cash_total, "
                "counted_by_id) VALUES (%s, %s, 'opening', 1, 50, %s) RETURNING id",
                (company, shift, cashier),
            ).fetchone()
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    "INSERT INTO pos_shift_count_lines VALUES (%s, %s, 'bill', 3, 1)",
                    (company, count),
                )
            connection.execute(
                "INSERT INTO pos_shift_count_lines VALUES (%s, %s, 'bill', 20, 2)", (company, count)
            )

            # Cierre: el aprobador no es el cajero, la diferencia cuadra y lo cerrado es inmutable.
            connection.execute(
                "UPDATE pos_shifts SET status = 'counted', counted_at = now(), counted_cash = 55, "
                "declared_card = 0, declared_transfer = 0 WHERE id = %s",
                (shift,),
            )
            close = (
                "UPDATE pos_shifts SET status = 'closed', closed_at = now(), approved_by_id = %s, "
                "expected_cash = 55, cash_difference = %s, expected_card = 0, "
                "expected_transfer = 0, retained_float = 50, cash_to_deposit = 5 WHERE id = %s"
            )
            with pytest.raises(errors.CheckViolation):
                connection.execute(close, (cashier, 0, shift))
            with pytest.raises(errors.CheckViolation):
                connection.execute(close, (supervisor, 1, shift))
            connection.execute(close, (supervisor, 0, shift))
            with pytest.raises(errors.CheckViolation, match="immutable"):
                connection.execute(
                    "UPDATE pos_shifts SET approval_notes = 'x' WHERE id = %s", (shift,)
                )

            # Permisos y plantillas de rol, iguales al catálogo.
            codes = {
                row[0]
                for row in connection.execute(
                    "SELECT code FROM permissions WHERE module = 'pos'"
                ).fetchall()
            }
            assert codes == {code for code in ALL_PERMISSION_CODES if code.startswith("pos:")}
            for role, expected in (
                ("CAJERO", POS_CASHIER_PERMISSIONS),
                ("SUPERVISOR_TIENDA", POS_SUPERVISOR_PERMISSIONS),
            ):
                granted = {
                    row[0]
                    for row in connection.execute(
                        "SELECT p.code FROM roles r JOIN role_permissions rp ON rp.role_id = r.id "
                        "JOIN permissions p ON p.id = rp.permission_id "
                        "WHERE r.name = %s AND r.company_id IS NULL AND r.is_system",
                        (role,),
                    ).fetchall()
                }
                assert granted == set(expected)

        with pytest.raises(RuntimeError, match="1 cajas o PIN"):
            command.downgrade(config, "0145")
        # Sin datos del punto de venta, la migración baja y vuelve a subir.
        rebuild_test_database(seed=False)
        command.downgrade(config, "0145")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
