from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
import pytest
from app.core.config import Settings
from app.infrastructure.malware_scanner import ClamAVScanner
from app.infrastructure.object_storage import S3ObjectStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DOCUMENT_STORAGE_INTEGRATION") != "true",
        reason="Set RUN_DOCUMENT_STORAGE_INTEGRATION=true with the local stack running",
    ),
]


def _settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        OBJECT_STORAGE_ENABLED=True,
        OBJECT_STORAGE_INTERNAL_ENDPOINT=os.getenv(
            "OBJECT_STORAGE_TEST_INTERNAL_ENDPOINT",
            os.getenv("OBJECT_STORAGE_INTERNAL_ENDPOINT", "http://localhost:9000"),
        ),
        OBJECT_STORAGE_PUBLIC_ENDPOINT=os.getenv(
            "OBJECT_STORAGE_TEST_PUBLIC_ENDPOINT",
            os.getenv("OBJECT_STORAGE_INTERNAL_ENDPOINT", "http://localhost:9000"),
        ),
        OBJECT_STORAGE_ACCESS_KEY=os.environ["OBJECT_STORAGE_ACCESS_KEY"],
        OBJECT_STORAGE_SECRET_KEY=os.environ["OBJECT_STORAGE_SECRET_KEY"],
        CLAMAV_HOST=os.getenv("CLAMAV_TEST_HOST", os.getenv("CLAMAV_HOST", "localhost")),
    )


async def test_presigned_put_get_head_delete_and_cors(tmp_path: Path) -> None:
    settings = _settings()
    storage = S3ObjectStorage(settings)
    await storage.ensure_bucket()
    key = f"integration/{uuid.uuid4()}"
    payload = b"document-storage-integration"
    ticket = await storage.presign_upload(
        key,
        content_type="text/plain",
        metadata={"document-id": str(uuid.uuid4()), "sha256": "a" * 64},
        expires_seconds=60,
    )
    async with httpx.AsyncClient() as client:
        preflight = await client.options(
            ticket.url,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,x-amz-meta-document-id",
            },
        )
        assert preflight.status_code < 400
        uploaded = await client.put(ticket.url, headers=ticket.headers, content=payload)
        assert uploaded.status_code < 300
        download_url = await storage.presign_download(
            key,
            filename="integration.txt",
            content_type="text/plain",
            expires_seconds=60,
        )
        downloaded = await client.get(download_url)
        assert downloaded.content == payload
    info = await storage.head(key)
    assert info is not None
    assert info.size_bytes == len(payload)
    local_copy = tmp_path / "downloaded.txt"
    await storage.download_to(key, local_copy, 1024)
    assert local_copy.read_bytes() == payload
    await storage.delete(key)
    assert await storage.head(key) is None


async def test_clamav_detects_eicar(tmp_path: Path) -> None:
    settings = _settings()
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    path = tmp_path / "eicar.com"
    path.write_bytes(eicar)
    result = await ClamAVScanner(
        settings.CLAMAV_HOST, settings.CLAMAV_PORT, settings.CLAMAV_TIMEOUT_SECONDS
    ).scan(path)
    assert result.clean is False
    assert result.malware_name
