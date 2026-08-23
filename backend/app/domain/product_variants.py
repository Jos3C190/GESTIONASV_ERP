"""Pure validation helpers for product family configuration."""

from __future__ import annotations

import re
import unicodedata

from app.domain.entities.media_image import SingleImageDraft, normalize_single_image_draft
from app.domain.entities.product_variants import (
    ProductVariantConfigDraft,
    ProductVariantImageDraft,
    ProductVariantUpdateDraft,
)


def normalize_variant_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip()).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-_").casefold()


def normalize_variant_config(config: ProductVariantConfigDraft) -> ProductVariantConfigDraft:
    """Normalize codes and labels while preserving the caller's structure."""
    from app.domain.entities.product_variants import (
        ProductFamilyAttributeDraft,
        ProductFamilyAttributeValueDraft,
        ProductVariantDraft,
        ProductVariantValueDraft,
    )

    attributes = tuple(
        ProductFamilyAttributeDraft(
            code=normalize_variant_token(attribute.code),
            name=" ".join(attribute.name.strip().split()),
            position=position,
            values=tuple(
                ProductFamilyAttributeValueDraft(
                    code=normalize_variant_token(value.code),
                    label=" ".join(value.label.strip().split()),
                    position=value.position,
                )
                for value in attribute.values
            ),
        )
        for position, attribute in enumerate(
            sorted(config.attributes, key=lambda item: item.position)
        )
    )
    variants = tuple(
        ProductVariantDraft(
            id=variant.id,
            sku=variant.sku.strip(),
            name_override=" ".join(variant.name_override.strip().split())
            if variant.name_override
            else None,
            lifecycle_status=variant.lifecycle_status,
            values=tuple(
                ProductVariantValueDraft(
                    attribute_code=normalize_variant_token(value.attribute_code),
                    value_code=normalize_variant_token(value.value_code),
                )
                for value in variant.values
            ),
            identifiers=variant.identifiers,
            image=(_normalize_variant_image(variant.image) if variant.image is not None else None),
        )
        for variant in config.variants
    )
    return ProductVariantConfigDraft(attributes=attributes, variants=variants)


def normalize_variant_update(draft: ProductVariantUpdateDraft) -> ProductVariantUpdateDraft:
    """Normalize only fields explicitly supplied by an individual edit."""
    fields = draft.provided_fields
    sku = draft.sku.strip() if "sku" in fields and draft.sku is not None else draft.sku
    name_override = draft.name_override
    if "name_override" in fields and name_override is not None:
        name_override = " ".join(name_override.strip().split()) or None
    lifecycle_status = draft.lifecycle_status.strip().lower() if draft.lifecycle_status else None
    identifiers = draft.identifiers
    if "identifiers" in fields and identifiers is not None:
        identifiers = tuple(
            type(identifier)(
                identifier_type=identifier.identifier_type,
                value=identifier.value.strip(),
                is_primary=identifier.is_primary,
                is_active=identifier.is_active,
            )
            for identifier in identifiers
        )
    image = draft.image
    if "image" in fields and image is not None:
        image = _normalize_variant_image(image)
    return ProductVariantUpdateDraft(
        expected_updated_at=draft.expected_updated_at,
        provided_fields=fields,
        sku=sku,
        name_override=name_override,
        lifecycle_status=lifecycle_status,
        identifiers=identifiers,
        image=image,
    )


def _normalize_variant_image(image: ProductVariantImageDraft) -> ProductVariantImageDraft:
    normalized = normalize_single_image_draft(
        SingleImageDraft(
            source_type=image.source_type,
            url=image.url,
            media_asset_id=image.media_asset_id,
            alt_text=image.alt_text,
        )
    )
    return ProductVariantImageDraft(
        source_type=normalized.source_type,
        url=normalized.url,
        media_asset_id=normalized.media_asset_id,
        alt_text=normalized.alt_text,
    )
