"""Pure Cloudinary signing helpers kept independent from the API layer."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping


def cloudinary_signature(params: Mapping[str, str | int | bool], api_secret: str) -> str:
    """Create the SHA-1 signature required by Cloudinary's Upload API."""
    normalized = "&".join(
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in sorted(params.items())
        if value not in (None, "")
    )
    return hashlib.sha1(f"{normalized}{api_secret}".encode()).hexdigest()  # noqa: S324
