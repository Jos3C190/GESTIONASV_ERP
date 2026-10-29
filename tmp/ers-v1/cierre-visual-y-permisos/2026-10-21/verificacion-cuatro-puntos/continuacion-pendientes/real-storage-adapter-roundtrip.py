"""Round-trip one unique fictitious file through the configured RustFS adapter."""
from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from app.core.config import settings
from app.infrastructure.object_storage import S3ObjectStorage


async def main() -> None:
    if not settings.OBJECT_STORAGE_ENABLED:
        raise SystemExit("STORAGE_DISABLED")

    adapter = S3ObjectStorage(settings)
    token = uuid.uuid4().hex
    key = f"ers-final-4p/verification/{token}.pdf"
    payload = f"%PDF-1.7\nERS-FINAL-4P storage adapter verification {token}\n%%EOF\n".encode()
    expected = hashlib.sha256(payload).hexdigest()
    descriptor, source_name = tempfile.mkstemp(prefix="ers-final4p-", suffix=".pdf")
    os.close(descriptor)
    source = Path(source_name)
    destination = source.with_suffix(".downloaded.pdf")
    source.write_bytes(payload)

    try:
        uploaded = await adapter.upload_from(
            key,
            source,
            content_type="application/pdf",
            metadata={"case": "ers-final-4p-storage-roundtrip"},
        )
        stored = await adapter.head(key)
        await adapter.download_to(key, destination, max_bytes=1024 * 1024)
        actual = hashlib.sha256(destination.read_bytes()).hexdigest()
        if stored is None or stored.size_bytes != len(payload):
            raise SystemExit("STORED_OBJECT_METADATA_MISMATCH")
        if uploaded.size_bytes != len(payload) or actual != expected:
            raise SystemExit("DOWNLOADED_BYTES_MISMATCH")
        print("OBJECT_STORAGE_ADAPTER=PASS")
        print(f"BUCKET={settings.OBJECT_STORAGE_BUCKET}")
        print(f"KEY={key}")
        print(f"BYTES={len(payload)}")
        print(f"UPLOAD_SHA256={expected}")
        print(f"DOWNLOAD_SHA256={actual}")
        print("HASH_MATCH=True")
    finally:
        await adapter.delete(key)
        source.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        print("CLEANUP=COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
