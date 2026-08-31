from __future__ import annotations

import asyncio

from app.core.config import settings
from app.infrastructure.object_storage import S3ObjectStorage


async def bootstrap() -> None:
    if not settings.OBJECT_STORAGE_ENABLED:
        return
    await S3ObjectStorage(settings).ensure_bucket()


if __name__ == "__main__":
    asyncio.run(bootstrap())
