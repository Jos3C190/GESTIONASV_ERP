"""Shared domain primitives for single primary images."""

from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

MAX_IMAGE_URL_LENGTH = 2048
MAX_ALT_TEXT_LENGTH = 160


@dataclass(frozen=True, slots=True)
class SingleImage:
    """A persisted primary image attached to one business entity."""

    id: uuid.UUID
    source_type: str
    url: str
    media_asset_id: uuid.UUID | None
    alt_text: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SingleImageDraft:
    """Input used to attach, replace, or remove a primary image."""

    source_type: str
    url: str
    media_asset_id: uuid.UUID | None
    alt_text: str | None


def validate_external_image_url(url: str) -> str:
    """Validate an external image reference without making a network request."""
    value = url.strip()
    if len(value) > MAX_IMAGE_URL_LENGTH:
        raise ValueError("La URL de imagen supera el máximo permitido.")
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not hostname:
        raise ValueError("Las imágenes externas deben usar una URL HTTPS válida.")
    if parsed.username or parsed.password:
        raise ValueError("La URL de imagen no puede contener credenciales.")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("No se permiten URLs locales para imágenes externas.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("No se permiten direcciones privadas para imágenes externas.")
    return value


def normalize_single_image_draft(draft: SingleImageDraft) -> SingleImageDraft:
    """Normalize one image and enforce source/asset parity."""
    source_type = draft.source_type.strip().lower()
    url = draft.url.strip()
    if not url:
        raise ValueError("La URL de imagen es obligatoria.")
    if len(url) > MAX_IMAGE_URL_LENGTH:
        raise ValueError("La URL de imagen supera el máximo permitido.")
    if source_type == "external":
        url = validate_external_image_url(url)
        if draft.media_asset_id is not None:
            raise ValueError("Una imagen externa no puede referenciar un asset Cloudinary.")
    elif source_type == "cloudinary":
        if draft.media_asset_id is None:
            raise ValueError("Una imagen Cloudinary debe referenciar su asset cargado.")
    else:
        raise ValueError("El origen de imagen no es válido.")
    alt_text = draft.alt_text.strip() if draft.alt_text else None
    if alt_text and len(alt_text) > MAX_ALT_TEXT_LENGTH:
        raise ValueError("El texto alternativo es demasiado largo.")
    return SingleImageDraft(
        source_type=source_type,
        url=url,
        media_asset_id=draft.media_asset_id,
        alt_text=alt_text,
    )
