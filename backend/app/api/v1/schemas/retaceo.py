"""Pydantic DTOs for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.retaceo import RetaceoCostClass, RetaceoImportData, RetaceoStatus
from app.domain.entities.retaceo_calculation import CalculationMode


class RetaceoImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    origin_country: str | None = Field(default=None, max_length=120)
    import_invoice_number: str | None = Field(default=None, max_length=80)
    import_invoice_date: date | None = None
    import_policy_number: str | None = Field(default=None, max_length=80)
    import_policy_date: date | None = None

    def to_domain(self) -> RetaceoImportData:
        return RetaceoImportData(**self.model_dump())


class RetaceoFobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_detail_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class RetaceoCalculationInput(BaseModel):
    calculation_mode: CalculationMode | None = None
    dai_rate: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=10, decimal_places=6)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=10, decimal_places=6)
    total_dai: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    import_vat: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    fob_lines: tuple[RetaceoFobInput, ...] | None = Field(
        default=None, min_length=1, max_length=200
    )

    @model_validator(mode="after")
    def validate_calculation(self) -> Self:
        if self.calculation_mode == "automatic":
            if self.dai_rate is None or self.vat_rate is None:
                raise ValueError("Ingrese los porcentajes de DAI e IVA para el cálculo automático.")
            if self.fob_lines is not None:
                raise ValueError("El modo automático toma el FOB de la compra.")
        else:
            if self.total_dai is None or self.import_vat is None:
                raise ValueError("Ingrese los importes de DAI e IVA en modo manual.")
            if self.dai_rate is not None or self.vat_rate is not None:
                raise ValueError("Seleccione automático para calcular desde porcentajes.")
        return self


class RetaceoCreate(RetaceoCalculationInput):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_id: uuid.UUID
    import_data: RetaceoImportInput | None = None
    total_freight: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_expenses: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    notes: str | None = Field(default=None, max_length=4000)


class RetaceoCostAllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_detail_id: uuid.UUID
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=6)


class RetaceoCostInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: uuid.UUID | None = None
    classification: RetaceoCostClass
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    allocations: tuple[RetaceoCostAllocationInput, ...] = Field(default_factory=tuple)
    expense_type_id: uuid.UUID | None = None
    source_purchase_order_expense_id: uuid.UUID | None = None
    incurred_on: date | None = None


class RetaceoCostDocumentInitiate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class RetaceoUpdate(RetaceoCalculationInput):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    import_data: RetaceoImportInput | None = None

    total_freight: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_expenses: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    notes: str | None = Field(default=None, max_length=4000)
    costs: tuple[RetaceoCostInput, ...] | None = None


class RetaceoCostAllocationResponse(ORMOut):
    purchase_detail_id: uuid.UUID
    amount: Decimal


class RetaceoCostDocumentResponse(ORMOut):
    id: uuid.UUID
    retaceo_cost_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    file_type: str
    size_bytes: int | None = None
    status: str | None = None
    failure_code: str | None = None
    uploaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetaceoCostDocumentUploadResponse(BaseModel):
    document: RetaceoCostDocumentResponse
    upload_url: str
    method: str = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


class RetaceoCostResponse(ORMOut):
    id: uuid.UUID
    retaceo_id: uuid.UUID
    source_purchase_order_expense_id: uuid.UUID | None = None
    expense_type_id: uuid.UUID | None = None
    classification: RetaceoCostClass
    title: str
    description: str | None = None
    amount: Decimal
    is_active: bool
    allocations: tuple[RetaceoCostAllocationResponse, ...] = ()
    documents: tuple[RetaceoCostDocumentResponse, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    incurred_on: date | None = None


class RetaceoDetailResponse(ORMOut):
    id: uuid.UUID
    retaceo_id: uuid.UUID
    purchase_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    cost_fob: Decimal
    freight: Decimal
    expenses: Decimal
    dai: Decimal
    total_cost: Decimal
    unit_cost: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetaceoValuationStatus(ORMOut):
    enabled: bool
    inventory_after_retaceo: bool = False


class RetaceoAverageLineResponse(ORMOut):
    product_id: int
    inventory_item_id: uuid.UUID
    base_unit_id: int
    previous_quantity: Decimal
    previous_value: Decimal
    previous_average: Decimal
    incoming_quantity: Decimal
    incoming_value: Decimal
    resulting_quantity: Decimal
    resulting_value: Decimal
    resulting_average: Decimal


class RetaceoAverageComparisonResponse(ORMOut):
    currency: str
    mode: str
    lines: tuple[RetaceoAverageLineResponse, ...]
    value_only: bool = False


class RetaceoResponse(ORMOut):
    calculation_mode: CalculationMode = "manual"
    dai_rate: Decimal | None = None
    vat_rate: Decimal | None = None
    manual_entry: bool = False
    origin_country: str | None = None
    import_invoice_number: str | None = None
    import_invoice_date: date | None = None
    import_policy_number: str | None = None
    import_policy_date: date | None = None
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    purchase_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    created_by_id: uuid.UUID
    currency: str
    details: tuple[RetaceoDetailResponse, ...]
    costs: tuple[RetaceoCostResponse, ...] = ()
    total_fob: Decimal
    total_freight: Decimal
    total_expenses: Decimal
    total_dai: Decimal
    import_vat: Decimal
    total_cost: Decimal
    freight_percentage: Decimal
    expense_percentage: Decimal
    dai_percentage: Decimal
    status: RetaceoStatus
    applied_at: datetime | None = None
    applied_by: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "RetaceoCostAllocationInput",
    "RetaceoCostAllocationResponse",
    "RetaceoCostDocumentInitiate",
    "RetaceoCostDocumentResponse",
    "RetaceoCostDocumentUploadResponse",
    "RetaceoCostInput",
    "RetaceoCostResponse",
    "RetaceoCreate",
    "RetaceoDetailResponse",
    "RetaceoResponse",
    "RetaceoUpdate",
]
