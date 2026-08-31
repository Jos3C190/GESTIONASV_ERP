from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObjectInfo:
    size_bytes: int
    content_type: str | None
    etag: str | None
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    headers: dict[str, str]


class ObjectStorage(Protocol):
    async def ensure_bucket(self) -> None: ...
    async def presign_upload(
        self, key: str, *, content_type: str, metadata: dict[str, str], expires_seconds: int
    ) -> PresignedUpload: ...
    async def presign_download(
        self, key: str, *, filename: str, content_type: str, expires_seconds: int
    ) -> str: ...
    async def head(self, key: str) -> StoredObjectInfo | None: ...
    async def download_to(self, key: str, destination: Path, max_bytes: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def health(self) -> bool: ...
