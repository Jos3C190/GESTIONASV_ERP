"""Pydantic v2 DTOs for Catalog: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.media_image import validate_external_image_url
from app.domain.product_variants import normalize_variant_token

DimensionUnit = Literal["mm", "cm", "m", "in", "ft"]
WeightUnit = Literal["mg", "g", "kg", "t", "oz", "lb"]
ProductKind = Literal["goods", "service"]
ProductLifecycleStatus = Literal["draft", "active", "blocked", "discontinued", "retired"]
StorageCondition = Literal["ambient", "cool", "refrigerated", "frozen", "dry", "other"]
IdentifierType = Literal["ean", "upc", "gtin", "isbn", "manufacturer", "internal", "other"]


# --- Country ---
class CountryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_country")
    name: str
    iso_code_2: str
    iso_code_3: str
    phone_code: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Category ---
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class CategoryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_category")
    uuid: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- SubCategory ---
class SubCategoryCreate(BaseModel):
    category_id: int = Field(..., alias="id_category")
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class SubCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class SubCategoryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_sub_category")
    category_id: int = Field(..., serialization_alias="id_category")
    company_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CatalogOptionResponse(BaseModel):
    """Small, searchable option used by large catalogue filters."""

    id: int
    label: str
    parent_id: int | None = None


class ProductDistributionItem(BaseModel):
    id: int | None = None
    parent_id: int | None = None
    label: str
    value: int = Field(..., ge=0)
    filterable: bool = True


class ProductDistributionResponse(BaseModel):
    scope_total: int = Field(..., ge=0)
    categories: list[ProductDistributionItem] = Field(default_factory=list)
    subcategories: list[ProductDistributionItem] = Field(default_factory=list)


# --- Unit ---
class UnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    symbol: str = Field(..., min_length=1, max_length=20)
    description: str | None = Field(None, max_length=500)


class UnitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None
    code: str | None = Field(None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    symbol: str | None = Field(None, min_length=1, max_length=20)
    description: str | None = Field(None, max_length=500)
    alias: str | None = Field(None, max_length=100)
    version: int = Field(..., ge=1)


class UnitResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_unit")
    name: str
    type: str
    code: str
    symbol: str
    owner_company_id: uuid.UUID | None = None
    description: str | None = None
    is_standard: bool
    is_enabled: bool
    alias: str | None = None
    version: int
    configuration_version: int
    usage_count: int = 0
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UnitConfigurationUpdate(BaseModel):
    version: int = Field(..., ge=1)
    alias: str | None = Field(None, max_length=100)


# --- Product ---
class ProductImageInput(BaseModel):
    id: uuid.UUID | None = None
    source_type: Literal["cloudinary", "external"]
    url: str = Field(..., min_length=10, max_length=2048)
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = Field(None, max_length=160)
    position: int = Field(..., ge=0, le=19)
    is_cover: bool = False

    @model_validator(mode="after")
    def validate_source(self) -> ProductImageInput:
        if self.source_type == "external":
            self.url = validate_external_image_url(self.url)
            parsed = urlparse(self.url.strip())
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if parsed.scheme.lower() != "https" or not hostname:
                raise ValueError("Las imágenes externas deben usar una URL HTTPS válida.")
            if parsed.username or parsed.password:
                raise ValueError("La URL de imagen no puede contener credenciales.")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise ValueError("No se permiten URLs locales para imágenes externas.")
            if self.media_asset_id is not None:
                raise ValueError("Una imagen externa no puede referenciar un asset Cloudinary.")
        elif self.media_asset_id is None:
            raise ValueError("Una imagen Cloudinary debe referenciar su asset cargado.")
        return self


class ProductImageResponse(ORMOut):
    id: uuid.UUID
    product_id: int | None = None
    variant_id: uuid.UUID | None = None
    source_type: Literal["cloudinary", "external"]
    url: str
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = None
    position: int
    is_cover: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductVariantImageInput(BaseModel):
    source_type: Literal["cloudinary", "external"]
    url: str = Field(..., min_length=10, max_length=2048)
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = Field(None, max_length=160)

    @model_validator(mode="after")
    def validate_source(self) -> ProductVariantImageInput:
        if self.source_type == "external":
            self.url = validate_external_image_url(self.url)
            parsed = urlparse(self.url.strip())
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if parsed.scheme.lower() != "https" or not hostname:
                raise ValueError("Las imágenes externas deben usar una URL HTTPS válida.")
            if parsed.username or parsed.password:
                raise ValueError("La URL de imagen no puede contener credenciales.")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise ValueError("No se permiten URLs locales para imágenes externas.")
            if self.media_asset_id is not None:
                raise ValueError("Una imagen externa no puede referenciar un asset Cloudinary.")
        elif self.media_asset_id is None:
            raise ValueError("Una imagen Cloudinary debe referenciar su asset cargado.")
        return self


class ProductFamilyAttributeValueInput(BaseModel):
    code: str = Field(..., min_length=1, max_length=60)
    label: str = Field(..., min_length=1, max_length=120)
    position: int = Field(0, ge=0)


class ProductFamilyAttributeInput(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=100)
    position: int = Field(0, ge=0, lt=5)
    values: list[ProductFamilyAttributeValueInput] = Field(..., min_length=1, max_length=100)


class ProductVariantValueInput(BaseModel):
    attribute_code: str = Field(..., min_length=1, max_length=40)
    value_code: str = Field(..., min_length=1, max_length=60)


class ProductVariantIdentifierInput(BaseModel):
    identifier_type: IdentifierType
    value: str = Field(..., min_length=1, max_length=160)
    is_primary: bool = False

    @model_validator(mode="after")
    def validate_identifier(self) -> ProductVariantIdentifierInput:
        # Keep variant identifiers under the same EAN/UPC/GTIN rules as
        # product identifiers.  The referenced model is defined later in this
        # module and is resolved when validation runs.
        ProductIdentifierCreate(
            identifier_type=self.identifier_type,
            value=self.value,
            is_primary=self.is_primary,
        )
        return self


class ProductVariantInput(BaseModel):
    id: uuid.UUID | None = None
    sku: str = Field(..., min_length=2, max_length=100)
    name_override: str | None = Field(None, max_length=200)
    lifecycle_status: ProductLifecycleStatus = "draft"
    values: list[ProductVariantValueInput] = Field(..., min_length=1, max_length=5)
    identifiers: list[ProductVariantIdentifierInput] = Field(default_factory=list, max_length=20)
    image: ProductVariantImageInput | None = None


class ProductVariantConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributes: list[ProductFamilyAttributeInput] = Field(..., min_length=1, max_length=5)
    variants: list[ProductVariantInput] = Field(..., min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_attribute_structure(self) -> ProductVariantConfigInput:
        attr_codes = [normalize_variant_token(item.code) for item in self.attributes]
        if any(not code for code in attr_codes):
            raise ValueError("Los atributos deben tener un código válido.")
        if len(set(attr_codes)) != len(attr_codes):
            raise ValueError("Una familia no puede repetir atributos.")
        for attribute in self.attributes:
            value_codes = [normalize_variant_token(item.code) for item in attribute.values]
            if any(not code for code in value_codes):
                raise ValueError("Los valores deben tener un código válido.")
            if len(set(value_codes)) != len(value_codes):
                raise ValueError("Un atributo no puede repetir valores.")
        expected = set(attr_codes)
        seen_combinations: set[tuple[tuple[str, str], ...]] = set()
        for variant in self.variants:
            pairs = tuple(
                sorted(
                    (
                        normalize_variant_token(item.attribute_code),
                        normalize_variant_token(item.value_code),
                    )
                    for item in variant.values
                )
            )
            if any(not attribute_code or not value_code for attribute_code, value_code in pairs):
                raise ValueError("Cada variante debe referenciar códigos válidos.")
            if (
                len(pairs) != len({key for key, _value in pairs})
                or {key for key, _value in pairs} != expected
            ):
                raise ValueError("Cada variante debe definir exactamente un valor por atributo.")
            if pairs in seen_combinations:
                raise ValueError("La familia contiene combinaciones repetidas.")
            seen_combinations.add(pairs)
        return self


class ProductVariantUpdateInput(BaseModel):
    """Patch for one variant; combination assignments are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(None, min_length=2, max_length=100)
    name_override: str | None = Field(None, max_length=200)
    lifecycle_status: ProductLifecycleStatus | None = None
    identifiers: list[ProductVariantIdentifierInput] | None = Field(None, max_length=20)
    image: ProductVariantImageInput | None = None
    expected_updated_at: datetime

    @model_validator(mode="after")
    def validate_patch(self) -> ProductVariantUpdateInput:
        editable = {"sku", "name_override", "lifecycle_status", "identifiers", "image"}
        provided = editable.intersection(self.model_fields_set)
        if not provided:
            raise ValueError("Debe enviar al menos un campo editable de la variante.")
        if self.expected_updated_at.tzinfo is None or self.expected_updated_at.utcoffset() is None:
            raise ValueError("expected_updated_at debe incluir zona horaria.")
        if "sku" in self.model_fields_set and self.sku is None:
            raise ValueError("El SKU no puede ser nulo.")
        if "lifecycle_status" in self.model_fields_set and self.lifecycle_status is None:
            raise ValueError("El estado de la variante no puede ser nulo.")
        if "identifiers" in self.model_fields_set and self.identifiers is None:
            raise ValueError("Para eliminar identificadores envíe una lista vacía.")
        return self


class ProductFamilyAttributeValueResponse(ORMOut):
    id: uuid.UUID
    attribute_id: uuid.UUID
    code: str
    label: str
    position: int
    is_active: bool


class ProductFamilyAttributeResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    code: str
    name: str
    position: int
    is_active: bool
    values: list[ProductFamilyAttributeValueResponse] = Field(default_factory=list)


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category_id: int = Field(..., alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    purchase_unit_id: int = Field(..., alias="purchase_unit")
    sale_unit_id: int = Field(..., alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = Field(None, max_length=50)
    dimension_length: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_width: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_height: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: WeightUnit | None = None
    description: str | None = None
    presentation: str | None = None
    product_kind: ProductKind = "goods"
    lifecycle_status: ProductLifecycleStatus = "active"
    can_purchase: bool = True
    can_sell: bool = True
    sales_name: str | None = Field(None, max_length=200)
    internal_name: str | None = Field(None, max_length=200)
    document_name: str | None = Field(None, max_length=160)
    sales_description: str | None = None
    purchase_description: str | None = None
    internal_notes: str | None = None
    keywords: list[str] = Field(default_factory=list, max_length=20)
    origin_country_id: int | None = None
    brand_id: uuid.UUID | None = None
    manufacturer_id: uuid.UUID | None = None
    storage_condition: StorageCondition | None = None
    storage_temperature_min_c: Decimal | None = Field(
        None, ge=-273.15, max_digits=6, decimal_places=2
    )
    storage_temperature_max_c: Decimal | None = Field(
        None, ge=-273.15, max_digits=6, decimal_places=2
    )
    storage_humidity_max_percent: Decimal | None = Field(
        None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    is_fragile: bool = False
    keep_dry: bool = False
    keep_upright: bool = False
    stackable: bool = True
    max_stack_height: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    handling_notes: str | None = None
    images: list[ProductImageInput] | None = Field(None, max_length=20)
    variant_config: ProductVariantConfigInput | None = None

    @model_validator(mode="after")
    def validate_measurement_pairs(self) -> ProductCreate:
        has_dimensions = any(
            value is not None
            for value in (self.dimension_length, self.dimension_width, self.dimension_height)
        )
        if has_dimensions != (self.dimension_unit is not None):
            raise ValueError(
                "Las dimensiones requieren una unidad y no se permite unidad sin medidas."
            )
        if (self.weight is None) != (self.weight_unit is None):
            raise ValueError("El peso requiere una unidad y no se permite unidad sin peso.")
        if (
            self.product_kind == "service"
            and any(
                value is not None
                for value in (
                    self.storage_condition,
                    self.storage_temperature_min_c,
                    self.storage_temperature_max_c,
                    self.storage_humidity_max_percent,
                    self.max_stack_height,
                    self.handling_notes,
                )
            )
        ) or (
            self.product_kind == "service"
            and (not self.stackable or any((self.is_fragile, self.keep_dry, self.keep_upright)))
        ):
            raise ValueError("Los datos de almacenamiento solo aplican a bienes físicos.")
        if (
            self.storage_temperature_min_c is not None
            and self.storage_temperature_max_c is not None
            and self.storage_temperature_min_c > self.storage_temperature_max_c
        ):
            raise ValueError("La temperatura mínima no puede superar la máxima.")
        return self


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category_id: int | None = Field(None, alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str | None = Field(None, min_length=2, max_length=100)
    name: str | None = Field(None, min_length=2, max_length=200)
    purchase_unit_id: int | None = Field(None, alias="purchase_unit")
    sale_unit_id: int | None = Field(None, alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = Field(None, max_length=50)
    dimension_length: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_width: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_height: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: WeightUnit | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool | None = None
    images: list[ProductImageInput] | None = Field(None, max_length=20)
    product_kind: ProductKind | None = None
    lifecycle_status: ProductLifecycleStatus | None = None
    can_purchase: bool | None = None
    can_sell: bool | None = None
    sales_name: str | None = Field(None, max_length=200)
    internal_name: str | None = Field(None, max_length=200)
    document_name: str | None = Field(None, max_length=160)
    sales_description: str | None = None
    purchase_description: str | None = None
    internal_notes: str | None = None
    keywords: list[str] | None = Field(None, max_length=20)
    origin_country_id: int | None = None
    brand_id: uuid.UUID | None = None
    manufacturer_id: uuid.UUID | None = None
    storage_condition: StorageCondition | None = None
    storage_temperature_min_c: Decimal | None = Field(
        None, ge=-273.15, max_digits=6, decimal_places=2
    )
    storage_temperature_max_c: Decimal | None = Field(
        None, ge=-273.15, max_digits=6, decimal_places=2
    )
    storage_humidity_max_percent: Decimal | None = Field(
        None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    is_fragile: bool | None = None
    keep_dry: bool | None = None
    keep_upright: bool | None = None
    stackable: bool | None = None
    max_stack_height: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    handling_notes: str | None = None
    expected_updated_at: datetime | None = None
    variant_config: ProductVariantConfigInput | None = None


class ProductResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_product")
    uuid: uuid.UUID
    company_id: uuid.UUID
    category_id: int = Field(..., serialization_alias="id_category")
    category_name: str | None = None
    sub_category_id: int | None = Field(None, serialization_alias="id_sub_category")
    sku: str
    name: str
    purchase_unit_id: int = Field(..., serialization_alias="purchase_unit")
    sale_unit_id: int = Field(..., serialization_alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = None
    dimensions: str | None = None
    dimensions_legacy: str | None = None
    dimension_length: Decimal | None = None
    dimension_width: Decimal | None = None
    dimension_height: Decimal | None = None
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = None
    weight_unit: WeightUnit | None = None
    dimension_summary: str | None = None
    volume: Decimal | None = None
    volume_unit: str | None = None
    description: str | None = None
    presentation: str | None = None
    product_kind: ProductKind = "goods"
    lifecycle_status: ProductLifecycleStatus = "active"
    can_purchase: bool = True
    can_sell: bool = True
    sales_name: str | None = None
    internal_name: str | None = None
    document_name: str | None = None
    sales_description: str | None = None
    purchase_description: str | None = None
    internal_notes: str | None = None
    keywords: list[str] = Field(default_factory=list)
    origin_country_id: int | None = None
    brand_id: uuid.UUID | None = None
    manufacturer_id: uuid.UUID | None = None
    storage_condition: StorageCondition | None = None
    storage_temperature_min_c: Decimal | None = None
    storage_temperature_max_c: Decimal | None = None
    storage_humidity_max_percent: Decimal | None = None
    is_fragile: bool = False
    keep_dry: bool = False
    keep_upright: bool = False
    stackable: bool = True
    max_stack_height: Decimal | None = None
    handling_notes: str | None = None
    identifiers: list[ProductIdentifierResponse] = Field(default_factory=list)
    supplier_links: list[ProductSupplierResponse] = Field(default_factory=list)
    is_active: bool
    images: list[ProductImageResponse] = Field(default_factory=list)
    image_count: int = 0
    cover_image: ProductImageResponse | None = None
    variant_mode: Literal["standalone", "template"] = "standalone"
    variant_count: int = 0
    variant_attributes: list[ProductFamilyAttributeResponse] = Field(default_factory=list)
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductIdentifierResponse(ORMOut):
    id: uuid.UUID
    product_id: int | None = None
    variant_id: uuid.UUID | None = None
    company_id: uuid.UUID
    identifier_type: IdentifierType
    value: str
    normalized_value: str
    is_primary: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductVariantResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    company_id: uuid.UUID
    sku: str
    name_override: str | None = None
    display_name: str
    combination_key: str
    lifecycle_status: ProductLifecycleStatus
    is_active: bool
    values: list[ProductVariantValueResponse] = Field(default_factory=list)
    identifiers: list[ProductIdentifierResponse] = Field(default_factory=list)
    image: ProductImageResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductVariantValueResponse(ORMOut):
    attribute_code: str
    value_code: str
    label: str


class ProductSupplierResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    supplier_id: int
    company_id: uuid.UUID
    supplier_name: str | None = None
    supplier_product_code: str | None = None
    unit_cost: Decimal | None = None
    currency_code: str | None = None
    minimum_order_qty: Decimal | None = None
    order_multiple: Decimal | None = None
    lead_time_days: int | None = None
    is_preferred: bool
    status: Literal["active", "inactive"]
    valid_from: date | None = None
    valid_until: date | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductIdentifierCreate(BaseModel):
    identifier_type: IdentifierType
    value: str = Field(..., min_length=1, max_length=160)
    is_primary: bool = False

    @model_validator(mode="after")
    def validate_identifier(self) -> ProductIdentifierCreate:
        value = "".join(ch for ch in self.value if ch.isalnum())
        if self.identifier_type in {"ean", "upc", "gtin"}:
            lengths = {"ean": {8, 13, 14}, "upc": {12}, "gtin": {8, 12, 13, 14}}
            if len(value) not in lengths[self.identifier_type] or not value.isdigit():
                raise ValueError(
                    f"El identificador {self.identifier_type.upper()} debe tener una longitud válida."
                )
            digits = [int(item) for item in value]
            check = digits.pop()
            total = sum(
                digit * (3 if (len(digits) - index) % 2 else 1)
                for index, digit in enumerate(digits)
            )
            if (10 - total % 10) % 10 != check:
                raise ValueError("El dígito de control del identificador no es válido.")
        return self


class ProductIdentifierUpdate(BaseModel):
    identifier_type: IdentifierType | None = None
    value: str | None = Field(None, min_length=1, max_length=160)
    is_primary: bool | None = None
    is_active: bool | None = None


class ProductSupplierCreate(BaseModel):
    supplier_id: int
    supplier_product_code: str | None = Field(None, max_length=120)
    unit_cost: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=4)
    currency_code: str | None = Field(None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    minimum_order_qty: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=4)
    order_multiple: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=4)
    lead_time_days: int | None = Field(None, ge=0)
    is_preferred: bool = False
    status: Literal["active", "inactive"] = "active"
    valid_from: date | None = None
    valid_until: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_supplier_terms(self) -> ProductSupplierCreate:
        if self.unit_cost is not None and not self.currency_code:
            raise ValueError("La moneda es obligatoria cuando se informa un costo.")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("La vigencia final no puede ser anterior a la inicial.")
        if self.is_preferred and self.status != "active":
            raise ValueError("Una relación inactiva no puede ser preferida.")
        return self


class ProductSupplierUpdate(ProductSupplierCreate):
    supplier_id: int | None = None


class ProductSupplierReplace(BaseModel):
    """Complete supplier set submitted from the product editor."""

    suppliers: list[ProductSupplierCreate] = Field(default_factory=list, max_length=100)


class ProductBrandCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=2, max_length=160)


class ProductBrandUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=60)
    name: str | None = Field(None, min_length=2, max_length=160)
    is_active: bool | None = None


class ProductBrandResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    normalized_name: str
    is_active: bool


class ProductManufacturerCreate(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=240)
    commercial_name: str | None = Field(None, max_length=200)
    country_id: int | None = None
    website: str | None = Field(None, max_length=2048)


class ProductManufacturerUpdate(ProductManufacturerCreate):
    legal_name: str | None = Field(None, min_length=2, max_length=240)
    is_active: bool | None = None


class ProductManufacturerResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    legal_name: str
    commercial_name: str | None = None
    country_id: int | None = None
    website: str | None = None
    is_active: bool


ProductResponse.model_rebuild()
ProductVariantResponse.model_rebuild()
