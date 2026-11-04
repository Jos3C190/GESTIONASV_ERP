"""Hands work to the vision worker from the API without ever failing the request.

Capture rows are the source of truth and the worker's reconcile job picks up
whatever this misses, so a Redis hiccup only costs a few seconds of latency.
The pool is separate from the shared Redis client because that one decodes
responses, which would corrupt arq's pickled payloads.
"""

from __future__ import annotations

import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

VLM_QUEUE = "arq:vlm"
VLM_HEALTH_KEY = "erp:vlm:health"

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis:
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await create_pool(
            RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0"),
            default_queue_name=VLM_QUEUE,
        )
    return _pool


async def enqueue_capture(capture_id: uuid.UUID) -> None:
    if not settings.VLM_ENABLED:
        return
    try:
        pool = await _get_pool()
        await pool.enqueue_job(
            "process_capture", str(capture_id), _job_id=f"vlm:{capture_id}", _queue_name=VLM_QUEUE
        )
    except Exception as exc:
        log.warning("vlm_enqueue_failed", error_type=type(exc).__name__)


async def request_warmup() -> None:
    """Start loading the model early; the worker ignores this when it is already up."""
    if not settings.VLM_ENABLED:
        return
    try:
        pool = await _get_pool()
        await pool.enqueue_job("warm_up", _job_id="vlm:warmup", _queue_name=VLM_QUEUE)
    except Exception as exc:
        log.warning("vlm_warmup_failed", error_type=type(exc).__name__)


async def worker_available() -> bool:
    if not settings.VLM_ENABLED:
        return False
    try:
        pool = await _get_pool()
        return bool(await pool.exists(VLM_HEALTH_KEY))
    except Exception as exc:
        log.warning("vlm_health_unavailable", error_type=type(exc).__name__)
        return False
