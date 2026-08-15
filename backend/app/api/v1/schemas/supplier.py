"""Pydantic v2 DTOs for Suppliers and Supplier Contacts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.media_image import SingleImageDraft, normalize_single_image_draft


class SupplierImageInput(BaseModel):
    source_type: Literal["cloudinary", "external"]
    url: str = Field(..., min_length=10, max_length=2048)
    media_asset_id: UUID | None = None
    alt_text: str | None = Field(None, max_length=160)

    @model_validator(mode="after")
    def validate_source(self) -> SupplierImageInput:
        normalized = normalize_single_image_draft(
            SingleImageDraft(
                source_type=self.source_type,
                url=self.url,
                media_asset_id=self.media_asset_id,
                alt_text=self.alt_text,
            )
        )
        self.source_type = normalized.source_type
        self.url = normalized.url
        self.alt_text = normalized.alt_text
        return self


class SupplierImageResponse(ORMOut):
    id: UUID
    source_type: Literal["cloudinary", "external"]
    url: str
    media_asset_id: UUID | None = None
    alt_text: str | None = None


# --- Supplier Contacts ---
class SupplierContactCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    image: SupplierImageInput | None = None


class SupplierContactUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    is_active: bool | None = None
    image: SupplierImageInput | None = None


class SupplierContactResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier_contact")
    supplier_id: int = Field(..., serialization_alias="id_supplier")
    uuid: UUID | None = None
    full_name: str
    phone: str | None = None
    email: str | None = None
    is_active: bool
    avatar_image: SupplierImageResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Supplier ---
class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    country_id: int = Field(..., alias="country")
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    website: str | None = Field(None, max_length=200)
    legal_name: str | None = Field(None, max_length=240)
    supplier_group_id: UUID | None = None
    supplier_status: Literal["pending_review", "approved", "on_hold", "suspended", "rejected", "retired"] = "approved"
    hold_reason: str | None = Field(None, max_length=500)
    hold_from: datetime | None = None
    hold_until: datetime | None = None
    default_currency_code: str | None = Field(None, min_length=3, max_length=3)
    payment_terms_id: UUID | None = None
    default_payment_method: str | None = Field(None, max_length=32)
    external_reference: str | None = Field(None, max_length=120)
    image: SupplierImageInput | None = None

    @field_validator("default_currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class SupplierUpdate(BaseModel):
    code: str | None = Field(None, min_length=2, max_length=50)
    name: str | None = Field(None, min_length=2, max_length=200)
    country_id: int | None = Field(None, alias="country")
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    website: str | None = Field(None, max_length=200)
    is_active: bool | None = None
    legal_name: str | None = Field(None, max_length=240)
    supplier_group_id: UUID | None = None
    supplier_status: Literal["pending_review", "approved", "on_hold", "suspended", "rejected", "retired"] | None = None
    hold_reason: str | None = Field(None, max_length=500)
    hold_from: datetime | None = None
    hold_until: datetime | None = None
    default_currency_code: str | None = Field(None, min_length=3, max_length=3)
    payment_terms_id: UUID | None = None
    default_payment_method: str | None = Field(None, max_length=32)
    external_reference: str | None = Field(None, max_length=120)
    image: SupplierImageInput | None = None

    @field_validator("default_currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class SupplierResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier")
    uuid: UUID
    company_id: UUID
    code: str
    name: str
    country_id: int = Field(..., serialization_alias="country")
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    is_active: bool
    legal_name: str | None = None
    supplier_group_id: UUID | None = None
    supplier_status: str = "approved"
    hold_reason: str | None = None
    hold_from: datetime | None = None
    hold_until: datetime | None = None
    default_currency_code: str | None = None
    payment_terms_id: UUID | None = None
    default_payment_method: str | None = None
    external_reference: str | None = None
    logo_image: SupplierImageResponse | None = None
    tax_identifiers: list[SupplierTaxIdentifierResponse] = Field(default_factory=list)
    addresses: list[SupplierAddressResponse] = Field(default_factory=list)
    bank_accounts: list[SupplierBankAccountResponse] = Field(default_factory=list)
    image_count: int = 0
    contacts: list[SupplierContactResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierTaxIdentifierCreate(BaseModel):
    country_id: int
    identifier_type: str = Field(..., min_length=1, max_length=40)
    value: str = Field(..., min_length=1, max_length=200)
    is_primary: bool = False
    is_verified: bool = False
    verified_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @field_validator("identifier_type", "value")
    @classmethod
    def trim(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("El identificador no puede estar vacío")
        return value


class SupplierTaxIdentifierUpdate(BaseModel):
    country_id: int | None = None
    identifier_type: str | None = Field(None, min_length=1, max_length=40)
    value: str | None = Field(None, min_length=1, max_length=200)
    is_primary: bool | None = None
    is_verified: bool | None = None
    verified_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class SupplierTaxIdentifierResponse(ORMOut):
    id: UUID
    supplier_id: int
    country_id: int
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool
    is_verified: bool
    verified_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierAddressCreate(BaseModel):
    address_type: Literal["fiscal", "billing", "delivery", "return", "office", "other"] = "other"
    line1: str = Field(..., min_length=1, max_length=240)
    line2: str | None = Field(None, max_length=240)
    country_id: int | None = None
    state_region: str | None = Field(None, max_length=120)
    city: str | None = Field(None, max_length=120)
    postal_code: str | None = Field(None, max_length=32)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    is_primary: bool = False


class SupplierAddressUpdate(SupplierAddressCreate):
    address_type: Literal["fiscal", "billing", "delivery", "return", "office", "other"] | None = None
    line1: str | None = Field(None, min_length=1, max_length=240)
    is_primary: bool | None = None


class SupplierAddressResponse(ORMOut):
    id: UUID
    supplier_id: int
    address_type: str
    line1: str
    line2: str | None = None
    country_id: int | None = None
    state_region: str | None = None
    city: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    is_primary: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierBankAccountCreate(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=160)
    account_holder: str = Field(..., min_length=1, max_length=200)
    account_number: str = Field(..., min_length=4, max_length=160)
    iban: str | None = Field(None, min_length=4, max_length=160)
    country_id: int | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    account_type: str | None = Field(None, max_length=32)
    is_primary: bool = False
    is_verified: bool = False
    status: Literal["active", "blocked", "closed"] = "active"

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class SupplierBankAccountUpdate(BaseModel):
    bank_name: str | None = Field(None, min_length=1, max_length=160)
    account_holder: str | None = Field(None, min_length=1, max_length=200)
    account_number: str | None = Field(None, min_length=4, max_length=160)
    iban: str | None = Field(None, min_length=4, max_length=160)
    country_id: int | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    account_type: str | None = Field(None, max_length=32)
    is_primary: bool | None = None
    is_verified: bool | None = None
    status: Literal["active", "blocked", "closed"] | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class SupplierBankAccountResponse(ORMOut):
    id: UUID
    supplier_id: int
    bank_name: str
    account_holder: str
    country_id: int | None = None
    currency_code: str | None = None
    account_type: str | None = None
    last_four: str
    is_primary: bool
    is_verified: bool
    status: str
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierGroupCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True


class SupplierGroupUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None


class SupplierGroupResponse(ORMOut):
    id: UUID
    company_id: UUID
    code: str
    name: str
    description: str | None = None
    is_active: bool


class PaymentTermsCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    net_days: int = Field(0, ge=0)
    discount_days: int = Field(0, ge=0)
    discount_percent: float = Field(0, ge=0, le=100)
    is_active: bool = True


class PaymentTermsUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=120)
    net_days: int | None = Field(None, ge=0)
    discount_days: int | None = Field(None, ge=0)
    discount_percent: float | None = Field(None, ge=0, le=100)
    is_active: bool | None = None


class PaymentTermsResponse(ORMOut):
    id: UUID
    company_id: UUID
    code: str
    name: str
    net_days: int
    discount_days: int
    discount_percent: float
    is_active: bool


class CurrencyResponse(ORMOut):
    code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool
