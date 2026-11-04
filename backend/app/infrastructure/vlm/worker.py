"""Extracts proposed values from capture photos using the on-demand vision model."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from arq.worker import Retry
from PIL import Image, ImageOps
from sqlalchemy import case, func, select, update

from app.application.document_capture.profiles import PROFILES, CaptureProfile
from app.core.config import settings
from app.core.exceptions import InfrastructureError
from app.core.logging import configure_logging, get_logger
from app.domain.ports.vision_extractor import VisionExtractionError, VisionExtractor
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.object_storage import S3ObjectStorage
from app.infrastructure.observability import (
    initialize_observability,
    operation_span,
    record_counter,
    record_gauge,
    record_histogram,
    shutdown_observability,
)
from app.infrastructure.vlm.client import LlamaServerExtractor
from app.infrastructure.vlm.job_queue import VLM_HEALTH_KEY, VLM_QUEUE
from app.infrastructure.vlm.supervisor import GpuBusyError, ModelStartError, ModelSupervisor

log = get_logger(__name__)

_GPU_BUSY_RETRY_SECONDS = 15
_ENGINE_RETRY_SECONDS = 10
_REAPER_SECONDS = 5
_RECONCILE_BATCH = 20
_MAX_SOURCE_PIXELS = 40_000_000
_JPEG_QUALITY = 88

Image.MAX_IMAGE_PIXELS = _MAX_SOURCE_PIXELS


def prepare_image(source: Path, destination: Path, *, max_edge: int) -> None:
    """Scale the long edge to ``max_edge``; 1280 px gave the best accuracy for its latency."""
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    ratio = max_edge / max(image.size)
    image = image.resize(
        (round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS
    )
    image.save(destination, "JPEG", quality=_JPEG_QUALITY)


def _sides_needing_work(capture: DocumentCaptureModel) -> list[tuple[str, uuid.UUID]]:
    done = capture.extracted or {}
    sides = (("front", capture.front_document_id), ("back", capture.back_document_id))
    return [
        (side, document_id)
        for side, document_id in sides
        if document_id is not None and (done.get(side) or {}).get("document_id") != str(document_id)
    ]


async def _active_asset(session: Any, document_id: uuid.UUID) -> DocumentAssetModel | None:
    asset: DocumentAssetModel | None = await session.get(DocumentAssetModel, document_id)
    return asset if asset is not None and asset.status == "active" else None


async def _read_side(
    extractor: VisionExtractor,
    storage: S3ObjectStorage,
    profile: CaptureProfile,
    side: str,
    asset: DocumentAssetModel,
) -> dict[str, str | None]:
    spec = profile.sides[side]
    with tempfile.TemporaryDirectory(prefix="erp-vlm-") as directory:
        source = Path(directory) / "source"
        prepared = Path(directory) / "prepared.jpg"
        await storage.download_to(asset.object_key, source, settings.DOCUMENT_MAX_BYTES)
        checksum = await asyncio.to_thread(lambda: hashlib.sha256(source.read_bytes()).hexdigest())
        if checksum != asset.checksum_sha256:
            raise VisionExtractionError("checksum_mismatch")
        try:
            await asyncio.to_thread(prepare_image, source, prepared, max_edge=settings.VLM_MAX_EDGE)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise VisionExtractionError("image_unreadable") from exc
        started = datetime.now(UTC)
        async with asyncio.timeout(settings.VLM_INFERENCE_TIMEOUT_SECONDS):
            values = await extractor.extract(
                prepared,
                prompt=spec.prompt(),
                response_format=spec.response_format(),
                keys=tuple(spec.fields),
            )
        record_histogram(
            "erp.vlm.inference.duration",
            (datetime.now(UTC) - started).total_seconds() * 1000,
            attributes={"variant": side},
        )
        return values


async def _claim(capture_id: uuid.UUID, now: datetime) -> bool:
    async with session_scope() as session:
        claimed = await session.execute(
            update(DocumentCaptureModel)
            .where(
                DocumentCaptureModel.id == capture_id,
                DocumentCaptureModel.status == "pending",
                DocumentCaptureModel.attempts < settings.VLM_MAX_ATTEMPTS,
            )
            .values(
                status="processing",
                attempts=DocumentCaptureModel.attempts + 1,
                started_at=now,
                failure_code=None,
            )
        )
        return bool(claimed.rowcount)  # type: ignore[attr-defined]


async def _mark_failure(capture_id: uuid.UUID, code: str) -> str:
    """Return to the queue while attempts remain. Only a row still processing is touched."""
    async with session_scope() as session:
        capture = await session.get(DocumentCaptureModel, capture_id, with_for_update=True)
        if capture is None or capture.status != "processing":
            return "ignored"
        capture.failure_code = code
        capture.started_at = None
        capture.status = "failed" if capture.attempts >= settings.VLM_MAX_ATTEMPTS else "pending"
        return capture.status


async def _store(
    capture_id: uuid.UUID,
    side: str,
    document_id: uuid.UUID,
    values: dict[str, str | None],
) -> bool:
    """Save one side unless the capture changed meanwhile: a retake or confirm wins."""
    async with session_scope() as session:
        capture = await session.get(DocumentCaptureModel, capture_id, with_for_update=True)
        current = None
        if capture is not None:
            current = capture.front_document_id if side == "front" else capture.back_document_id
        if capture is None or capture.status != "processing" or current != document_id:
            return False
        capture.extracted = {
            **(capture.extracted or {}),
            side: {"document_id": str(document_id), "values": values},
        }
        return True


async def _finish(capture_id: uuid.UUID) -> bool:
    """Close the attempt; a photo that arrived during it sends the capture back to the queue."""
    async with session_scope() as session:
        capture = await session.get(DocumentCaptureModel, capture_id, with_for_update=True)
        if capture is None or capture.status != "processing":
            return False
        capture.started_at = None
        if _sides_needing_work(capture):
            capture.status = "pending"
            capture.attempts = 0
            return False
        capture.status = "ready"
        return True


async def _load_work(
    capture_id: uuid.UUID,
) -> tuple[CaptureProfile, list[tuple[str, uuid.UUID, DocumentAssetModel]]] | None:
    async with session_scope() as session:
        capture = await session.get(DocumentCaptureModel, capture_id)
        if capture is None or capture.status != "processing":
            return None
        work = []
        for side, document_id in _sides_needing_work(capture):
            asset = await _active_asset(session, document_id)
            if asset is not None:
                work.append((side, document_id, asset))
        return PROFILES[capture.kind], work


async def _is_waiting(capture_id: uuid.UUID, now: datetime) -> bool:
    async with session_scope() as session:
        capture = await session.get(DocumentCaptureModel, capture_id)
        return (
            capture is not None
            and capture.status == "pending"
            and capture.expires_at > now
            and capture.attempts < settings.VLM_MAX_ATTEMPTS
        )


async def process_capture(ctx: dict[str, Any], raw_id: str) -> None:
    capture_id = uuid.UUID(raw_id)
    # Una cola acumulada con la PC apagada no debe cargar el modelo para trabajo vencido.
    if not await _is_waiting(capture_id, datetime.now(UTC)):
        return
    supervisor: ModelSupervisor = ctx["supervisor"]
    started = datetime.now(UTC)
    was_cold = False
    with operation_span("vlm.process", operation="process"):
        try:
            async with supervisor.lease() as cold:
                was_cold = cold
                if cold and supervisor.last_load_seconds is not None:
                    record_histogram(
                        "erp.vlm.model.load.duration",
                        supervisor.last_load_seconds * 1000,
                    )
                if not await _claim(capture_id, datetime.now(UTC)):
                    return
                await _extract_sides(ctx, capture_id)
        except GpuBusyError as exc:
            record_counter("erp.vlm.jobs", attributes={"status": "gpu_busy"})
            raise Retry(defer=_GPU_BUSY_RETRY_SECONDS) from exc
        except ModelStartError as exc:
            log.warning("vlm_model_start_failed", capture_id=raw_id)
            record_counter("erp.vlm.jobs", attributes={"status": "engine_unavailable"})
            raise Retry(defer=_ENGINE_RETRY_SECONDS) from exc
        except (VisionExtractionError, InfrastructureError, TimeoutError, OSError) as exc:
            code = exc.args[0] if isinstance(exc, VisionExtractionError) else type(exc).__name__
            status = await _mark_failure(capture_id, str(code)[:64])
            record_counter("erp.vlm.jobs", attributes={"status": "retry"})
            # El tipo de error basta: el mensaje podría incluir contenido de la licencia.
            log.warning("vlm_extraction_failed", capture_id=raw_id, error_type=type(exc).__name__)
            if status == "pending":
                raise Retry(defer=_ENGINE_RETRY_SECONDS) from exc
            return
    ready = await _finish(capture_id)
    if ready:
        record_counter("erp.vlm.jobs", attributes={"status": "ready"})
        record_histogram(
            "erp.vlm.job.latency",
            (datetime.now(UTC) - started).total_seconds() * 1000,
            attributes={"result": "cold" if was_cold else "warm"},
        )


async def _extract_sides(ctx: dict[str, Any], capture_id: uuid.UUID) -> None:
    loaded = await _load_work(capture_id)
    if loaded is None:
        return
    profile, work = loaded
    for side, document_id, asset in work:
        values = await _read_side(ctx["extractor"], ctx["storage"], profile, side, asset)
        await _store(capture_id, side, document_id, values)


async def warm_up(ctx: dict[str, Any]) -> None:
    """Start loading in the background: this job must not hold the only worker slot."""
    supervisor: ModelSupervisor = ctx["supervisor"]
    if supervisor.loaded:
        await supervisor.ensure_started()
        return
    task = asyncio.create_task(_warm(supervisor))
    ctx["warm_tasks"].add(task)
    task.add_done_callback(ctx["warm_tasks"].discard)


async def _warm(supervisor: ModelSupervisor) -> None:
    with contextlib.suppress(GpuBusyError, ModelStartError):
        await supervisor.ensure_started()


async def reconcile_captures(ctx: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.VLM_STALE_SECONDS)
    async with session_scope() as session:
        # A diferencia del OCR, recuperar trabajo colgado sí respeta el tope de intentos.
        await session.execute(
            update(DocumentCaptureModel)
            .where(
                DocumentCaptureModel.status == "processing",
                DocumentCaptureModel.started_at < stale_before,
            )
            .values(
                status=case(
                    (DocumentCaptureModel.attempts >= settings.VLM_MAX_ATTEMPTS, "failed"),
                    else_="pending",
                ),
                failure_code="vlm_interrupted",
                started_at=None,
            )
        )
        pending = (
            await session.scalars(
                select(DocumentCaptureModel.id)
                .where(
                    DocumentCaptureModel.status == "pending",
                    DocumentCaptureModel.expires_at > now,
                )
                .order_by(DocumentCaptureModel.updated_at)
                .limit(_RECONCILE_BATCH)
            )
        ).all()
        oldest = await session.scalar(
            select(func.min(DocumentCaptureModel.updated_at)).where(
                DocumentCaptureModel.status == "pending"
            )
        )
    record_gauge("erp.vlm.pending", len(pending))
    record_gauge("erp.vlm.pending.age", (now - oldest).total_seconds() if oldest else 0)
    for capture_id in pending:
        await ctx["redis"].enqueue_job(
            "process_capture", str(capture_id), _job_id=f"vlm:{capture_id}", _queue_name=VLM_QUEUE
        )


async def _free_vram_mib() -> int | None:
    try:
        process = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=memory.free",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except (OSError, TimeoutError):
        return None
    try:
        free = int(output.decode().split()[0])
    except (ValueError, IndexError):
        return None
    record_gauge("erp.vlm.vram.free", free)
    return free


def _server_command() -> list[str]:
    model_dir = Path(settings.VLM_MODEL_DIR)
    return [
        settings.VLM_SERVER_BIN,
        "--model",
        str(model_dir / settings.VLM_MODEL_FILE),
        "--mmproj",
        str(model_dir / settings.VLM_MMPROJ_FILE),
        "--host",
        "127.0.0.1",
        "--port",
        str(settings.VLM_PORT),
        "--alias",
        "HYVL",
        "--ctx-size",
        "4096",
        "--n-predict",
        "256",
        "--n-gpu-layers",
        "99",
        "--parallel",
        "1",
        "-fa",
        "on",
        "--jinja",
        "--no-webui",
    ]


async def _reap(ctx: dict[str, Any]) -> None:
    supervisor: ModelSupervisor = ctx["supervisor"]
    while True:
        await asyncio.sleep(_REAPER_SECONDS)
        await supervisor.stop_if_idle()
        record_gauge("erp.vlm.model.loaded", 1 if supervisor.loaded else 0)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    initialize_observability("erp-vlm-worker")
    extractor = LlamaServerExtractor(
        f"http://127.0.0.1:{settings.VLM_PORT}",
        timeout_seconds=settings.VLM_INFERENCE_TIMEOUT_SECONDS,
    )
    ctx["extractor"] = extractor
    ctx["storage"] = S3ObjectStorage(settings)
    ctx["supervisor"] = ModelSupervisor(
        _server_command(),
        is_ready=extractor.is_ready,
        free_vram_mib=_free_vram_mib,
        min_free_vram_mib=settings.VLM_MIN_FREE_VRAM_MIB,
        idle_seconds=settings.VLM_IDLE_SECONDS,
        startup_timeout_seconds=settings.VLM_STARTUP_TIMEOUT_SECONDS,
    )
    ctx["warm_tasks"] = set()
    ctx["reaper"] = asyncio.create_task(_reap(ctx))


async def shutdown(ctx: dict[str, Any]) -> None:
    ctx["reaper"].cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await ctx["reaper"]
    await ctx["supervisor"].shutdown()
    shutdown_observability()


_reconcile_seconds = set(range(0, 60, settings.VLM_RECONCILE_SECONDS))


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_capture, warm_up]
    cron_jobs: ClassVar[list[Any]] = [
        cron(reconcile_captures, second=_reconcile_seconds, run_at_startup=True)
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0")
    queue_name = VLM_QUEUE
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1
    # Un trabajo reintentado por GPU ocupada no gasta intentos: el tope real está en la fila.
    max_tries = 1000
    job_timeout = (
        settings.VLM_STARTUP_TIMEOUT_SECONDS + 2 * settings.VLM_INFERENCE_TIMEOUT_SECONDS + 30
    )
    keep_result = 0
    health_check_interval = 10
    health_check_key = VLM_HEALTH_KEY
