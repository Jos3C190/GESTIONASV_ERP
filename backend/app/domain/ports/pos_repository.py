"""Punto de venta: cajas, turnos, efectivo, conteos, depósitos y PIN de supervisor (bloque V6a)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.pos import (
    CashMovementKind,
    CountKind,
    DenominationCount,
    ShiftStatus,
    ShiftTotals,
)


@dataclass(frozen=True)
class Register:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    establishment_id: uuid.UUID
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
    unclosed_shift_id: uuid.UUID | None = None
    unclosed_shift_cashier: str | None = None
    has_shifts: bool = False


@dataclass(frozen=True)
class RegisterData:
    code: str
    name: str
    opening_float: Decimal
    cash_out_approval_threshold: Decimal
    cash_drawer_limit: Decimal | None
    is_active: bool = True


@dataclass(frozen=True)
class PointOfSaleOption:
    id: uuid.UUID
    code: str
    name: str
    establishment_id: uuid.UUID
    establishment_code: str
    branch_id: uuid.UUID
    branch_name: str
    is_active: bool
    establishment_active: bool
    register_id: uuid.UUID | None


@dataclass(frozen=True)
class Shift:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    register_id: uuid.UUID
    register_code: str
    register_name: str
    cashier_id: uuid.UUID
    cashier_name: str
    number: int
    status: ShiftStatus
    opening_float: Decimal
    opened_at: datetime
    counted_at: datetime | None
    recount_reason: str | None
    closed_at: datetime | None
    approved_by_id: uuid.UUID | None
    approved_by_name: str | None
    approval_notes: str | None
    expected_cash: Decimal | None
    counted_cash: Decimal | None
    cash_difference: Decimal | None
    expected_card: Decimal | None
    declared_card: Decimal | None
    expected_transfer: Decimal | None
    declared_transfer: Decimal | None
    retained_float: Decimal | None
    cash_to_deposit: Decimal | None
    version: int
    idempotency_key: str
    deposit_id: uuid.UUID | None = None
    deposit_number: int | None = None


@dataclass(frozen=True)
class CashMovement:
    id: uuid.UUID
    shift_id: uuid.UUID
    kind: CashMovementKind
    amount: Decimal
    reason: str
    reference: str | None
    authorized_by_id: uuid.UUID | None
    authorized_by_name: str | None
    created_by_id: uuid.UUID
    created_by_name: str
    created_at: datetime
    idempotency_key: str


@dataclass(frozen=True)
class ShiftCount:
    id: uuid.UUID
    kind: CountKind
    sequence: int
    cash_total: Decimal
    card_total: Decimal | None
    transfer_total: Decimal | None
    notes: str | None
    counted_by_id: uuid.UUID
    counted_by_name: str
    counted_at: datetime
    lines: tuple[DenominationCount, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DepositShift:
    shift_id: uuid.UUID
    shift_number: int
    register_code: str
    cashier_name: str
    closed_at: datetime | None
    amount: Decimal


@dataclass(frozen=True)
class Deposit:
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    number: int
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
    idempotency_key: str
    shifts: tuple[DepositShift, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Person:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class ShiftFilter:
    branch_ids: Sequence[uuid.UUID] | None = None
    statuses: Sequence[ShiftStatus] | None = None
    register_id: uuid.UUID | None = None
    cashier_id: uuid.UUID | None = None
    opened_from: date | None = None
    opened_to: date | None = None
    limit: int = 50
    offset: int = 0


class PosRepository(Protocol):
    # --- cajas -----------------------------------------------------------------------------------
    async def registers(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Register]: ...

    async def register(
        self, company_id: uuid.UUID, register_id: uuid.UUID, *, lock: bool = False
    ) -> Register | None: ...

    async def point_of_sale_options(self, company_id: uuid.UUID) -> list[PointOfSaleOption]: ...

    async def point_of_sale(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSaleOption | None: ...

    async def register_code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude: uuid.UUID | None = None
    ) -> bool: ...

    async def create_register(
        self,
        *,
        company_id: uuid.UUID,
        point_of_sale: PointOfSaleOption,
        data: RegisterData,
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    async def update_register(
        self,
        *,
        company_id: uuid.UUID,
        register_id: uuid.UUID,
        data: RegisterData,
        actor_id: uuid.UUID,
    ) -> None: ...

    # --- turnos ----------------------------------------------------------------------------------
    async def shift(
        self, company_id: uuid.UUID, shift_id: uuid.UUID, *, lock: bool = False
    ) -> Shift | None: ...

    async def shift_by_key(self, company_id: uuid.UUID, key: str) -> Shift | None: ...

    async def unclosed_shift_for_cashier(
        self, company_id: uuid.UUID, cashier_id: uuid.UUID
    ) -> Shift | None: ...

    async def unclosed_shift_for_register(
        self, company_id: uuid.UUID, register_id: uuid.UUID
    ) -> Shift | None: ...

    async def shifts(
        self, company_id: uuid.UUID, filters: ShiftFilter
    ) -> tuple[list[Shift], int]: ...

    async def create_shift(
        self,
        *,
        company_id: uuid.UUID,
        register: Register,
        cashier_id: uuid.UUID,
        opening_float: Decimal,
        idempotency_key: str,
    ) -> uuid.UUID: ...

    async def totals(self, company_id: uuid.UUID, shift: Shift) -> ShiftTotals: ...

    async def mark_counted(
        self,
        *,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        counted_cash: Decimal,
        declared_card: Decimal,
        declared_transfer: Decimal,
        totals: ShiftTotals,
    ) -> None: ...

    async def mark_recount(
        self, *, company_id: uuid.UUID, shift_id: uuid.UUID, reason: str
    ) -> None: ...

    async def close(
        self,
        *,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        approved_by_id: uuid.UUID,
        notes: str | None,
        totals: ShiftTotals,
        cash_difference: Decimal,
        retained_float: Decimal,
        cash_to_deposit: Decimal,
    ) -> None: ...

    # --- efectivo y conteos ----------------------------------------------------------------------
    async def movements(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> list[CashMovement]: ...

    async def movement_by_key(self, company_id: uuid.UUID, key: str) -> CashMovement | None: ...

    async def add_movement(
        self,
        *,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        kind: CashMovementKind,
        amount: Decimal,
        reason: str,
        reference: str | None,
        authorized_by_id: uuid.UUID | None,
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> uuid.UUID: ...

    async def counts(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> list[ShiftCount]: ...

    async def add_count(
        self,
        *,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        kind: CountKind,
        lines: Sequence[DenominationCount],
        cash_total: Decimal,
        card_total: Decimal | None,
        transfer_total: Decimal | None,
        notes: str | None,
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    # --- depósitos -------------------------------------------------------------------------------
    async def deposit_candidates(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, lock: bool = False
    ) -> list[DepositShift]: ...

    async def deposits(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Deposit]: ...

    async def deposit(self, company_id: uuid.UUID, deposit_id: uuid.UUID) -> Deposit | None: ...

    async def deposit_by_key(self, company_id: uuid.UUID, key: str) -> Deposit | None: ...

    async def slip_taken(self, company_id: uuid.UUID, bank_name: str, slip_number: str) -> bool: ...

    async def create_deposit(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        deposited_on: date,
        bank_name: str,
        account_reference: str,
        slip_number: str,
        expected_amount: Decimal,
        deposited_amount: Decimal,
        difference: Decimal,
        notes: str | None,
        shifts: Sequence[DepositShift],
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> uuid.UUID: ...

    # --- personas y PIN --------------------------------------------------------------------------
    async def person(self, user_id: uuid.UUID) -> Person | None: ...

    async def supervisors(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> list[Person]: ...

    async def can_supervise(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool: ...

    async def has_pin(self, user_id: uuid.UUID) -> bool: ...

    async def password_hash(self, user_id: uuid.UUID) -> str | None: ...

    async def set_pin(self, user_id: uuid.UUID, pin_hash: str) -> None: ...


class PinAttempts(Protocol):
    """Verifica un PIN en su propia transacción, para que un intento fallido quede contado."""

    async def verify(self, user_id: uuid.UUID, pin: str) -> PinCheck: ...


@dataclass(frozen=True)
class PinCheck:
    ok: bool
    configured: bool
    locked_until: datetime | None
    remaining_attempts: int
