"""DTOs del punto de venta: cajas, turnos, efectivo, arqueo, depósitos y PIN (bloque V6a)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

ShiftStatusName = Literal["open", "counted", "recount", "closed"]
MovementKindName = Literal["cash_in", "cash_out", "safe_drop"]
FormName = Literal["coin", "bill"]
Money = Field(ge=0, max_digits=12, decimal_places=2)


class RegisterIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=80)
    opening_float: Decimal = Field(ge=0, le=10000, max_digits=12, decimal_places=2)
    cash_out_approval_threshold: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    cash_drawer_limit: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    is_active: bool = True


class RegisterCreateIn(RegisterIn):
    point_of_sale_id: uuid.UUID


class RegisterUpdateIn(RegisterIn):
    expected_version: int = Field(ge=1)


class RegisterOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    establishment_code: str
    point_of_sale_id: uuid.UUID
    point_of_sale_code: str
    code: str
    name: str
    opening_float: Decimal
    cash_out_approval_threshold: Decimal
    cash_drawer_limit: Decimal | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    unclosed_shift_id: uuid.UUID | None
    unclosed_shift_cashier: str | None
    has_shifts: bool


class PointOfSaleOptionOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    establishment_code: str
    branch_id: uuid.UUID
    branch_name: str
    available: bool
    unavailable_reason: str | None


class DenominationIn(BaseModel):
    form: FormName
    denomination: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    quantity: int = Field(ge=0, le=100000)


class DenominationOut(BaseModel):
    form: FormName
    denomination: Decimal
    quantity: int
    amount: Decimal


class SupervisorApprovalIn(BaseModel):
    supervisor_id: uuid.UUID
    pin: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OpenShiftIn(BaseModel):
    register_id: uuid.UUID
    denominations: list[DenominationIn] = Field(max_length=20)
    notes: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=120)


class MovementIn(BaseModel):
    kind: MovementKindName
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=5, max_length=200)
    reference: str | None = Field(default=None, max_length=60)
    approval: SupervisorApprovalIn | None = None
    idempotency_key: str = Field(min_length=8, max_length=120)


class CountIn(BaseModel):
    expected_version: int = Field(ge=1)
    denominations: list[DenominationIn] = Field(max_length=20)
    declared_card: Decimal = Money
    declared_transfer: Decimal = Money
    notes: str | None = Field(default=None, max_length=300)


class RecountIn(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=200)


class ApproveIn(BaseModel):
    expected_version: int = Field(ge=1)
    retained_float: Decimal = Money
    notes: str | None = Field(default=None, max_length=300)


class PersonOut(BaseModel):
    id: uuid.UUID
    name: str


class MovementOut(BaseModel):
    id: uuid.UUID
    kind: MovementKindName
    amount: Decimal
    reason: str
    reference: str | None
    authorized_by: PersonOut | None
    created_by: PersonOut
    created_at: datetime


class CountOut(BaseModel):
    id: uuid.UUID
    kind: Literal["opening", "closing"]
    sequence: int
    cash_total: Decimal
    card_total: Decimal | None
    transfer_total: Decimal | None
    notes: str | None
    counted_by: PersonOut
    counted_at: datetime
    denominations: list[DenominationOut]


class ShiftOut(BaseModel):
    """Un turno. Mientras no se cierra, el esperado y la diferencia solo los ve el supervisor."""

    id: uuid.UUID
    number: int
    code: str
    branch_id: uuid.UUID
    branch_name: str
    register_id: uuid.UUID
    register_code: str
    register_name: str
    cashier: PersonOut
    status: ShiftStatusName
    opening_float: Decimal
    opened_at: datetime
    counted_at: datetime | None
    recount_reason: str | None
    closed_at: datetime | None
    approved_by: PersonOut | None
    approval_notes: str | None
    counted_cash: Decimal | None
    declared_card: Decimal | None
    declared_transfer: Decimal | None
    expected_cash: Decimal | None
    cash_difference: Decimal | None
    expected_card: Decimal | None
    expected_transfer: Decimal | None
    retained_float: Decimal | None
    cash_to_deposit: Decimal | None
    deposit_id: uuid.UUID | None
    deposit_number: int | None
    version: int
    amounts_visible: bool


class ShiftTotalsOut(BaseModel):
    opening_float: Decimal
    cash_in: Decimal
    cash_out: Decimal
    safe_drops: Decimal
    cash_sales: Decimal
    cash_refunds: Decimal
    card_sales: Decimal
    card_refunds: Decimal
    transfer_sales: Decimal
    transfer_refunds: Decimal
    expected_cash: Decimal
    expected_card: Decimal
    expected_transfer: Decimal


class ShiftDetailOut(BaseModel):
    shift: ShiftOut
    register_detail: RegisterOut
    movements: list[MovementOut]
    counts: list[CountOut]
    totals: ShiftTotalsOut | None
    drawer_limit_reached: bool


class ShiftPage(BaseModel):
    items: list[ShiftOut]
    total: int
    limit: int
    offset: int


class MeOut(BaseModel):
    user: PersonOut
    shift: ShiftOut | None
    has_pin: bool
    can_supervise: bool


class PinIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    pin: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class DepositShiftOut(BaseModel):
    shift_id: uuid.UUID
    shift_number: int
    shift_code: str
    register_code: str
    cashier_name: str
    closed_at: datetime | None
    amount: Decimal


class DepositIn(BaseModel):
    branch_id: uuid.UUID
    shift_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    deposited_on: date
    bank_name: str = Field(min_length=2, max_length=80)
    account_reference: str = Field(min_length=2, max_length=40)
    slip_number: str = Field(min_length=2, max_length=40)
    deposited_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    notes: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=120)


class DepositOut(BaseModel):
    id: uuid.UUID
    number: int
    code: str
    branch_id: uuid.UUID
    branch_name: str
    deposited_on: date
    bank_name: str
    account_reference: str
    slip_number: str
    expected_amount: Decimal
    deposited_amount: Decimal
    difference: Decimal
    notes: str | None
    created_by_name: str
    created_at: datetime
    shifts: list[DepositShiftOut]
