from __future__ import annotations

from collections.abc import Awaitable
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
    def ensure_bucket(self) -> Awaitable[None]: ...
    def presign_upload(
        self, key: str, *, content_type: str, metadata: dict[str, str], expires_seconds: int
    ) -> Awaitable[PresignedUpload]: ...
    def presign_download(
        self, key: str, *, filename: str, content_type: str, expires_seconds: int
    ) -> Awaitable[str]: ...
    def presign_preview(
        self, key: str, *, filename: str, content_type: str, expires_seconds: int
    ) -> Awaitable[str]: ...
    def head(self, key: str) -> Awaitable[StoredObjectInfo | None]: ...
    def download_to(self, key: str, destination: Path, max_bytes: int) -> Awaitable[None]: ...
    def upload_from(
        self, key: str, source: Path, *, content_type: str, metadata: dict[str, str]
    ) -> Awaitable[StoredObjectInfo]: ...
    def delete(self, key: str) -> Awaitable[None]: ...
    def health(self) -> Awaitable[bool]: ...
