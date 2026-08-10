"""First-setup database bootstrap for local and review environments.

Docker invokes this stable entrypoint on every ``compose up``.  A durable
marker in ``app_meta`` makes the business seed run only once, so an ordinary
restart never restores records that an administrator intentionally deleted.
Set ``FORCE_SEED=true`` only when the canonical demo dataset must be reconciled
explicitly.
"""

from __future__ import annotations

import asyncio
import os

from app.infrastructure.db.session import session_scope
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


def force_seed_enabled() -> bool:
    """Return whether an operator explicitly requested seed reconciliation."""
    return os.environ.get("FORCE_SEED", "false").strip().casefold() in _TRUTHY


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


async def _write_marker(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES (:key, :value, now())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
            """
        ),
        {"key": SEED_MARKER_KEY, "value": SEED_MARKER_VERSION},
    )


async def bootstrap(*, force: bool | None = None) -> bool:
    """Run the business seed once and return whether it performed work."""
    should_force = force_seed_enabled() if force is None else force
    async with session_scope() as control:
        # A session-level advisory lock prevents concurrent bootstrap jobs from
        # both observing an empty marker and inserting the same business data.
        await control.execute(
            text("SELECT pg_advisory_lock(hashtext(:key))"), {"key": SEED_MARKER_KEY}
        )
        try:
            marker = await control.scalar(
                text("SELECT value FROM app_meta WHERE key = :key"),
                {"key": SEED_MARKER_KEY},
            )
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
        finally:
            await control.execute(
                text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": SEED_MARKER_KEY}
            )


def main() -> None:
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
