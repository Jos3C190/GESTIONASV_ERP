from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.media_image import (
    MAX_ALT_TEXT_LENGTH,
    MAX_IMAGE_URL_LENGTH,
    validate_external_image_url,
)

MAX_PRODUCT_IMAGES = 20


@dataclass(frozen=True, slots=True)
class ProductImage:
    id: uuid.UUID
    product_id: int
    source_type: str
    url: str
    media_asset_id: uuid.UUID | None
    alt_text: str | None
    position: int
    is_cover: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProductImageDraft:
    id: uuid.UUID | None
    source_type: str
    url: str
    media_asset_id: uuid.UUID | None
    alt_text: str | None
    position: int
    is_cover: bool


def normalize_product_image_drafts(drafts: list[ProductImageDraft]) -> list[ProductImageDraft]:
    """Validate and normalize a gallery into contiguous positions."""
    if len(drafts) > MAX_PRODUCT_IMAGES:
        raise ValueError(f"Un producto admite como máximo {MAX_PRODUCT_IMAGES} imágenes.")

    seen_ids: set[uuid.UUID] = set()
    seen_urls: set[str] = set()
    seen_positions: set[int] = set()
    normalized: list[ProductImageDraft] = []
    for position, draft in enumerate(sorted(drafts, key=lambda item: item.position)):
        normalized.append(
            _validate_and_normalize_draft(
                draft,
                position=position,
                seen_ids=seen_ids,
                seen_urls=seen_urls,
                seen_positions=seen_positions,
            )
        )

    cover_count = sum(1 for draft in normalized if draft.is_cover)
    if cover_count > 1:
        raise ValueError("La galería solo puede tener una portada.")
    if normalized and cover_count == 0:
        first = normalized[0]
        normalized[0] = ProductImageDraft(
            id=first.id,
            source_type=first.source_type,
            url=first.url,
            media_asset_id=first.media_asset_id,
            alt_text=first.alt_text,
            position=first.position,
            is_cover=True,
        )
    return normalized


def _validate_and_normalize_draft(
    draft: ProductImageDraft,
    *,
    position: int,
    seen_ids: set[uuid.UUID],
    seen_urls: set[str],
    seen_positions: set[int],
) -> ProductImageDraft:
    if draft.position < 0 or draft.position >= MAX_PRODUCT_IMAGES:
        raise ValueError("La posición de la imagen debe estar entre 0 y 19.")
    if draft.position in seen_positions:
        raise ValueError("Las imágenes no pueden repetir posición.")
    seen_positions.add(draft.position)
    if draft.id is not None:
        if draft.id in seen_ids:
            raise ValueError("La galería contiene una imagen repetida.")
        seen_ids.add(draft.id)

    url = draft.url.strip()
    if not url:
        raise ValueError("La URL de imagen es obligatoria.")
    if len(url) > MAX_IMAGE_URL_LENGTH:
        raise ValueError("La URL de imagen supera el máximo permitido.")
    if url.casefold() in seen_urls:
        raise ValueError("La galería no puede repetir URLs.")
    seen_urls.add(url.casefold())

    source_type = draft.source_type.strip().lower()
    _validate_image_source(source_type, url, draft.media_asset_id)

    alt_text = draft.alt_text.strip() if draft.alt_text else None
    if alt_text and len(alt_text) > MAX_ALT_TEXT_LENGTH:
        raise ValueError("El texto alternativo es demasiado largo.")
    return ProductImageDraft(
        id=draft.id,
        source_type=source_type,
        url=url,
        media_asset_id=draft.media_asset_id,
        alt_text=alt_text,
        position=position,
        is_cover=draft.is_cover,
    )


def _validate_image_source(
    source_type: str, url: str, media_asset_id: uuid.UUID | None
) -> None:
    if source_type not in {"cloudinary", "external"}:
        raise ValueError("El origen de imagen no es válido.")
    if source_type == "external":
        validate_external_image_url(url)
        if media_asset_id is not None:
            raise ValueError("Una imagen externa no puede referenciar un asset Cloudinary.")
    elif media_asset_id is None:
        raise ValueError("Una imagen Cloudinary debe referenciar su asset cargado.")
