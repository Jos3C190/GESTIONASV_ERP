"""Domain entities: Supplier, SupplierContact."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.media_image import SingleImage


@dataclass(frozen=True, slots=True)
class SupplierContact:
    id: int
    supplier_id: int
    full_name: str
    uuid: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    avatar_image: SingleImage | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Supplier:
    id: int
    uuid: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    country_id: int
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    is_active: bool = True
    legal_name: str | None = None
    supplier_group_id: uuid.UUID | None = None
    supplier_status: str = "approved"
    hold_reason: str | None = None
    hold_from: datetime | None = None
    hold_until: datetime | None = None
    default_currency_code: str | None = None
    payment_terms_id: uuid.UUID | None = None
    default_payment_method: str | None = None
    external_reference: str | None = None
    logo_image: SingleImage | None = None
    tax_identifiers: tuple[SupplierTaxIdentifier, ...] = ()
    addresses: tuple[SupplierAddress, ...] = ()
    bank_accounts: tuple[SupplierBankAccount, ...] = ()
    contacts: tuple[SupplierContact, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SupplierTaxIdentifier:
    id: uuid.UUID
    supplier_id: int
    country_id: int
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False
    is_verified: bool = False
    verified_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class SupplierAddress:
    id: uuid.UUID
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
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class SupplierBankAccount:
    id: uuid.UUID
    supplier_id: int
    bank_name: str
    account_holder: str
    country_id: int | None
    currency_code: str | None
    account_type: str | None
    last_four: str
    is_primary: bool = False
    is_verified: bool = False
    status: str = "active"
    verified_at: datetime | None = None
