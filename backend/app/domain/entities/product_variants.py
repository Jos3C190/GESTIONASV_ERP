"""Domain entities and drafts for product families and variants."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.product_image import ProductImage
from app.domain.entities.product_master import ProductIdentifier


@dataclass(frozen=True, slots=True)
class ProductFamilyAttributeValue:
    id: uuid.UUID
    attribute_id: uuid.UUID
    code: str
    label: str
    position: int = 0
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ProductFamilyAttribute:
    id: uuid.UUID
    product_id: int
    code: str
    name: str
    position: int = 0
    is_active: bool = True
    values: tuple[ProductFamilyAttributeValue, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductVariantValue:
    attribute_code: str
    value_code: str
    label: str


@dataclass(frozen=True, slots=True)
class ProductVariant:
    id: uuid.UUID
    product_id: int
    company_id: uuid.UUID
    sku: str
    name_override: str | None
    display_name: str
    combination_key: str
    lifecycle_status: str
    is_active: bool
    values: tuple[ProductVariantValue, ...] = ()
    identifiers: tuple[ProductIdentifier, ...] = ()
    image: ProductImage | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProductVariantImageDraft:
    source_type: str
    url: str
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = None


@dataclass(frozen=True, slots=True)
class ProductVariantValueDraft:
    attribute_code: str
    value_code: str


@dataclass(frozen=True, slots=True)
class ProductVariantIdentifierDraft:
    identifier_type: str
    value: str
    is_primary: bool = False
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ProductVariantDraft:
    id: uuid.UUID | None
    sku: str
    name_override: str | None
    lifecycle_status: str
    values: tuple[ProductVariantValueDraft, ...]
    identifiers: tuple[ProductVariantIdentifierDraft, ...] = ()
    image: ProductVariantImageDraft | None = None


@dataclass(frozen=True, slots=True)
class ProductFamilyAttributeValueDraft:
    code: str
    label: str
    position: int = 0


@dataclass(frozen=True, slots=True)
class ProductFamilyAttributeDraft:
    code: str
    name: str
    position: int
    values: tuple[ProductFamilyAttributeValueDraft, ...]


@dataclass(frozen=True, slots=True)
class ProductVariantConfigDraft:
    attributes: tuple[ProductFamilyAttributeDraft, ...]
    variants: tuple[ProductVariantDraft, ...]


@dataclass(frozen=True, slots=True)
class ProductVariantUpdateDraft:
    """Partial update for one variant; attribute assignments are immutable here."""

    expected_updated_at: datetime
    provided_fields: frozenset[str]
    sku: str | None = None
    name_override: str | None = None
    lifecycle_status: str | None = None
    identifiers: tuple[ProductVariantIdentifierDraft, ...] | None = None
    image: ProductVariantImageDraft | None = None
