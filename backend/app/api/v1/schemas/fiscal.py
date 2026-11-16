"""DTOs de la configuración fiscal del emisor de DTE."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.entities.fiscal import (
    CertificationStatus,
    EstablishmentType,
    OperatingMode,
    PersonType,
    TaxpayerCategory,
)

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CatalogSummaryOut(BaseModel):
    code: str
    title: str


class CatalogItemOut(BaseModel):
    group_code: str
    code: str
    name: str


class FiscalProfileOut(BaseModel):
    company_id: uuid.UUID
    company_name: str
    commercial_name: str
    nit: str
    nrc: str
    taxpayer_category: TaxpayerCategory
    person_type: PersonType
    operating_mode: OperatingMode
    dte_email: str | None
    dte_phone: str | None
    configured: bool
    updated_at: datetime | None
    production_blockers: list[str]


class FiscalProfileIn(BaseModel):
    model_config = _IN

    taxpayer_category: TaxpayerCategory
    person_type: PersonType
    operating_mode: OperatingMode
    dte_email: EmailStr | None = Field(default=None, max_length=100)
    dte_phone: str | None = Field(default=None, min_length=8, max_length=30)


class EconomicActivityOut(BaseModel):
    id: uuid.UUID
    code: str
    description: str
    is_primary: bool


class EconomicActivityIn(BaseModel):
    model_config = _IN

    code: str = Field(min_length=5, max_length=6, pattern=r"^[0-9]{5,6}$")
    is_primary: bool = False


class PointOfSaleOut(BaseModel):
    id: uuid.UUID
    establishment_id: uuid.UUID
    code: str
    name: str
    is_active: bool


class PointOfSaleIn(BaseModel):
    model_config = _IN

    code: str = Field(min_length=4, max_length=4)
    name: str = Field(min_length=2, max_length=120)


class PointOfSaleUpdate(PointOfSaleIn):
    is_active: bool


class EstablishmentAddressOut(BaseModel):
    department: str
    department_code: str | None
    municipality: str
    municipality_code: str | None
    district: str
    district_code: str | None
    complement: str
    complete: bool


class EstablishmentOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    establishment_type: EstablishmentType
    code: str
    activity_id: uuid.UUID | None
    activity_code: str | None
    is_active: bool
    address: EstablishmentAddressOut
    phone: str | None
    email: str | None
    points_of_sale: list[PointOfSaleOut]


class EstablishmentIn(BaseModel):
    model_config = _IN

    branch_id: uuid.UUID
    establishment_type: EstablishmentType
    code: str = Field(min_length=4, max_length=4)
    activity_id: uuid.UUID | None = None


class EstablishmentUpdate(BaseModel):
    model_config = _IN

    establishment_type: EstablishmentType
    code: str = Field(min_length=4, max_length=4)
    activity_id: uuid.UUID | None = None
    is_active: bool


class BranchOptionOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    is_headquarters: bool
    establishment_id: uuid.UUID | None


class DocumentTypeOut(BaseModel):
    document_type: str
    name: str
    is_enabled: bool
    certification_status: CertificationStatus
    certified_at: datetime | None
    notes: str | None


class DocumentTypeIn(BaseModel):
    model_config = _IN

    is_enabled: bool
    certification_status: CertificationStatus
    notes: str | None = Field(default=None, max_length=1000)
