"""0128: SMTP propio de la empresa, sus reglas en la base y la guarda del downgrade."""

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

_SETTINGS = (
    "INSERT INTO company_email_settings (company_id, host, port, security, username, "
    "password_encrypted, from_address, last_test_at, last_test_ok, last_test_error) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _settings(
    connection: Connection[tuple[object, ...]],
    *,
    host: str = "smtp.example.com",
    port: int = 587,
    security: str = "starttls",
    username: str | None = "facturacion@example.com",
    password: bytes | None = b"cifrado",
    from_address: str = "facturacion@example.com",
    tested: bool | None = None,
    error: str | None = None,
) -> None:
    connection.execute(
        _SETTINGS,
        (
            uuid.uuid4(),
            host,
            port,
            security,
            username,
            password,
            from_address,
            "2026-11-17T10:00:00-06:00" if tested is not None else None,
            tested,
            error,
        ),
    )


def test_email_settings_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _settings(connection)
        _settings(connection, security="none", port=25, username=None, password=None)
        _settings(connection, tested=True)
        _settings(connection, tested=False, error="Credenciales rechazadas")
        invalid: list[dict[str, object]] = [
            {"port": 0},
            {"port": 70000},
            {"security": "tls"},
            {"host": "  "},
            {"from_address": "sin-arroba"},
            {"username": None},
            {"tested": False},
        ]
        for kwargs in invalid:
            with pytest.raises(errors.CheckViolation):
                _settings(connection, **kwargs)  # type: ignore[arg-type]


def test_downgrade_refuses_when_settings_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _settings(connection)
        with pytest.raises(RuntimeError, match="1 configuraciones"):
            command.downgrade(config, "0127")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM company_email_settings")
        command.downgrade(config, "0127")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
