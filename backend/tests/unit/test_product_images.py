from __future__ import annotations

import uuid

import pytest
from app.api.v1.schemas.catalog import ProductImageInput
from app.domain.entities.product_image import (
    ProductImageDraft,
    normalize_product_image_drafts,
    validate_external_image_url,
)
from pydantic import ValidationError


def _external(position: int = 0, *, cover: bool = False, url: str | None = None) -> ProductImageDraft:
    return ProductImageDraft(
        id=None,
        source_type="external",
        url=url or f"https://cdn.example.com/product-{position}.webp",
        media_asset_id=None,
        alt_text=None,
        position=position,
        is_cover=cover,
    )


def test_gallery_normalizes_positions_and_promotes_first_cover() -> None:
    result = normalize_product_image_drafts([_external(7), _external(3)])

    assert [image.position for image in result] == [0, 1]
    assert result[0].is_cover is True
    assert result[1].is_cover is False


def test_gallery_rejects_duplicate_positions_urls_and_multiple_covers() -> None:
    with pytest.raises(ValueError, match="repetir posición"):
        normalize_product_image_drafts([_external(0), _external(0, url="https://cdn.example.com/other.webp")])
    with pytest.raises(ValueError, match="repetir URLs"):
        normalize_product_image_drafts([_external(0, url="https://cdn.example.com/a.webp"), _external(1, url="https://cdn.example.com/a.webp")])
    with pytest.raises(ValueError, match="solo puede tener una portada"):
        normalize_product_image_drafts([_external(0, cover=True), _external(1, cover=True)])


def test_gallery_rejects_more_than_twenty_and_invalid_external_urls() -> None:
    images = [_external(position) for position in range(21)]
    with pytest.raises(ValueError, match="20 imágenes"):
        normalize_product_image_drafts(images)
    with pytest.raises(ValueError, match="HTTPS"):
        validate_external_image_url("http://cdn.example.com/image.webp")
    with pytest.raises(ValueError, match="locales"):
        validate_external_image_url("https://localhost/image.webp")


def test_schema_enforces_cloudinary_asset_and_external_https() -> None:
    with pytest.raises(ValidationError):
        ProductImageInput(
            source_type="cloudinary",
            url="https://res.cloudinary.com/demo/image/upload/a.webp",
            position=0,
        )
    with pytest.raises(ValidationError):
        ProductImageInput(
            source_type="external",
            url="http://cdn.example.com/a.webp",
            position=0,
        )
    image = ProductImageInput(
        source_type="cloudinary",
        url="https://res.cloudinary.com/demo/image/upload/a.webp",
        media_asset_id=uuid.uuid4(),
        position=0,
        is_cover=True,
    )
    assert image.is_cover is True
