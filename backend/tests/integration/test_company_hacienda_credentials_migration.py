"""0129: credenciales de Hacienda de la empresa, sus reglas en la base y la guarda del downgrade."""

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

_ROW = (
    "INSERT INTO company_hacienda_credentials (company_id, api_password_encrypted, "
    "private_key_password_encrypted, certificate_encrypted, certificate_sha256, certificate_nit, "
    "last_test_at, last_test_ok, last_test_error) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _row(
    connection: Connection[tuple[object, ...]],
    *,
    nit: str = "06142803901121",
    sha: str = "a" * 64,
    tested: bool | None = None,
    error: str | None = None,
) -> None:
    connection.execute(
        _ROW,
        (
            uuid.uuid4(),
            b"api",
            b"pri",
            b"crt",
            sha,
            nit,
            "2026-11-17T10:00:00-06:00" if tested is not None else None,
            tested,
            error,
        ),
    )


def test_credentials_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _row(connection)
        _row(connection, nit="012345678")
        _row(connection, tested=True)
        _row(connection, tested=False, error="Credenciales rechazadas")
        for kwargs in (
            {"nit": "0614-2803"},
            {"sha": "A" * 64},
            {"sha": "abc"},
            {"tested": False},
        ):
            with pytest.raises(errors.CheckViolation):
                _row(connection, **kwargs)  # type: ignore[arg-type]


def test_downgrade_refuses_when_credentials_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _row(connection)
        with pytest.raises(RuntimeError, match="1 credenciales"):
            command.downgrade(config, "0128")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM company_hacienda_credentials")
        command.downgrade(config, "0128")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
