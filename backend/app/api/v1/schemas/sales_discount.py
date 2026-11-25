"""DTOs de topes de descuento, escalas por volumen y evaluación (bloque V2c)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DiscountPolicyIn(BaseModel):
    model_config = _IN

    max_line_discount_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    max_global_discount_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class DiscountPolicyOut(BaseModel):
    max_line_discount_percent: Decimal
    max_global_discount_percent: Decimal


class RolePolicyOut(DiscountPolicyOut):
    role_id: uuid.UUID
    role_name: str
    configured: bool
    updated_at: datetime | None


class VolumeDiscountIn(BaseModel):
    model_config = _IN

    product_id: int = Field(gt=0)
    variant_id: uuid.UUID | None = None
    unit_id: int = Field(gt=0)
    min_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    discount_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    valid_from: date | None = None


class VolumeDiscountOut(BaseModel):
    id: uuid.UUID
    price_list_id: uuid.UUID
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    min_quantity: Decimal
    discount_percent: Decimal
    valid_from: date
    valid_to: date | None
    status: str


class EvaluationLineIn(BaseModel):
    model_config = _IN

    product_id: int = Field(gt=0)
    variant_id: uuid.UUID | None = None
    unit_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    discount_percent: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )


class EvaluationIn(BaseModel):
    model_config = _IN

    customer_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    on: date | None = None
    global_discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    lines: list[EvaluationLineIn] = Field(min_length=1, max_length=500)


class EvaluationLineOut(BaseModel):
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    quantity: Decimal
    found: bool
    message: str | None
    price_list_id: uuid.UUID | None
    price_list_name: str | None
    prices_include_vat: bool | None
    list_price: Decimal | None
    suggested_discount_percent: Decimal | None
    suggested_discount_source: str | None
    discount_percent: Decimal | None
    net_price: Decimal | None
    cost: Decimal | None
    margin_percent: Decimal | None
    requires_authorization: bool
    below_cost: bool = False
    """Queda bajo el costo del kardex: se bloquea, no se autoriza."""
    reasons: list[str]
    reason_messages: list[str]


class EvaluationOut(BaseModel):
    policy: DiscountPolicyOut
    lines: list[EvaluationLineOut]
    global_discount_percent: Decimal
    global_reasons: list[str]
    requires_authorization: bool
