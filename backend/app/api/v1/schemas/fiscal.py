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
    renta_operation_type: int | None = None
    renta_income_type: int | None = None


class ActivityRentaIn(BaseModel):
    model_config = _IN

    operation_type: int | None = None
    income_type: int | None = None


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


# --- SMTP propio de la empresa (bloque V3c) ---


class EmailSettingsIn(BaseModel):
    model_config = _IN

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    security: str = Field(pattern="^(none|starttls|ssl)$")
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=500)
    """Vacío al editar: se conserva la contraseña guardada. Nunca se devuelve."""
    from_address: str = Field(min_length=3, max_length=254)
    from_name: str | None = Field(default=None, max_length=150)
    is_enabled: bool = True


class EmailSettingsOut(BaseModel):
    configured: bool
    host: str | None = None
    port: int | None = None
    security: str | None = None
    username: str | None = None
    has_password: bool = False
    from_address: str | None = None
    from_name: str | None = None
    is_enabled: bool = False
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_error: str | None = None
    server_fallback: bool
    """Si el servidor tiene un SMTP propio que se usa cuando la empresa no configura el suyo."""


class EmailTestIn(BaseModel):
    model_config = _IN

    recipient: str = Field(min_length=3, max_length=254)


class EmailTestOut(BaseModel):
    ok: bool
    message: str


# --- Credenciales de Hacienda de la empresa (bloque V3d) ---


class HaciendaCredentialsIn(BaseModel):
    model_config = _IN

    api_password: str | None = Field(default=None, max_length=500)
    private_key_password: str | None = Field(default=None, max_length=500)
    certificate_base64: str | None = Field(default=None, max_length=360_000)
    """El ``.crt`` de Hacienda en base64. Vacío al editar: se conserva el guardado."""


class HaciendaCredentialsOut(BaseModel):
    configured: bool
    certificate_nit: str | None = None
    certificate_sha256: str | None = None
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_error: str | None = None
    updated_at: datetime | None = None


class HaciendaTestOut(BaseModel):
    ok: bool
    authentication_ok: bool
    authentication_message: str
    signature_ok: bool
    signature_message: str
