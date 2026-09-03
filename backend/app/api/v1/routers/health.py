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
from urllib.request import Request, urlopen

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.v1.deps import SessionDep
from app.api.v1.schemas.common import HealthComponent, HealthReport
from app.core.config import settings
from app.infrastructure.malware_scanner import ClamAVScanner
from app.infrastructure.object_storage import S3ObjectStorage
from app.infrastructure.observability import record_gauge
from app.infrastructure.redis_client import get_redis_client, redis_health

router = APIRouter(prefix="/health", tags=["health"])
EXPECTED_SCHEMA_REVISION = "0043"
HTTP_OK_MIN = 200
HTTP_REDIRECTION_MIN = 300


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _observability_health() -> tuple[str, str | None]:
    if not settings.OBSERVABILITY_ENABLED:
        return "disabled", None
    if not settings.OBSERVABILITY_HEALTH_URL:
        return "configured", "OTLP export is configured; no health URL was provided"

    def _check() -> bool:
        request = Request(  # noqa: S310 - URL is operator-controlled configuration
            settings.OBSERVABILITY_HEALTH_URL or "", method="GET"
        )
        with urlopen(  # noqa: S310 - URL is operator-controlled configuration
            request, timeout=settings.OBSERVABILITY_HEALTH_TIMEOUT_SECONDS
        ) as response:
            return HTTP_OK_MIN <= int(response.status) < HTTP_REDIRECTION_MIN

    try:
        available = await asyncio.to_thread(_check)
    except Exception:
        available = False
    return (
        ("ok", None)
        if available
        else ("down", "OpenTelemetry Collector is unavailable; exports are buffered or dropped")
    )


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

    if settings.REDIS_ENABLED:
        redis_ok = await redis_health()
        components.append(
            HealthComponent(
                name="redis",
                status="ok" if redis_ok else "down",
                detail=None
                if redis_ok
                else "Redis is unavailable; rate limits use memory fallback",
            )
        )
        external_ok = external_ok and redis_ok
        if settings.OCR_ENABLED:
            worker_ok = False
            if redis_ok:
                try:
                    worker_ok = bool(await get_redis_client().exists("erp:ocr:health"))
                except Exception:
                    worker_ok = False
            components.append(
                HealthComponent(
                    name="ocr_worker",
                    status="ok" if worker_ok else "down",
                    detail=None if worker_ok else "OCR worker heartbeat is unavailable",
                )
            )
            external_ok = external_ok and worker_ok
        else:
            components.append(HealthComponent(name="ocr_worker", status="disabled"))
    else:
        components.extend(
            [
                HealthComponent(name="redis", status="disabled"),
                HealthComponent(name="ocr_worker", status="disabled"),
            ]
        )

    collector_status, collector_detail = await _observability_health()
    components.append(
        HealthComponent(name="otel_collector", status=collector_status, detail=collector_detail)
    )
    collector_ok = collector_status in {"ok", "configured", "disabled"}

    overall = (
        "ok"
        if db_status == "ok" and schema_status == "ok" and external_ok and collector_ok
        else "degraded"
    )
    for component in components:
        record_gauge(
            "erp.component.health",
            1 if component.status in {"ok", "configured", "disabled"} else 0,
            attributes={"component": component.name},
        )
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
