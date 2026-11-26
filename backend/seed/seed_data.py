"""First-setup database bootstrap for local and review environments.

Docker invokes this stable entrypoint on every ``compose up``.  A durable
marker in ``app_meta`` makes the business seed run only once, so an ordinary
restart never restores records that an administrator intentionally deleted.
Set ``FORCE_SEED=true`` only when the canonical demo dataset must be reconciled
explicitly.

After the base seed, the entrypoint runs follow-up steps once each, with their
own marker, so a database bootstrapped before a step existed still gets it on
its next start:

* the correction of the harina suave units (bought by the 50 lb sack);
* the fleet (``seed_grupo_lorena_fleet``). Its marker is written only once every
  vehicle and driver has its documents; while the document storage or the
  antivirus is unavailable the vehicles are assigned with a recorded exception
  and the next start retries the documents;
* the DTE issuer in simulated mode (``seed_grupo_lorena_fiscal``): fiscal profile,
  economic activities, one establishment per branch with its point of sale and the
  documents a bakery issues;
* the demonstration customers with fiscal data and the generic «Consumidor final» of every
  branch (``seed_grupo_lorena_customers``);
* the published privacy notice of the company (``seed_grupo_lorena_privacy``);
* the «Mostrador» and «Mayoreo» price lists with their prices
  (``seed_grupo_lorena_price_lists``);
* target margins, volume tiers, a customer discount and discount limits per role
  (``seed_grupo_lorena_discounts``);
* the demonstration operation (``seed_grupo_lorena_operations``), which creates
  purchase and inventory documents, only with ``SEED_DEMO_OPERATIONS=true`` and
  never when ``ENVIRONMENT=production``.

A failing follow-up step is reported and retried on the next start; it never
undoes the base bootstrap nor stops the stack.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.infrastructure.db.session import session_scope
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from seed.seed_catalog import ensure_soft_flour_units
from seed.seed_catalog import main as seed_catalog
from seed.seed_grupo_lorena import (
    BRANCHES,
    COMPANY_ID,
    DEPARTMENTS,
    EMPLOYEES,
)
from seed.seed_grupo_lorena import (
    seed as seed_grupo_lorena,
)

SEED_MARKER_KEY = "seed.grupo_lorena.initialized"
SEED_MARKER_VERSION = "2026-08-09-v1"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _flag(name: str) -> bool:
    return os.environ.get(name, "false").strip().casefold() in _TRUTHY


def force_seed_enabled() -> bool:
    """Return whether an operator explicitly requested seed reconciliation."""
    return _flag("FORCE_SEED")


def demo_operations_enabled() -> bool:
    """The demonstration operation creates business documents: opt-in, never in production."""
    production = os.environ.get("ENVIRONMENT", "development").strip().casefold() == "production"
    return _flag("SEED_DEMO_OPERATIONS") and not production


def demo_sales_enabled() -> bool:
    """Un mes de ventas de demostración (V9b): opcional y nunca en producción."""
    production = os.environ.get("ENVIRONMENT", "development").strip().casefold() == "production"
    return _flag("SEED_DEMO_SALES") and not production


async def _soft_flour_units() -> bool:
    async with session_scope() as session:
        for note in await ensure_soft_flour_units(session):
            print(f"[seed] {note}")
    return True


async def _fleet() -> bool:
    from seed.seed_grupo_lorena_fleet import seed as seed_fleet

    return await seed_fleet()


async def _fiscal_issuer() -> bool:
    from seed.seed_grupo_lorena_fiscal import seed as seed_fiscal

    return await seed_fiscal()


async def _customers() -> bool:
    from seed.seed_grupo_lorena_customers import seed as seed_customers

    return await seed_customers()


async def _privacy_notice() -> bool:
    from seed.seed_grupo_lorena_privacy import seed as seed_privacy

    return await seed_privacy()


async def _price_lists() -> bool:
    from seed.seed_grupo_lorena_price_lists import seed as seed_price_lists

    return await seed_price_lists()


async def _sales_discounts() -> bool:
    from seed.seed_grupo_lorena_discounts import seed as seed_discounts

    return await seed_discounts()


async def _operations() -> bool:
    from seed.seed_grupo_lorena_operations import seed as seed_operations

    await seed_operations()
    return True


async def _sales_month() -> bool:
    from seed.seed_grupo_lorena_sales import seed as seed_sales

    report = await seed_sales()
    for error in report.errors:
        print(f"[seed] ventas de demostración: {error}")
    return not report.errors


@dataclass(frozen=True, slots=True)
class FollowUp:
    """A step after the base seed; ``run`` returns False to be retried next time."""

    key: str
    version: str
    run: Callable[[], Awaitable[bool]]
    enabled: Callable[[], bool] = lambda: True


FOLLOW_UPS: tuple[FollowUp, ...] = (
    FollowUp("seed.catalog.soft_flour_units", "2026-11-14-v1", _soft_flour_units),
    FollowUp("seed.grupo_lorena.fleet", "2026-11-14-v1", _fleet),
    FollowUp("seed.grupo_lorena.fiscal_issuer", "2026-11-15-v1", _fiscal_issuer),
    FollowUp("seed.grupo_lorena.customers", "2026-11-16-v1", _customers),
    FollowUp("seed.grupo_lorena.privacy_notice", "2026-11-16-v1", _privacy_notice),
    FollowUp("seed.grupo_lorena.price_lists", "2026-11-16-v2", _price_lists),
    FollowUp("seed.grupo_lorena.sales_discounts", "2026-11-16-v1", _sales_discounts),
    FollowUp("seed.grupo_lorena.operations", "2026-11-14-v1", _operations, demo_operations_enabled),
    FollowUp("seed.grupo_lorena.sales_month", "2026-11-26-v1", _sales_month, demo_sales_enabled),
)


async def _legacy_seed_is_complete(session: AsyncSession) -> bool:
    """Recognise databases seeded before the durable marker was introduced."""
    result = await session.scalar(
        text(
            """
            SELECT
                EXISTS (SELECT 1 FROM companies WHERE id = :company_id)
                AND (SELECT count(*) FROM branches WHERE company_id = :company_id) >= :branches
                AND (SELECT count(*) FROM departments WHERE company_id = :company_id) >= :departments
                AND (SELECT count(*) FROM employees WHERE company_id = :company_id) >= :employees
                AND (SELECT count(*) FROM categories WHERE company_id = :company_id) >= 4
                AND (SELECT count(*) FROM products WHERE company_id = :company_id) >= 2
                AND (SELECT count(*) FROM suppliers WHERE company_id = :company_id) >= 2
            """
        ),
        {
            "company_id": COMPANY_ID,
            "branches": len(BRANCHES),
            "departments": len(DEPARTMENTS),
            "employees": len(EMPLOYEES),
        },
    )
    return bool(result)


async def _read_marker(session: AsyncSession, key: str) -> str | None:
    value = await session.scalar(text("SELECT value FROM app_meta WHERE key = :key"), {"key": key})
    return None if value is None else str(value)


async def _write_marker(
    session: AsyncSession, key: str = SEED_MARKER_KEY, value: str = SEED_MARKER_VERSION
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES (:key, :value, now())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
            """
        ),
        {"key": key, "value": value},
    )


async def _base_seed(control: AsyncSession, should_force: bool) -> bool:
    marker = await _read_marker(control, SEED_MARKER_KEY)
    if marker is not None and not should_force:
        print(f"[seed] Bootstrap already completed ({marker}); skipping.")
        return False

    if marker is None and not should_force and await _legacy_seed_is_complete(control):
        await _write_marker(control)
        print("[seed] Existing Grupo Lorena dataset adopted; skipping reconciliation.")
        return False

    await seed_grupo_lorena()
    await seed_catalog()
    await _write_marker(control)
    print(f"[seed] Bootstrap completed ({SEED_MARKER_VERSION}).")
    return True


async def _follow_ups(control: AsyncSession, should_force: bool) -> None:
    for step in FOLLOW_UPS:
        if not step.enabled():
            continue
        marker = await _read_marker(control, step.key)
        if marker is not None and not should_force:
            continue
        try:
            done = await step.run()
        except Exception as exc:  # reported and retried next time; the base seed stays
            print(f"[seed] {step.key} failed ({type(exc).__name__}: {exc}); will retry.")
            continue
        if done:
            await _write_marker(control, step.key, step.version)
            print(f"[seed] {step.key} completed ({step.version}).")
        else:
            print(f"[seed] {step.key} incomplete; will retry on the next start.")


async def bootstrap(*, force: bool | None = None, follow_ups: bool = False) -> bool:
    """Run the business seed once and return whether it performed work.

    ``follow_ups`` also runs the follow-up steps (the Compose entrypoint does);
    the test suite's canonical database keeps only the base seed.
    """
    should_force = force_seed_enabled() if force is None else force
    async with session_scope() as control:
        # A session-level advisory lock prevents concurrent bootstrap jobs from
        # both observing an empty marker and inserting the same business data.
        await control.execute(
            text("SELECT pg_advisory_lock(hashtext(:key))"), {"key": SEED_MARKER_KEY}
        )
        try:
            # The lock lives on this session's connection: no commit until the end,
            # or the connection could return to the pool while still holding it.
            performed = await _base_seed(control, should_force)
            if follow_ups:
                await _follow_ups(control, should_force)
            return performed
        finally:
            await control.execute(
                text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": SEED_MARKER_KEY}
            )


def main() -> None:
    asyncio.run(bootstrap(follow_ups=True))


if __name__ == "__main__":
    main()
