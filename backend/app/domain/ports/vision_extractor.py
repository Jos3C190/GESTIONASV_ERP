from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class VisionExtractionError(Exception):
    """The model answered, but not with the requested fields."""


class VisionExtractor(Protocol):
    async def extract(
        self,
        image: Path,
        *,
        prompt: str,
        response_format: Mapping[str, Any],
        keys: tuple[str, ...],
    ) -> dict[str, str | None]: ...
