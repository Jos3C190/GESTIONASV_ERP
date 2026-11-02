"""The extraction job against a real database, with a fake model and storage."""

from __future__ import annotations

import hashlib
import io
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.core.config import settings
from app.domain.ports.malware_scanner import ScanResult
from app.domain.ports.vision_extractor import VisionExtractionError
from app.infrastructure import document_maintenance
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.vlm import worker as vlm_worker
from app.infrastructure.vlm.supervisor import GpuBusyError
from arq.worker import Retry
from PIL import Image
from sqlalchemy import update

from tests.e2e.test_documents import E2EScanner, _enable_fake_services
from tests.e2e.test_driver_license_capture import _driver
from tests.e2e.test_fleet_vehicles import _admin

pytestmark = pytest.mark.e2e

FRONT = {
    "clase": "D LIVIANA",
    "vence": "02-2099",
    "numero": "0101-010101-101-1",
    "dui": "12345678-4",
    "nombre_linea_1": "PEREZ GOMEZ",
    "nombre_linea_2": "MARIA",
}
BACK = {"expedicion": "25.02.2023", "nacimiento": "20.05.1990", "numero_control": "LD-1"}


def _jpeg(shade: int = 200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (640, 400), (shade, shade, shade)).save(buffer, "JPEG")
    return buffer.getvalue()


class FakeExtractor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, int]]] = []
        self.error: Exception | None = None
        self.before_answer: Any = None

    async def extract(
        self, image: Path, *, prompt: str, response_format: Any, keys: tuple[str, ...]
    ) -> dict[str, str | None]:
        with Image.open(image) as opened:
            self.calls.append((keys[0], opened.size))
        if self.before_answer is not None:
            await self.before_answer()
        if self.error is not None:
            raise self.error
        source = FRONT if "clase" in keys else BACK
        return {key: source.get(key) for key in keys}


class FakeSupervisor:
    def __init__(self) -> None:
        self.busy = False
        self.leases = 0
        self.last_load_seconds = None
        self.loaded = False

    @asynccontextmanager
    async def lease(self) -> AsyncIterator[bool]:
        if self.busy:
            raise GpuBusyError
        self.leases += 1
        yield self.leases == 1


@pytest.fixture
def storage(e2e_client: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "LICENSE_CAPTURE_ENABLED", True)
    monkeypatch.setattr(settings, "VLM_ENABLED", True)
    return _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))


@pytest.fixture
def ctx(storage: Any) -> dict[str, Any]:
    return {"extractor": FakeExtractor(), "storage": storage, "supervisor": FakeSupervisor()}


async def _upload(
    e2e_client: Any, storage: Any, admin: dict[str, str], driver_id: str, capture_id: str, side: str
) -> dict[str, Any]:
    payload = _jpeg(180 if side == "back" else 200)
    base = f"/api/v1/drivers/{driver_id}/license-captures/{capture_id}/sides/{side}"
    started = await e2e_client.post(
        f"{base}/upload",
        headers=admin,
        json={
            "content_type": "image/jpeg",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert started.status_code == 201, started.text
    storage.put(started.json()["document_id"], payload)
    done = await e2e_client.post(f"{base}/complete", headers=admin)
    assert done.status_code == 200, done.text
    return dict(done.json())


async def _start(e2e_client: Any) -> tuple[dict[str, str], str, str, dict[str, Any]]:
    admin = await _admin(e2e_client)
    driver, employee = await _driver(e2e_client, admin)
    opened = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures", headers=admin
    )
    assert opened.status_code == 201, opened.text
    return admin, driver["id"], opened.json()["id"], employee


async def _row(capture_id: str) -> DocumentCaptureModel:
    async with async_session_factory() as session:
        capture = await session.get(DocumentCaptureModel, uuid.UUID(capture_id))
    assert capture is not None
    return capture


async def test_front_is_read_as_soon_as_scanned_and_back_later(
    e2e_client: Any, storage: Any, ctx: dict[str, Any]
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)

    uploaded = await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    assert uploaded["status"] == "pending"

    await vlm_worker.process_capture(ctx, capture_id)
    view = await e2e_client.get(
        f"/api/v1/drivers/{driver_id}/license-captures/{capture_id}", headers=admin
    )
    body = view.json()
    assert body["status"] == "ready"
    assert body["front"]["extracted"] is True
    assert body["back"]["extracted"] is False
    assert body["values"]["number"] == FRONT["numero"]
    assert body["values"]["surnames"] == FRONT["nombre_linea_1"]
    # Otra persona: el aviso sale antes de que el usuario confirme.
    assert "name_mismatch" in {item["code"] for item in body["issues"]}
    # Se reescala al borde configurado antes de enviarlo al modelo.
    assert max(ctx["extractor"].calls[0][1]) == settings.VLM_MAX_EDGE

    await _upload(e2e_client, storage, admin, driver_id, capture_id, "back")
    await vlm_worker.process_capture(ctx, capture_id)
    body = (
        await e2e_client.get(
            f"/api/v1/drivers/{driver_id}/license-captures/{capture_id}", headers=admin
        )
    ).json()
    assert body["status"] == "ready"
    assert body["values"]["issued"] == BACK["expedicion"]
    # El frente no se vuelve a leer: una inferencia por lado.
    assert [call[0] for call in ctx["extractor"].calls] == ["clase", "expedicion"]


async def test_gpu_busy_retries_without_spending_an_attempt(
    e2e_client: Any, storage: Any, ctx: dict[str, Any]
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    ctx["supervisor"].busy = True

    with pytest.raises(Retry):
        await vlm_worker.process_capture(ctx, capture_id)

    capture = await _row(capture_id)
    assert capture.status == "pending"
    assert capture.attempts == 0


async def test_failures_stop_at_the_attempt_limit(
    e2e_client: Any, storage: Any, ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "VLM_MAX_ATTEMPTS", 2)
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    ctx["extractor"].error = VisionExtractionError("invalid_json")

    with pytest.raises(Retry):
        await vlm_worker.process_capture(ctx, capture_id)
    assert (await _row(capture_id)).status == "pending"

    await vlm_worker.process_capture(ctx, capture_id)
    capture = await _row(capture_id)
    assert capture.status == "failed"
    assert capture.failure_code == "invalid_json"

    # Ya no carga el modelo para esta captura.
    leases = ctx["supervisor"].leases
    await vlm_worker.process_capture(ctx, capture_id)
    assert ctx["supervisor"].leases == leases


async def test_retake_during_inference_discards_the_late_answer(
    e2e_client: Any, storage: Any, ctx: dict[str, Any]
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")

    async def retaken() -> None:
        async with async_session_factory() as session:
            await session.execute(
                update(DocumentCaptureModel)
                .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
                .values(front_document_id=None)
            )
            await session.commit()

    ctx["extractor"].before_answer = retaken
    await vlm_worker.process_capture(ctx, capture_id)

    capture = await _row(capture_id)
    assert not (capture.extracted or {}).get("front")


async def test_confirmed_capture_ignores_late_result_and_loads_nothing(
    e2e_client: Any, storage: Any, ctx: dict[str, Any]
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    async with async_session_factory() as session:
        await session.execute(
            update(DocumentCaptureModel)
            .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
            .values(status="confirmed")
        )
        await session.commit()

    await vlm_worker.process_capture(ctx, capture_id)

    assert ctx["supervisor"].leases == 0
    assert (await _row(capture_id)).extracted is None


async def test_expired_capture_loads_nothing(
    e2e_client: Any, storage: Any, ctx: dict[str, Any]
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    async with async_session_factory() as session:
        await session.execute(
            update(DocumentCaptureModel)
            .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    await vlm_worker.process_capture(ctx, capture_id)

    assert ctx["supervisor"].leases == 0


class _Redis:
    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def enqueue_job(self, _name: str, capture_id: str, **_options: Any) -> None:
        self.jobs.append(capture_id)


async def test_reconcile_requeues_stuck_work_but_respects_the_attempt_limit(
    e2e_client: Any, storage: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "VLM_MAX_ATTEMPTS", 2)
    admin, driver_id, retriable, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, retriable, "front")
    other_admin, other_driver, exhausted, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, other_admin, other_driver, exhausted, "front")
    long_ago = datetime.now(UTC) - timedelta(hours=1)
    async with async_session_factory() as session:
        for capture_id, attempts in ((retriable, 1), (exhausted, 2)):
            await session.execute(
                update(DocumentCaptureModel)
                .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
                .values(status="processing", attempts=attempts, started_at=long_ago)
            )
        await session.commit()
    redis = _Redis()

    await vlm_worker.reconcile_captures({"redis": redis})

    assert (await _row(retriable)).status == "pending"
    assert (await _row(exhausted)).status == "failed"
    assert retriable in redis.jobs
    assert exhausted not in redis.jobs


async def test_maintenance_expires_abandoned_captures_and_their_photos(
    e2e_client: Any, storage: Any, ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, driver_id, capture_id, _ = await _start(e2e_client)
    await _upload(e2e_client, storage, admin, driver_id, capture_id, "front")
    await vlm_worker.process_capture(ctx, capture_id)
    assert len(storage.objects) == 1
    async with async_session_factory() as session:
        await session.execute(
            update(DocumentCaptureModel)
            .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    monkeypatch.setattr(document_maintenance, "S3ObjectStorage", lambda _settings: storage)
    await document_maintenance._run_once_impl()

    capture = await _row(capture_id)
    assert capture.status == "expired"
    assert capture.extracted is None
    assert storage.objects == {}
