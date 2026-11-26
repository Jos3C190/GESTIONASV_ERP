"""Cajas, turnos, efectivo, arqueo ciego, depósitos y autorización de supervisor (bloque V6a).

Los permisos y el alcance por sucursal se validan en el router; aquí viven las reglas que dependen
del estado: de quién es el turno, en qué estado está, cuánto efectivo hay y quién puede autorizar.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.domain.entities.pos import (
    MAX_NOTES,
    MIN_REASON,
    ZERO,
    CashMovementKind,
    CountKind,
    DenominationCount,
    ShiftStatus,
    ShiftTotals,
    count_total,
    decide_closing,
    money,
    require_countable,
    require_open,
    require_other_person,
    require_reviewable,
    validate_count,
    validate_deposit,
    validate_movement,
    validate_opening,
    validate_pin,
    validate_reason,
    validate_register,
)
from app.domain.ports.pos_repository import (
    CashMovement,
    Deposit,
    DepositShift,
    Person,
    PinAttempts,
    PosRepository,
    Register,
    RegisterData,
    Shift,
    ShiftCount,
    ShiftFilter,
)

MIN_KEY = 8


@dataclass(frozen=True)
class SupervisorApproval:
    """El supervisor que autoriza en la caja, con su PIN."""

    supervisor_id: uuid.UUID
    pin: str


@dataclass(frozen=True)
class ShiftDetail:
    shift: Shift
    register: Register
    movements: list[CashMovement]
    counts: list[ShiftCount]
    totals: ShiftTotals
    drawer_limit_reached: bool


def _not_found_register() -> NotFoundError:
    return NotFoundError("Caja no encontrada.", code="pos_register_not_found")


def _not_found_shift() -> NotFoundError:
    return NotFoundError("Turno no encontrado.", code="pos_shift_not_found")


def _key(value: str) -> str:
    key = value.strip()
    if len(key) < MIN_KEY:
        raise BusinessRuleError("Falta la clave de idempotencia.", code="pos_idempotency_key")
    return key


def _notes(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    if len(text) > MAX_NOTES:
        raise BusinessRuleError("Las notas admiten hasta 300 caracteres.", code="pos_notes_long")
    return text or None


def _declared(value: Decimal, label: str) -> Decimal:
    if value < ZERO or money(value) != value:
        raise BusinessRuleError(
            f"El total de {label} debe ser $0.00 o más, con centavos.", code="pos_declared_invalid"
        )
    return value


class PosUseCases:
    def __init__(
        self,
        repository: PosRepository,
        pins: PinAttempts,
        *,
        hash_pin: Callable[[str], str],
        verify_password: Callable[[str, str], bool],
    ) -> None:
        self._repository = repository
        self._pins = pins
        self._hash_pin = hash_pin
        self._verify_password = verify_password

    # --- cajas -----------------------------------------------------------------------------------

    async def registers(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Register]:
        return await self._repository.registers(company_id, branch_ids)

    async def register(self, company_id: uuid.UUID, register_id: uuid.UUID) -> Register:
        found = await self._repository.register(company_id, register_id)
        if found is None:
            raise _not_found_register()
        return found

    async def create_register(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        point_of_sale_id: uuid.UUID,
        data: RegisterData,
    ) -> Register:
        data = self._clean_register(data)
        point = await self._repository.point_of_sale(company_id, point_of_sale_id)
        if point is None:
            raise NotFoundError(
                "Punto de venta fiscal no encontrado.", code="pos_point_of_sale_not_found"
            )
        if not point.is_active or not point.establishment_active:
            raise BusinessRuleError(
                "El punto de venta o su establecimiento están inactivos en la configuración fiscal.",
                code="pos_point_of_sale_inactive",
            )
        if point.register_id is not None:
            raise ConflictError(
                f"El punto de venta {point.code} ya tiene una caja.",
                code="pos_point_of_sale_taken",
            )
        await self._require_free_code(company_id, data.code)
        register_id = await self._repository.create_register(
            company_id=company_id, point_of_sale=point, data=data, actor_id=actor_id
        )
        return await self.register(company_id, register_id)

    async def update_register(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        register_id: uuid.UUID,
        expected_version: int,
        data: RegisterData,
    ) -> Register:
        data = self._clean_register(data)
        current = await self._repository.register(company_id, register_id, lock=True)
        if current is None:
            raise _not_found_register()
        if current.version != expected_version:
            raise ConflictError(
                "Otra persona cambió la caja; vuelve a abrirla.", code="pos_register_version"
            )
        if data.code != current.code:
            if current.has_shifts:
                raise BusinessRuleError(
                    "El código de una caja con turnos no cambia: aparece en sus tiquetes y cierres.",
                    code="pos_register_code_locked",
                )
            await self._require_free_code(company_id, data.code, exclude=register_id)
        if not data.is_active and current.unclosed_shift_id is not None:
            raise ConflictError(
                "La caja tiene un turno sin cerrar; ciérralo antes de desactivarla.",
                code="pos_register_has_open_shift",
            )
        await self._repository.update_register(
            company_id=company_id, register_id=register_id, data=data, actor_id=actor_id
        )
        return await self.register(company_id, register_id)

    async def _require_free_code(
        self, company_id: uuid.UUID, code: str, *, exclude: uuid.UUID | None = None
    ) -> None:
        if await self._repository.register_code_taken(company_id, code, exclude=exclude):
            raise ConflictError(
                f"Ya existe una caja con el código {code}.", code="pos_register_code_taken"
            )

    @staticmethod
    def _clean_register(data: RegisterData) -> RegisterData:
        cleaned = RegisterData(
            code=data.code.strip().upper(),
            name=" ".join(data.name.split()),
            opening_float=money(data.opening_float),
            cash_out_approval_threshold=money(data.cash_out_approval_threshold),
            cash_drawer_limit=None
            if data.cash_drawer_limit is None
            else money(data.cash_drawer_limit),
            is_active=data.is_active,
        )
        validate_register(
            code=cleaned.code,
            name=cleaned.name,
            opening_float=cleaned.opening_float,
            cash_out_approval_threshold=cleaned.cash_out_approval_threshold,
            cash_drawer_limit=cleaned.cash_drawer_limit,
        )
        return cleaned

    # --- turnos ----------------------------------------------------------------------------------

    async def open_shift(
        self,
        company_id: uuid.UUID,
        cashier_id: uuid.UUID,
        register_id: uuid.UUID,
        lines: Sequence[DenominationCount],
        notes: str | None,
        idempotency_key: str,
    ) -> Shift:
        key = _key(idempotency_key)
        repeated = await self._repository.shift_by_key(company_id, key)
        if repeated is not None:
            if repeated.register_id != register_id or repeated.cashier_id != cashier_id:
                raise ConflictError(
                    "La clave de idempotencia ya se usó para otro turno.",
                    code="pos_idempotency_conflict",
                )
            return repeated
        register = await self._repository.register(company_id, register_id, lock=True)
        if register is None:
            raise _not_found_register()
        if not register.is_active:
            raise BusinessRuleError("La caja está desactivada.", code="pos_register_inactive")
        own = await self._repository.unclosed_shift_for_cashier(company_id, cashier_id)
        if own is not None:
            raise ConflictError(
                f"Ya tienes el turno {own.number} sin cerrar en la caja {own.register_code}.",
                code="pos_cashier_has_shift",
            )
        busy = await self._repository.unclosed_shift_for_register(company_id, register_id)
        if busy is not None:
            raise ConflictError(
                f"La caja {register.code} tiene el turno de {busy.cashier_name} sin cerrar.",
                code="pos_register_busy",
            )
        counted = validate_count(lines)
        opening = validate_opening(count_total(counted))
        clean_notes = _notes(notes)
        if opening != register.opening_float and (
            clean_notes is None or len(clean_notes) < MIN_REASON
        ):
            raise BusinessRuleError(
                f"El fondo contado (${opening:,.2f}) no coincide con el de la caja "
                f"(${register.opening_float:,.2f}): explica la diferencia.",
                code="pos_opening_float_differs",
            )
        shift_id = await self._repository.create_shift(
            company_id=company_id,
            register=register,
            cashier_id=cashier_id,
            opening_float=opening,
            idempotency_key=key,
        )
        await self._repository.add_count(
            company_id=company_id,
            shift_id=shift_id,
            kind=CountKind.OPENING,
            lines=counted,
            cash_total=opening,
            card_total=None,
            transfer_total=None,
            notes=clean_notes,
            actor_id=cashier_id,
        )
        return await self._shift(company_id, shift_id)

    async def current_shift(self, company_id: uuid.UUID, cashier_id: uuid.UUID) -> Shift | None:
        return await self._repository.unclosed_shift_for_cashier(company_id, cashier_id)

    async def shifts(self, company_id: uuid.UUID, filters: ShiftFilter) -> tuple[list[Shift], int]:
        return await self._repository.shifts(company_id, filters)

    async def shift(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        return await self._shift(company_id, shift_id)

    async def detail(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> ShiftDetail:
        shift = await self._shift(company_id, shift_id)
        register = await self.register(company_id, shift.register_id)
        totals = await self._repository.totals(company_id, shift)
        limit = register.cash_drawer_limit
        return ShiftDetail(
            shift=shift,
            register=register,
            movements=await self._repository.movements(company_id, shift_id),
            counts=await self._repository.counts(company_id, shift_id),
            totals=totals,
            drawer_limit_reached=(
                shift.status is ShiftStatus.OPEN
                and limit is not None
                and totals.expected_cash >= limit
            ),
        )

    async def _shift(
        self, company_id: uuid.UUID, shift_id: uuid.UUID, *, lock: bool = False
    ) -> Shift:
        found = await self._repository.shift(company_id, shift_id, lock=lock)
        if found is None:
            raise _not_found_shift()
        return found

    async def _own_shift(
        self, company_id: uuid.UUID, cashier_id: uuid.UUID, shift_id: uuid.UUID
    ) -> Shift:
        shift = await self._shift(company_id, shift_id, lock=True)
        if shift.cashier_id != cashier_id:
            raise AuthorizationError(
                "Solo el cajero del turno puede operarlo.", code="pos_shift_not_yours"
            )
        return shift

    # --- efectivo --------------------------------------------------------------------------------

    async def add_movement(
        self,
        company_id: uuid.UUID,
        cashier_id: uuid.UUID,
        shift_id: uuid.UUID,
        *,
        kind: CashMovementKind,
        amount: Decimal,
        reason: str,
        reference: str | None,
        approval: SupervisorApproval | None,
        idempotency_key: str,
    ) -> CashMovement:
        key = _key(idempotency_key)
        repeated = await self._repository.movement_by_key(company_id, key)
        if repeated is not None:
            if (
                repeated.shift_id != shift_id
                or repeated.kind is not kind
                or repeated.amount != amount
            ):
                raise ConflictError(
                    "La clave de idempotencia ya se usó para otro movimiento.",
                    code="pos_idempotency_conflict",
                )
            return repeated
        shift = await self._own_shift(company_id, cashier_id, shift_id)
        require_open(shift.status)
        register = await self.register(company_id, shift.register_id)
        totals = await self._repository.totals(company_id, shift)
        authorizer = (
            await self.authorize(company_id, shift.branch_id, cashier_id, approval)
            if approval is not None
            else None
        )
        validate_movement(
            kind=kind,
            amount=amount,
            available_cash=totals.expected_cash,
            approval_threshold=register.cash_out_approval_threshold,
            authorized=authorizer is not None,
        )
        clean_reference = " ".join((reference or "").split()) or None
        if clean_reference is not None and len(clean_reference) > 60:  # noqa: PLR2004
            raise BusinessRuleError(
                "La referencia admite hasta 60 caracteres.", code="pos_reference_long"
            )
        movement_id = await self._repository.add_movement(
            company_id=company_id,
            shift_id=shift_id,
            kind=kind,
            amount=amount,
            reason=validate_reason(reason),
            reference=clean_reference,
            authorized_by_id=authorizer,
            actor_id=cashier_id,
            idempotency_key=key,
        )
        movements = await self._repository.movements(company_id, shift_id)
        return next(item for item in movements if item.id == movement_id)

    # --- cierre ----------------------------------------------------------------------------------

    async def count(
        self,
        company_id: uuid.UUID,
        cashier_id: uuid.UUID,
        shift_id: uuid.UUID,
        *,
        expected_version: int,
        lines: Sequence[DenominationCount],
        declared_card: Decimal,
        declared_transfer: Decimal,
        notes: str | None,
    ) -> Shift:
        shift = await self._own_shift(company_id, cashier_id, shift_id)
        if shift.version != expected_version:
            raise ConflictError("El turno cambió; vuelve a abrirlo.", code="pos_shift_version")
        require_countable(shift.status)
        counted = validate_count(lines)
        cash = count_total(counted)
        card = _declared(declared_card, "tarjeta")
        transfer = _declared(declared_transfer, "transferencias")
        totals = await self._repository.totals(company_id, shift)
        await self._repository.add_count(
            company_id=company_id,
            shift_id=shift_id,
            kind=CountKind.CLOSING,
            lines=counted,
            cash_total=cash,
            card_total=card,
            transfer_total=transfer,
            notes=_notes(notes),
            actor_id=cashier_id,
        )
        await self._repository.mark_counted(
            company_id=company_id,
            shift_id=shift_id,
            counted_cash=cash,
            declared_card=card,
            declared_transfer=transfer,
            totals=totals,
        )
        return await self._shift(company_id, shift_id)

    async def request_recount(
        self,
        company_id: uuid.UUID,
        supervisor_id: uuid.UUID,
        shift_id: uuid.UUID,
        *,
        expected_version: int,
        reason: str,
    ) -> Shift:
        shift = await self._reviewable(company_id, supervisor_id, shift_id, expected_version)
        await self._repository.mark_recount(
            company_id=company_id,
            shift_id=shift.id,
            reason=validate_reason(reason, code="pos_recount_reason_required"),
        )
        return await self._shift(company_id, shift_id)

    async def approve(
        self,
        company_id: uuid.UUID,
        supervisor_id: uuid.UUID,
        shift_id: uuid.UUID,
        *,
        expected_version: int,
        retained_float: Decimal,
        notes: str | None,
    ) -> Shift:
        shift = await self._reviewable(company_id, supervisor_id, shift_id, expected_version)
        totals = await self._repository.totals(company_id, shift)
        counted = shift.counted_cash
        if counted is None:  # pragma: no cover - el estado ``counted`` lo garantiza
            raise ConflictError("El turno no tiene conteo.", code="pos_shift_not_counted")
        decision = decide_closing(
            expected_cash=totals.expected_cash,
            counted_cash=counted,
            retained_float=retained_float,
            notes=notes,
        )
        await self._repository.close(
            company_id=company_id,
            shift_id=shift.id,
            approved_by_id=supervisor_id,
            notes=_notes(notes),
            totals=totals,
            cash_difference=decision.cash_difference,
            retained_float=decision.retained_float,
            cash_to_deposit=decision.cash_to_deposit,
        )
        return await self._shift(company_id, shift_id)

    async def _reviewable(
        self,
        company_id: uuid.UUID,
        supervisor_id: uuid.UUID,
        shift_id: uuid.UUID,
        expected_version: int,
    ) -> Shift:
        shift = await self._shift(company_id, shift_id, lock=True)
        if shift.version != expected_version:
            raise ConflictError("El turno cambió; vuelve a abrirlo.", code="pos_shift_version")
        require_reviewable(shift.status)
        require_other_person(shift.cashier_id, supervisor_id)
        return shift

    # --- depósitos -------------------------------------------------------------------------------

    async def deposit_candidates(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[DepositShift]:
        return await self._repository.deposit_candidates(company_id, branch_id)

    async def deposits(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Deposit]:
        return await self._repository.deposits(company_id, branch_ids)

    async def deposit(self, company_id: uuid.UUID, deposit_id: uuid.UUID) -> Deposit:
        found = await self._repository.deposit(company_id, deposit_id)
        if found is None:
            raise NotFoundError("Depósito no encontrado.", code="pos_deposit_not_found")
        return found

    async def create_deposit(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        branch_id: uuid.UUID,
        shift_ids: Sequence[uuid.UUID],
        deposited_on: date,
        bank_name: str,
        account_reference: str,
        slip_number: str,
        deposited_amount: Decimal,
        notes: str | None,
        idempotency_key: str,
    ) -> Deposit:
        key = _key(idempotency_key)
        repeated = await self._repository.deposit_by_key(company_id, key)
        if repeated is not None:
            if {item.shift_id for item in repeated.shifts} != set(shift_ids):
                raise ConflictError(
                    "La clave de idempotencia ya se usó para otro depósito.",
                    code="pos_idempotency_conflict",
                )
            return repeated
        if not shift_ids or len(set(shift_ids)) != len(shift_ids):
            raise BusinessRuleError(
                "Elige los turnos que se depositan, sin repetirlos.", code="pos_deposit_shifts"
            )
        bank = " ".join(bank_name.split())
        account = " ".join(account_reference.split())
        slip = " ".join(slip_number.split())
        if len(bank) < 2 or len(account) < 2 or len(slip) < 2:  # noqa: PLR2004
            raise BusinessRuleError(
                "Escribe el banco, la cuenta y el número de boleta.",
                code="pos_deposit_bank_required",
            )
        if await self._repository.slip_taken(company_id, bank, slip):
            raise ConflictError(
                f"La boleta {slip} de {bank} ya está registrada.", code="pos_deposit_slip_taken"
            )
        candidates = {
            item.shift_id: item
            for item in await self._repository.deposit_candidates(company_id, branch_id, lock=True)
        }
        missing = [shift_id for shift_id in shift_ids if shift_id not in candidates]
        if missing:
            raise ConflictError(
                "Uno de los turnos no está cerrado, es de otra sucursal o ya se depositó.",
                code="pos_deposit_shift_unavailable",
            )
        chosen = [candidates[shift_id] for shift_id in shift_ids]
        expected = money(sum((item.amount for item in chosen), ZERO))
        clean_notes = _notes(notes)
        difference = validate_deposit(
            expected=expected, deposited=deposited_amount, notes=clean_notes
        )
        deposit_id = await self._repository.create_deposit(
            company_id=company_id,
            branch_id=branch_id,
            deposited_on=deposited_on,
            bank_name=bank,
            account_reference=account,
            slip_number=slip,
            expected_amount=expected,
            deposited_amount=deposited_amount,
            difference=difference,
            notes=clean_notes,
            shifts=chosen,
            actor_id=actor_id,
            idempotency_key=key,
        )
        return await self.deposit(company_id, deposit_id)

    # --- supervisor ------------------------------------------------------------------------------

    async def supervisors(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> list[Person]:
        return await self._repository.supervisors(company_id, branch_id)

    async def authorize(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        approval: SupervisorApproval,
    ) -> uuid.UUID:
        """Valida que otra persona con ``pos:supervise`` en la sucursal autoriza con su PIN."""
        require_other_person(actor_id, approval.supervisor_id)
        if not await self._repository.can_supervise(company_id, branch_id, approval.supervisor_id):
            raise AuthorizationError(
                "Esa persona no puede autorizar en esta sucursal.", code="pos_supervisor_invalid"
            )
        check = await self._pins.verify(approval.supervisor_id, approval.pin)
        if not check.configured:
            raise AuthorizationError(
                "El supervisor todavía no tiene PIN de autorización.", code="pos_pin_not_set"
            )
        if check.locked_until is not None and not check.ok:
            raise AuthorizationError(
                "El PIN del supervisor está bloqueado por intentos fallidos; espera 15 minutos.",
                code="pos_pin_locked",
            )
        if not check.ok:
            raise AuthorizationError(
                f"PIN incorrecto. Quedan {check.remaining_attempts} intentos.",
                code="pos_pin_incorrect",
            )
        return approval.supervisor_id

    async def has_pin(self, user_id: uuid.UUID) -> bool:
        return await self._repository.has_pin(user_id)

    async def set_pin(self, user_id: uuid.UUID, password: str, pin: str) -> None:
        stored = await self._repository.password_hash(user_id)
        if stored is None or not self._verify_password(password, stored):
            raise AuthorizationError(
                "La contraseña no es correcta.", code="pos_pin_password_incorrect"
            )
        await self._repository.set_pin(user_id, self._hash_pin(validate_pin(pin)))
