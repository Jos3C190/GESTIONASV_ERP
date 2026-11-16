"""DTOs del maestro de clientes con identidad fiscal."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.entities.customer import CustomerType, IdentityDocument
from app.domain.entities.fiscal import PersonType, TaxpayerCategory

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GeographyIn(BaseModel):
    model_config = _IN

    department_id: uuid.UUID
    municipality_id: uuid.UUID
    district_id: uuid.UUID


class CustomerIn(BaseModel):
    model_config = _IN

    customer_type: CustomerType = CustomerType.FINAL_CONSUMER
    name: str = Field(min_length=2, max_length=200)
    person_type: PersonType = PersonType.NATURAL
    taxpayer_category: TaxpayerCategory | None = None
    is_withholding_agent: bool = False
    commercial_name: str | None = Field(default=None, max_length=200)
    document_type: IdentityDocument | None = None
    document_number: str | None = Field(default=None, max_length=30)
    nrc: str | None = Field(default=None, max_length=12)
    activity_code: str | None = Field(default=None, max_length=6)
    geography: GeographyIn | None = None
    address_line: str | None = Field(default=None, max_length=200)
    country_code: str | None = Field(default=None, max_length=4)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    credit_days: int = Field(default=0, ge=0, le=365)
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    seller_employee_id: uuid.UUID | None = None


class CustomerCreate(CustomerIn):
    code: str | None = Field(default=None, max_length=40)


class CustomerStatusIn(BaseModel):
    model_config = _IN

    is_active: bool


class AddressOut(BaseModel):
    department_id: uuid.UUID | None
    municipality_id: uuid.UUID | None
    district_id: uuid.UUID | None
    department: str | None
    department_code: str | None
    municipality: str | None
    municipality_code: str | None
    district: str | None
    district_code: str | None


class DeliveryAddressIn(BaseModel):
    model_config = _IN

    label: str = Field(min_length=2, max_length=80)
    address_line: str = Field(min_length=3, max_length=200)
    geography: GeographyIn | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    contact_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    is_default: bool = False
    is_active: bool = True


class DeliveryAddressOut(BaseModel):
    id: uuid.UUID
    label: str
    address_line: str
    address: AddressOut
    latitude: Decimal | None
    longitude: Decimal | None
    contact_name: str | None
    phone: str | None
    is_default: bool
    is_active: bool


class CustomerOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    customer_type: CustomerType
    name: str
    person_type: PersonType
    taxpayer_category: TaxpayerCategory | None
    is_withholding_agent: bool
    commercial_name: str | None
    document_type: IdentityDocument | None
    document_number: str | None
    nrc: str | None
    activity_code: str | None
    activity_name: str | None
    address: AddressOut
    address_line: str | None
    country_code: str | None
    country_name: str | None
    phone: str | None
    email: str | None
    credit_days: int
    credit_limit: Decimal | None
    seller_employee_id: uuid.UUID | None
    seller_name: str | None
    anonymized_at: datetime | None
    is_active: bool
    is_generic: bool
    branch_id: uuid.UUID | None
    receivable_documents: list[str]
    tax_credit_missing: list[str]
    delivery_addresses: list[DeliveryAddressOut]
    created_at: datetime
    updated_at: datetime


class SellerOptionOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    position: str | None


class CustomerPageMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    meta: CustomerPageMeta
