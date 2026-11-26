"""V6a: dos cajeros que abren la misma caja a la vez y el bloqueo del PIN de supervisor.

La apertura bloquea la fila de la caja y los índices únicos son el respaldo: de dos aperturas
simultáneas solo una gana. El intento fallido de PIN se guarda en su propia transacción, así que
cuenta aunque la petición que lo usó se revierta.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.application.pos.use_cases import PosUseCases
from app.core.exceptions import ConflictError
from app.core.security import hash_password, verify_password
from app.domain.entities.pos import DenominationCount, DenominationForm, ShiftStatus
from app.domain.ports.pos_repository import PinCheck, RegisterData
from app.infrastructure.db import session as db_session
from app.infrastructure.repositories.pos_repository import (
    SqlAlchemyPinAttempts,
    SqlAlchemyPosRepository,
)
from sqlalchemy import text

pytestmark = pytest.mark.integration

FIFTY = [
    DenominationCount(DenominationForm.BILL, Decimal("20"), 2),
    DenominationCount(DenominationForm.BILL, Decimal("10"), 1),
]


class _NoPins:
    async def verify(self, user_id: uuid.UUID, pin: str) -> PinCheck:  # pragma: no cover
        raise AssertionError("Esta prueba no autoriza con PIN")


def _use_cases(session: object) -> PosUseCases:
    return PosUseCases(
        SqlAlchemyPosRepository(session),  # type: ignore[arg-type]
        _NoPins(),
        hash_pin=hash_password,
        verify_password=verify_password,
    )


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Empresa, caja con su punto de venta fiscal y dos usuarios distintos."""
    async with db_session.async_session_factory() as session, session.begin():
        company, branch = (
            await session.execute(
                text(
                    "SELECT company_id, id FROM branches WHERE deleted_at IS NULL AND is_active "
                    "ORDER BY created_at LIMIT 1"
                )
            )
        ).one()
        establishment = await session.scalar(
            text("SELECT id FROM fiscal_establishments WHERE company_id = :c AND branch_id = :b"),
            {"c": company, "b": branch},
        )
        if establishment is None:
            establishment = await session.scalar(
                text(
                    "INSERT INTO fiscal_establishments (id, company_id, branch_id, "
                    "establishment_type, code, created_at, updated_at) VALUES (gen_random_uuid(), "
                    ":c, :b, '01', 'S950', now(), now()) RETURNING id"
                ),
                {"c": company, "b": branch},
            )
        point = await session.scalar(
            text(
                "INSERT INTO fiscal_points_of_sale (id, company_id, establishment_id, code, name, "
                "created_at, updated_at) VALUES (gen_random_uuid(), :c, :e, 'P950', 'Caja de prueba', "
                "now(), now()) RETURNING id"
            ),
            {"c": company, "e": establishment},
        )
        users = (
            (await session.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 2")))
            .scalars()
            .all()
        )
        register = await _use_cases(session).create_register(
            company,
            users[0],
            point,
            RegisterData(
                code="CAJA-950",
                name="Caja de prueba",
                opening_float=Decimal("50"),
                cash_out_approval_threshold=Decimal("20"),
                cash_drawer_limit=None,
            ),
        )
    return company, register.id, users[0], users[1]


async def _open(company: uuid.UUID, register: uuid.UUID, cashier: uuid.UUID) -> object:
    try:
        async with db_session.async_session_factory() as session, session.begin():
            shift = await _use_cases(session).open_shift(
                company, cashier, register, FIFTY, None, f"apertura-{uuid.uuid4()}"
            )
            await asyncio.sleep(0.2)  # mantiene el bloqueo mientras la otra apertura espera
            return shift
    except ConflictError as error:
        return error


def test_concurrent_openings_and_pin_lockout(rebuild_test_database: Callable[..., None]) -> None:
    rebuild_test_database()
    try:
        asyncio.run(_scenario())
    finally:
        asyncio.run(db_session.dispose_engine())
        rebuild_test_database()


async def _scenario() -> None:
    await db_session.dispose_engine()
    company, register, first, second = await _setup()

    results = await asyncio.gather(
        _open(company, register, first), _open(company, register, second)
    )
    errors = [item for item in results if isinstance(item, ConflictError)]
    opened = [item for item in results if not isinstance(item, ConflictError)]
    assert len(opened) == 1, results
    assert len(errors) == 1, results
    assert errors[0].code in {"pos_register_busy", "pos_shift_conflict"}
    assert opened[0].status is ShiftStatus.OPEN  # type: ignore[attr-defined]
    assert opened[0].opening_float == Decimal("50.00")  # type: ignore[attr-defined]

    # PIN: cinco fallos bloquean 15 minutos; el bloqueo vence y el PIN correcto vuelve a valer.
    async with db_session.async_session_factory() as session, session.begin():
        await SqlAlchemyPosRepository(session).set_pin(second, hash_password("482915"))
    now = datetime.now(UTC)
    clock = {"now": now}
    pins = SqlAlchemyPinAttempts(
        db_session.async_session_factory, verify_password, lambda: clock["now"]
    )
    for attempt in range(1, 6):
        check = await pins.verify(second, "000000")
        assert not check.ok
        assert check.remaining_attempts == 5 - attempt
    assert check.locked_until is not None
    locked = await pins.verify(second, "482915")
    assert not locked.ok  # bloqueado aunque sea correcto
    assert locked.locked_until is not None
    clock["now"] = now + timedelta(minutes=16)
    unlocked = await pins.verify(second, "482915")
    assert unlocked.ok
    assert unlocked.remaining_attempts == 5
    missing = await pins.verify(first, "482915")
    assert not missing.configured
