"""Health endpoints.

- `/health/live`  : process is alive (no I/O). For orchestrator liveness probes.
- `/health/ready` : can serve requests (DB plus enabled external services).
- `/health`       : same as ready, plus component breakdown.

These are deliberately NOT under `/api/v1` so they sit at the root and match
typical probe expectations. They are also registered in `main.py` separately.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.v1.deps import SessionDep
from app.api.v1.schemas.common import HealthComponent, HealthReport
from app.core.config import settings
from app.infrastructure.malware_scanner import ClamAVScanner
from app.infrastructure.object_storage import S3ObjectStorage

router = APIRouter(prefix="/health", tags=["health"])
EXPECTED_SCHEMA_REVISION = "0041"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/live", summary="Liveness probe", status_code=status.HTTP_200_OK)
async def live() -> HealthReport:
    return HealthReport(
        status="ok",
        version=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=_now(),
        components=[HealthComponent(name="process", status="ok")],
    )


@router.get("/ready", summary="Readiness probe", status_code=status.HTTP_200_OK)
async def ready(session: SessionDep) -> HealthReport:
    db_status = "ok"
    detail: str | None = None
    schema_status = "unknown"
    schema_detail: str | None = None
    try:
        result = await session.execute(text("SELECT 1"))
        _ = result.scalar_one()
        revision = (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
        schema_status = "ok" if revision == EXPECTED_SCHEMA_REVISION else "outdated"
        if schema_status != "ok":
            schema_detail = f"Expected {EXPECTED_SCHEMA_REVISION}; found {revision}"
    except Exception as exc:
        db_status = "down"
        detail = str(exc)[:200]
        schema_status = "unknown"

    components = [
        HealthComponent(name="database", status=db_status, detail=detail),
        HealthComponent(name="schema", status=schema_status, detail=schema_detail),
    ]
    external_ok = True
    if settings.OBJECT_STORAGE_ENABLED:
        storage = S3ObjectStorage(settings)
        scanner = ClamAVScanner(
            settings.CLAMAV_HOST,
            settings.CLAMAV_PORT,
            settings.CLAMAV_TIMEOUT_SECONDS,
        )
        storage_ok, scanner_ok = await asyncio.gather(storage.health(), scanner.health())
        components.extend(
            [
                HealthComponent(
                    name="rustfs",
                    status="ok" if storage_ok else "down",
                    detail=None if storage_ok else "Object storage is unavailable",
                ),
                HealthComponent(
                    name="clamav",
                    status="ok" if scanner_ok else "down",
                    detail=None if scanner_ok else "Antivirus scanner is unavailable",
                ),
            ]
        )
        external_ok = storage_ok and scanner_ok
    else:
        components.extend(
            [
                HealthComponent(name="rustfs", status="disabled"),
                HealthComponent(name="clamav", status="disabled"),
            ]
        )

    overall = "ok" if db_status == "ok" and schema_status == "ok" and external_ok else "degraded"
    return HealthReport(
        status=overall,
        version=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=_now(),
        components=components,
    )


@router.get("", summary="Full health report", status_code=status.HTTP_200_OK)
async def health(session: SessionDep) -> HealthReport:
    return await ready(session)
