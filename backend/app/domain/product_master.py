"""Shared product master-data constants and normalization rules."""

from __future__ import annotations

import re
from typing import Final

PRODUCT_KINDS: Final[tuple[str, ...]] = ("goods", "service")
PRODUCT_LIFECYCLE_STATUSES: Final[tuple[str, ...]] = (
    "draft",
    "active",
    "blocked",
    "discontinued",
    "retired",
)
STORAGE_CONDITIONS: Final[tuple[str, ...]] = (
    "ambient",
    "cool",
    "refrigerated",
    "frozen",
    "dry",
    "other",
)
PRODUCT_IDENTIFIER_TYPES: Final[tuple[str, ...]] = (
    "ean",
    "upc",
    "gtin",
    "isbn",
    "manufacturer",
    "internal",
    "other",
)
MAX_PRODUCT_KEYWORDS: Final[int] = 20


def normalize_identifier(value: str) -> str:
    """Normalize identifiers without applying a country-specific tax rule."""
    return re.sub(r"[\s-]+", "", value.strip()).upper()


def normalize_keywords(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(str(value).strip().split())
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item[:80])
    if len(result) > MAX_PRODUCT_KEYWORDS:
        raise ValueError("Un producto puede tener como máximo 20 palabras clave.")
    return result
