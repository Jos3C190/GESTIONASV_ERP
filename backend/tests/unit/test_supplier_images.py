from __future__ import annotations

import uuid

import pytest
from app.api.v1.schemas.supplier import SupplierImageInput
from app.domain.entities.media_image import SingleImageDraft, normalize_single_image_draft
from pydantic import ValidationError


def test_single_image_normalizes_external_url_and_alt_text() -> None:
    image = normalize_single_image_draft(
        SingleImageDraft(
            source_type="EXTERNAL",
            url="  https://cdn.example.com/logo.webp  ",
            media_asset_id=None,
            alt_text="  Logo corporativo  ",
        )
    )

    assert image.source_type == "external"
    assert image.url == "https://cdn.example.com/logo.webp"
    assert image.alt_text == "Logo corporativo"


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.com/logo.webp",
        "https://user:password@cdn.example.com/logo.webp",
        "https://localhost/logo.webp",
        "https://127.0.0.1/logo.webp",
        "data:image/png;base64,abc",
    ],
)
def test_single_image_rejects_unsafe_external_urls(url: str) -> None:
    with pytest.raises(ValueError, match="URL|credenciales|locales|privadas"):
        normalize_single_image_draft(
            SingleImageDraft(
                source_type="external",
                url=url,
                media_asset_id=None,
                alt_text=None,
            )
        )


def test_single_image_requires_cloudinary_asset_and_schema_accepts_valid_sources() -> None:
    with pytest.raises(ValidationError):
        SupplierImageInput(
            source_type="cloudinary",
            url="https://res.cloudinary.com/demo/image/upload/logo.webp",
        )

    asset_id = uuid.uuid4()
    image = SupplierImageInput(
        source_type="cloudinary",
        url="https://res.cloudinary.com/demo/image/upload/logo.webp",
        media_asset_id=asset_id,
        alt_text="Logo",
    )
    assert image.media_asset_id == asset_id
