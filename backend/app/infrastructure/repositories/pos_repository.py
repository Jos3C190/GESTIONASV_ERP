"""Persistencia del punto de venta (bloque V6a): cajas, turnos, efectivo, conteos y depósitos."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.domain.entities.pos import (
    MAX_PIN_ATTEMPTS,
    PIN_LOCK_MINUTES,
    ZERO,
    CashMovementKind,
    CountKind,
    DenominationCount,
    DenominationForm,
    ShiftStatus,
    ShiftTotals,
)
from app.domain.ports.pos_repository import (
    CashMovement,
    Deposit,
    DepositShift,
    Person,
    PinCheck,
    PointOfSaleOption,
    Register,
    RegisterData,
    Shift,
    ShiftCount,
    ShiftFilter,
)


def _money(value: Any) -> Decimal | None:
    return None if value is None else Decimal(value)


_REGISTERS = """
    SELECT r.id, r.company_id, r.branch_id, b.name AS branch_name, r.establishment_id,
           e.code AS establishment_code, r.point_of_sale_id, p.code AS point_of_sale_code, r.code,
           r.name, r.opening_float, r.cash_out_approval_threshold, r.cash_drawer_limit, r.is_active,
           r.version, r.created_at, r.updated_at, s.id AS unclosed_shift_id,
           CASE WHEN s.id IS NULL THEN NULL ELSE pos_user_name(s.cashier_id) END AS unclosed_shift_cashier,
           EXISTS (SELECT 1 FROM pos_shifts x WHERE x.company_id = r.company_id
                   AND x.register_id = r.id) AS has_shifts
    FROM pos_registers r
    JOIN branches b ON b.id = r.branch_id
    JOIN fiscal_establishments e ON e.id = r.establishment_id
    JOIN fiscal_points_of_sale p ON p.id = r.point_of_sale_id
    LEFT JOIN pos_shifts s ON s.company_id = r.company_id AND s.register_id = r.id
         AND s.status <> 'closed'
    WHERE r.company_id = :company
"""

_SHIFTS = """
    SELECT s.*, b.name AS branch_name, r.code AS register_code, r.name AS register_name,
           pos_user_name(s.cashier_id) AS cashier_name,
           CASE WHEN s.approved_by_id IS NULL THEN NULL ELSE pos_user_name(s.approved_by_id) END
             AS approved_by_name,
           ds.deposit_id, d.number AS deposit_number
    FROM pos_shifts s
    JOIN pos_registers r ON r.company_id = s.company_id AND r.id = s.register_id
    JOIN branches b ON b.id = s.branch_id
    LEFT JOIN pos_deposit_shifts ds ON ds.company_id = s.company_id AND ds.shift_id = s.id
    LEFT JOIN pos_deposits d ON d.company_id = ds.company_id AND d.id = ds.deposit_id
    WHERE s.company_id = :company
"""

_SHIFT_COUNT = "SELECT count(*) FROM pos_shifts s WHERE s.company_id = :company"

_MOVEMENTS = """
    SELECT m.*, pos_user_name(m.created_by_id) AS created_by_name,
           CASE WHEN m.authorized_by_id IS NULL THEN NULL ELSE pos_user_name(m.authorized_by_id) END
             AS authorized_by_name
    FROM pos_cash_movements m
    WHERE m.company_id = :company
"""

_DEPOSITS = """
    SELECT d.*, b.name AS branch_name, pos_user_name(d.created_by_id) AS created_by_name
    FROM pos_deposits d JOIN branches b ON b.id = d.branch_id
    WHERE d.company_id = :company
"""

_SUPERVISORS = """
    SELECT u.id, {name} AS name
    FROM users u
    WHERE u.is_active AND u.deleted_at IS NULL
      AND (u.is_superuser OR EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN role_permissions rp ON rp.role_id = ur.role_id
            JOIN permissions p ON p.id = rp.permission_id AND p.deleted_at IS NULL
            JOIN roles ro ON ro.id = ur.role_id AND ro.deleted_at IS NULL
            WHERE ur.user_id = u.id AND ur.company_id = :company AND p.code = 'pos:supervise'))
      AND (u.is_superuser OR EXISTS (
            SELECT 1 FROM user_companies uc
            WHERE uc.user_id = u.id AND uc.company_id = :company
              AND (uc.access_all_branches OR EXISTS (
                    SELECT 1 FROM user_branches ub
                    WHERE ub.user_id = u.id AND ub.company_id = :company
                      AND ub.branch_id = :branch AND ub.is_active))))
"""


def _register(row: Any) -> Register:
    return Register(
        id=row.id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        branch_name=row.branch_name,
        establishment_id=row.establishment_id,
        establishment_code=row.establishment_code,
        point_of_sale_id=row.point_of_sale_id,
        point_of_sale_code=row.point_of_sale_code,
        code=row.code,
        name=row.name,
        opening_float=Decimal(row.opening_float),
        cash_out_approval_threshold=Decimal(row.cash_out_approval_threshold),
        cash_drawer_limit=_money(row.cash_drawer_limit),
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        unclosed_shift_id=row.unclosed_shift_id,
        unclosed_shift_cashier=row.unclosed_shift_cashier,
        has_shifts=row.has_shifts,
    )


def _shift(row: Any) -> Shift:
    return Shift(
        id=row.id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        branch_name=row.branch_name,
        register_id=row.register_id,
        register_code=row.register_code,
        register_name=row.register_name,
        cashier_id=row.cashier_id,
        cashier_name=row.cashier_name,
        number=row.number,
        status=ShiftStatus(row.status),
        opening_float=Decimal(row.opening_float),
        opened_at=row.opened_at,
        counted_at=row.counted_at,
        recount_reason=row.recount_reason,
        closed_at=row.closed_at,
        approved_by_id=row.approved_by_id,
        approved_by_name=row.approved_by_name,
        approval_notes=row.approval_notes,
        expected_cash=_money(row.expected_cash),
        counted_cash=_money(row.counted_cash),
        cash_difference=_money(row.cash_difference),
        expected_card=_money(row.expected_card),
        declared_card=_money(row.declared_card),
        expected_transfer=_money(row.expected_transfer),
        declared_transfer=_money(row.declared_transfer),
        retained_float=_money(row.retained_float),
        cash_to_deposit=_money(row.cash_to_deposit),
        version=row.version,
        idempotency_key=row.idempotency_key,
        deposit_id=row.deposit_id,
        deposit_number=row.deposit_number,
    )


def _movement(row: Any) -> CashMovement:
    return CashMovement(
        id=row.id,
        shift_id=row.shift_id,
        kind=CashMovementKind(row.kind),
        amount=Decimal(row.amount),
        reason=row.reason,
        reference=row.reference,
        authorized_by_id=row.authorized_by_id,
        authorized_by_name=row.authorized_by_name,
        created_by_id=row.created_by_id,
        created_by_name=row.created_by_name,
        created_at=row.created_at,
        idempotency_key=row.idempotency_key,
    )


class SqlAlchemyPosRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _lock(self, key: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key}
        )

    # --- cajas -----------------------------------------------------------------------------------

    async def registers(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Register]:
        rows = await self._session.execute(
            text(
                _REGISTERS
                + " AND (CAST(:branches AS uuid[]) IS NULL OR r.branch_id = ANY(CAST(:branches AS uuid[])))"
                " ORDER BY b.name, r.code"
            ),
            {"company": company_id, "branches": None if branch_ids is None else list(branch_ids)},
        )
        return [_register(row) for row in rows]

    async def register(
        self, company_id: uuid.UUID, register_id: uuid.UUID, *, lock: bool = False
    ) -> Register | None:
        if lock:
            await self._session.execute(
                text(
                    "SELECT id FROM pos_registers WHERE company_id = :company AND id = :id "
                    "FOR UPDATE"
                ),
                {"company": company_id, "id": register_id},
            )
        row = (
            await self._session.execute(
                text(_REGISTERS + " AND r.id = :id"), {"company": company_id, "id": register_id}
            )
        ).first()
        return None if row is None else _register(row)

    _POINTS = """
        SELECT p.id, p.code, p.name, p.is_active, e.id AS establishment_id,
               e.code AS establishment_code, e.is_active AS establishment_active, e.branch_id,
               b.name AS branch_name, r.id AS register_id
        FROM fiscal_points_of_sale p
        JOIN fiscal_establishments e ON e.company_id = p.company_id AND e.id = p.establishment_id
        JOIN branches b ON b.id = e.branch_id
        LEFT JOIN pos_registers r ON r.company_id = p.company_id AND r.point_of_sale_id = p.id
        WHERE p.company_id = :company
    """

    @staticmethod
    def _point(row: Any) -> PointOfSaleOption:
        return PointOfSaleOption(
            id=row.id,
            code=row.code,
            name=row.name,
            establishment_id=row.establishment_id,
            establishment_code=row.establishment_code,
            branch_id=row.branch_id,
            branch_name=row.branch_name,
            is_active=row.is_active,
            establishment_active=row.establishment_active,
            register_id=row.register_id,
        )

    async def point_of_sale_options(self, company_id: uuid.UUID) -> list[PointOfSaleOption]:
        rows = await self._session.execute(
            text(self._POINTS + " ORDER BY b.name, p.code"), {"company": company_id}
        )
        return [self._point(row) for row in rows]

    async def point_of_sale(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSaleOption | None:
        row = (
            await self._session.execute(
                text(self._POINTS + " AND p.id = :id"),
                {"company": company_id, "id": point_of_sale_id},
            )
        ).first()
        return None if row is None else self._point(row)

    async def register_code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude: uuid.UUID | None = None
    ) -> bool:
        found = await self._session.scalar(
            text(
                "SELECT 1 FROM pos_registers WHERE company_id = :company AND code = :code "
                "AND (CAST(:exclude AS uuid) IS NULL OR id <> CAST(:exclude AS uuid))"
            ),
            {"company": company_id, "code": code, "exclude": exclude},
        )
        return found is not None

    async def create_register(
        self,
        *,
        company_id: uuid.UUID,
        point_of_sale: PointOfSaleOption,
        data: RegisterData,
        actor_id: uuid.UUID,
    ) -> uuid.UUID:
        register_id = uuid.uuid4()
        try:
            await self._session.execute(
                text(
                    "INSERT INTO pos_registers (id, company_id, branch_id, establishment_id, "
                    "point_of_sale_id, code, name, opening_float, cash_out_approval_threshold, "
                    "cash_drawer_limit, is_active, created_by_id, updated_by_id) VALUES (:id, "
                    ":company, :branch, :establishment, :point, :code, :name, :float, :threshold, "
                    ":limit, :active, :actor, :actor)"
                ),
                {
                    "id": register_id,
                    "company": company_id,
                    "branch": point_of_sale.branch_id,
                    "establishment": point_of_sale.establishment_id,
                    "point": point_of_sale.id,
                    "code": data.code,
                    "name": data.name,
                    "float": data.opening_float,
                    "threshold": data.cash_out_approval_threshold,
                    "limit": data.cash_drawer_limit,
                    "active": data.is_active,
                    "actor": actor_id,
                },
            )
        except IntegrityError as error:
            raise ConflictError(
                "Otra persona registró esa caja o ese punto de venta al mismo tiempo.",
                code="pos_register_conflict",
            ) from error
        return register_id

    async def update_register(
        self,
        *,
        company_id: uuid.UUID,
        register_id: uuid.UUID,
        data: RegisterData,
        actor_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE pos_registers SET code = :code, name = :name, opening_float = :float, "
                "cash_out_approval_threshold = :threshold, cash_drawer_limit = :limit, "
                "is_active = :active, updated_by_id = :actor, updated_at = now(), "
                "version = version + 1 WHERE company_id = :company AND id = :id"
            ),
            {
                "company": company_id,
                "id": register_id,
                "code": data.code,
                "name": data.name,
                "float": data.opening_float,
                "threshold": data.cash_out_approval_threshold,
                "limit": data.cash_drawer_limit,
                "active": data.is_active,
                "actor": actor_id,
            },
        )

    # --- turnos ----------------------------------------------------------------------------------

    async def shift(
        self, company_id: uuid.UUID, shift_id: uuid.UUID, *, lock: bool = False
    ) -> Shift | None:
        if lock:
            await self._session.execute(
                text(
                    "SELECT id FROM pos_shifts WHERE company_id = :company AND id = :id FOR UPDATE"
                ),
                {"company": company_id, "id": shift_id},
            )
        row = (
            await self._session.execute(
                text(_SHIFTS + " AND s.id = :id"), {"company": company_id, "id": shift_id}
            )
        ).first()
        return None if row is None else _shift(row)

    async def shift_by_key(self, company_id: uuid.UUID, key: str) -> Shift | None:
        row = (
            await self._session.execute(
                text(_SHIFTS + " AND s.idempotency_key = :key"), {"company": company_id, "key": key}
            )
        ).first()
        return None if row is None else _shift(row)

    async def unclosed_shift_for_cashier(
        self, company_id: uuid.UUID, cashier_id: uuid.UUID
    ) -> Shift | None:
        row = (
            await self._session.execute(
                text(_SHIFTS + " AND s.cashier_id = :cashier AND s.status <> 'closed'"),
                {"company": company_id, "cashier": cashier_id},
            )
        ).first()
        return None if row is None else _shift(row)

    async def unclosed_shift_for_register(
        self, company_id: uuid.UUID, register_id: uuid.UUID
    ) -> Shift | None:
        row = (
            await self._session.execute(
                text(_SHIFTS + " AND s.register_id = :register AND s.status <> 'closed'"),
                {"company": company_id, "register": register_id},
            )
        ).first()
        return None if row is None else _shift(row)

    async def shifts(self, company_id: uuid.UUID, filters: ShiftFilter) -> tuple[list[Shift], int]:
        where = """
          AND (CAST(:branches AS uuid[]) IS NULL OR s.branch_id = ANY(CAST(:branches AS uuid[])))
          AND (CAST(:statuses AS text[]) IS NULL OR s.status = ANY(CAST(:statuses AS text[])))
          AND (CAST(:register AS uuid) IS NULL OR s.register_id = CAST(:register AS uuid))
          AND (CAST(:cashier AS uuid) IS NULL OR s.cashier_id = CAST(:cashier AS uuid))
          AND (CAST(:from AS date) IS NULL
               OR (s.opened_at AT TIME ZONE 'America/El_Salvador')::date >= CAST(:from AS date))
          AND (CAST(:to AS date) IS NULL
               OR (s.opened_at AT TIME ZONE 'America/El_Salvador')::date <= CAST(:to AS date))
        """
        params = {
            "company": company_id,
            "branches": None if filters.branch_ids is None else list(filters.branch_ids),
            "statuses": None
            if filters.statuses is None
            else [item.value for item in filters.statuses],
            "register": filters.register_id,
            "cashier": filters.cashier_id,
            "from": filters.opened_from,
            "to": filters.opened_to,
        }
        total = await self._session.scalar(text(_SHIFT_COUNT + where), params)
        rows = await self._session.execute(
            text(
                _SHIFTS
                + where
                + " ORDER BY s.opened_at DESC, s.number DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": filters.limit, "offset": filters.offset},
        )
        return [_shift(row) for row in rows], int(total or 0)

    async def create_shift(
        self,
        *,
        company_id: uuid.UUID,
        register: Register,
        cashier_id: uuid.UUID,
        opening_float: Decimal,
        idempotency_key: str,
    ) -> uuid.UUID:
        await self._lock(f"pos_shifts:{company_id}")
        number = await self._session.scalar(
            text("SELECT COALESCE(max(number), 0) + 1 FROM pos_shifts WHERE company_id = :c"),
            {"c": company_id},
        )
        shift_id = uuid.uuid4()
        try:
            await self._session.execute(
                text(
                    "INSERT INTO pos_shifts (id, company_id, branch_id, register_id, cashier_id, "
                    "number, opening_float, idempotency_key) VALUES (:id, :company, :branch, "
                    ":register, :cashier, :number, :float, :key)"
                ),
                {
                    "id": shift_id,
                    "company": company_id,
                    "branch": register.branch_id,
                    "register": register.id,
                    "cashier": cashier_id,
                    "number": number,
                    "float": opening_float,
                    "key": idempotency_key,
                },
            )
        except IntegrityError as error:
            raise ConflictError(
                "La caja o el cajero ya tienen un turno sin cerrar.", code="pos_shift_conflict"
            ) from error
        return shift_id

    async def totals(self, company_id: uuid.UUID, shift: Shift) -> ShiftTotals:
        rows = await self._session.execute(
            text(
                "SELECT kind, sum(amount) AS amount FROM pos_cash_movements "
                "WHERE company_id = :company AND shift_id = :shift GROUP BY kind"
            ),
            {"company": company_id, "shift": shift.id},
        )
        sums: dict[str, Decimal] = {row.kind: Decimal(row.amount) for row in rows}
        return ShiftTotals(
            opening_float=shift.opening_float,
            cash_in=sums.get(CashMovementKind.CASH_IN.value, ZERO),
            cash_out=sums.get(CashMovementKind.CASH_OUT.value, ZERO),
            safe_drops=sums.get(CashMovementKind.SAFE_DROP.value, ZERO),
        )

    async def mark_counted(
        self,
        *,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        counted_cash: Decimal,
        declared_card: Decimal,
        declared_transfer: Decimal,
        totals: ShiftTotals,
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE pos_shifts SET status = 'counted', counted_at = now(), recount_reason = NULL, "
                "counted_cash = :cash, declared_card = :card, declared_transfer = :transfer, "
                "expected_cash = :e_cash, expected_card = :e_card, expected_transfer = :e_transfer, "
                "version = version + 1 WHERE company_id = :company AND id = :id"
            ),
            {
                "company": company_id,
                "id": shift_id,
                "cash": counted_cash,
                "card": declared_card,
                "transfer": declared_transfer,
                "e_cash": totals.expected_cash,
                "e_card": totals.expected_card,
                "e_transfer": totals.expected_transfer,
            },
        )

    async def mark_recount(
        self, *, company_id: uuid.UUID, shift_id: uuid.UUID, reason: str
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE pos_shifts SET status = 'recount', recount_reason = :reason, "
                "version = version + 1 WHERE company_id = :company AND id = :id"
            ),
            {"company": company_id, "id": shift_id, "reason": reason},
        )

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
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE pos_shifts SET status = 'closed', closed_at = now(), "
                "approved_by_id = :approver, approval_notes = :notes, expected_cash = :e_cash, "
                "expected_card = :e_card, expected_transfer = :e_transfer, "
                "cash_difference = :difference, retained_float = :retained, "
                "cash_to_deposit = :deposit, version = version + 1 "
                "WHERE company_id = :company AND id = :id"
            ),
            {
                "company": company_id,
                "id": shift_id,
                "approver": approved_by_id,
                "notes": notes,
                "e_cash": totals.expected_cash,
                "e_card": totals.expected_card,
                "e_transfer": totals.expected_transfer,
                "difference": cash_difference,
                "retained": retained_float,
                "deposit": cash_to_deposit,
            },
        )

    # --- efectivo y conteos ----------------------------------------------------------------------

    async def movements(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> list[CashMovement]:
        rows = await self._session.execute(
            text(_MOVEMENTS + " AND m.shift_id = :shift ORDER BY m.created_at, m.id"),
            {"company": company_id, "shift": shift_id},
        )
        return [_movement(row) for row in rows]

    async def movement_by_key(self, company_id: uuid.UUID, key: str) -> CashMovement | None:
        row = (
            await self._session.execute(
                text(_MOVEMENTS + " AND m.idempotency_key = :key"),
                {"company": company_id, "key": key},
            )
        ).first()
        return None if row is None else _movement(row)

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
    ) -> uuid.UUID:
        movement_id = uuid.uuid4()
        await self._session.execute(
            text(
                "INSERT INTO pos_cash_movements (id, company_id, shift_id, kind, amount, reason, "
                "reference, authorized_by_id, created_by_id, idempotency_key) VALUES (:id, "
                ":company, :shift, :kind, :amount, :reason, :reference, :authorizer, :actor, :key)"
            ),
            {
                "id": movement_id,
                "company": company_id,
                "shift": shift_id,
                "kind": kind.value,
                "amount": amount,
                "reason": reason,
                "reference": reference,
                "authorizer": authorized_by_id,
                "actor": actor_id,
                "key": idempotency_key,
            },
        )
        return movement_id

    async def counts(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> list[ShiftCount]:
        rows = (
            await self._session.execute(
                text(
                    "SELECT c.*, pos_user_name(c.counted_by_id) AS counted_by_name "
                    "FROM pos_shift_counts c WHERE c.company_id = :company AND c.shift_id = :shift "
                    "ORDER BY c.counted_at, c.sequence"
                ),
                {"company": company_id, "shift": shift_id},
            )
        ).all()
        lines: dict[uuid.UUID, list[DenominationCount]] = defaultdict(list)
        if rows:
            for line in await self._session.execute(
                text(
                    "SELECT count_id, form, denomination, quantity FROM pos_shift_count_lines "
                    "WHERE company_id = :company AND count_id = ANY(:counts) "
                    "ORDER BY form DESC, denomination DESC"
                ),
                {"company": company_id, "counts": [row.id for row in rows]},
            ):
                lines[line.count_id].append(
                    DenominationCount(
                        DenominationForm(line.form), Decimal(line.denomination), line.quantity
                    )
                )
        return [
            ShiftCount(
                id=row.id,
                kind=CountKind(row.kind),
                sequence=row.sequence,
                cash_total=Decimal(row.cash_total),
                card_total=_money(row.card_total),
                transfer_total=_money(row.transfer_total),
                notes=row.notes,
                counted_by_id=row.counted_by_id,
                counted_by_name=row.counted_by_name,
                counted_at=row.counted_at,
                lines=tuple(lines[row.id]),
            )
            for row in rows
        ]

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
    ) -> uuid.UUID:
        sequence = await self._session.scalar(
            text(
                "SELECT COALESCE(max(sequence), 0) + 1 FROM pos_shift_counts "
                "WHERE company_id = :company AND shift_id = :shift AND kind = :kind"
            ),
            {"company": company_id, "shift": shift_id, "kind": kind.value},
        )
        count_id = uuid.uuid4()
        await self._session.execute(
            text(
                "INSERT INTO pos_shift_counts (id, company_id, shift_id, kind, sequence, cash_total, "
                "card_total, transfer_total, notes, counted_by_id) VALUES (:id, :company, :shift, "
                ":kind, :sequence, :cash, :card, :transfer, :notes, :actor)"
            ),
            {
                "id": count_id,
                "company": company_id,
                "shift": shift_id,
                "kind": kind.value,
                "sequence": sequence,
                "cash": cash_total,
                "card": card_total,
                "transfer": transfer_total,
                "notes": notes,
                "actor": actor_id,
            },
        )
        if lines:
            await self._session.execute(
                text(
                    "INSERT INTO pos_shift_count_lines (company_id, count_id, form, denomination, "
                    "quantity) VALUES (:company, :count, :form, :denomination, :quantity)"
                ),
                [
                    {
                        "company": company_id,
                        "count": count_id,
                        "form": line.form.value,
                        "denomination": line.denomination,
                        "quantity": line.quantity,
                    }
                    for line in lines
                ],
            )
        return count_id

    # --- depósitos -------------------------------------------------------------------------------

    async def deposit_candidates(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, lock: bool = False
    ) -> list[DepositShift]:
        if lock:
            await self._lock(f"pos_deposits:{company_id}:{branch_id}")
        rows = await self._session.execute(
            text(
                """
                SELECT s.id, s.number, r.code AS register_code, pos_user_name(s.cashier_id) AS cashier_name,
                       s.closed_at,
                       s.cash_to_deposit + COALESCE((SELECT sum(m.amount) FROM pos_cash_movements m
                           WHERE m.company_id = s.company_id AND m.shift_id = s.id
                             AND m.kind = 'safe_drop'), 0) AS amount
                FROM pos_shifts s
                JOIN pos_registers r ON r.company_id = s.company_id AND r.id = s.register_id
                WHERE s.company_id = :company AND s.branch_id = :branch AND s.status = 'closed'
                  AND NOT EXISTS (SELECT 1 FROM pos_deposit_shifts ds
                                  WHERE ds.company_id = s.company_id AND ds.shift_id = s.id)
                ORDER BY s.closed_at, s.number
                """
            ),
            {"company": company_id, "branch": branch_id},
        )
        return [
            DepositShift(
                shift_id=row.id,
                shift_number=row.number,
                register_code=row.register_code,
                cashier_name=row.cashier_name,
                closed_at=row.closed_at,
                amount=Decimal(row.amount),
            )
            for row in rows
            if Decimal(row.amount) > ZERO
        ]

    async def _deposit_rows(
        self, company_id: uuid.UUID, where: str, params: dict[str, Any]
    ) -> list[Deposit]:
        rows = (
            await self._session.execute(
                text(_DEPOSITS + where + " ORDER BY d.deposited_on DESC, d.number DESC"),
                {"company": company_id, **params},
            )
        ).all()
        if not rows:
            return []
        shifts: dict[uuid.UUID, list[DepositShift]] = defaultdict(list)
        for row in await self._session.execute(
            text(
                """
                SELECT ds.deposit_id, s.id, s.number, r.code AS register_code,
                       pos_user_name(s.cashier_id) AS cashier_name, s.closed_at, ds.amount
                FROM pos_deposit_shifts ds
                JOIN pos_shifts s ON s.company_id = ds.company_id AND s.id = ds.shift_id
                JOIN pos_registers r ON r.company_id = s.company_id AND r.id = s.register_id
                WHERE ds.company_id = :company AND ds.deposit_id = ANY(:deposits)
                ORDER BY s.number
                """
            ),
            {"company": company_id, "deposits": [row.id for row in rows]},
        ):
            shifts[row.deposit_id].append(
                DepositShift(
                    shift_id=row.id,
                    shift_number=row.number,
                    register_code=row.register_code,
                    cashier_name=row.cashier_name,
                    closed_at=row.closed_at,
                    amount=Decimal(row.amount),
                )
            )
        return [
            Deposit(
                id=row.id,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                number=row.number,
                deposited_on=row.deposited_on,
                bank_name=row.bank_name,
                account_reference=row.account_reference,
                slip_number=row.slip_number,
                expected_amount=Decimal(row.expected_amount),
                deposited_amount=Decimal(row.deposited_amount),
                difference=Decimal(row.difference),
                notes=row.notes,
                created_by_name=row.created_by_name,
                created_at=row.created_at,
                idempotency_key=row.idempotency_key,
                shifts=tuple(shifts[row.id]),
            )
            for row in rows
        ]

    async def deposits(
        self, company_id: uuid.UUID, branch_ids: Sequence[uuid.UUID] | None
    ) -> list[Deposit]:
        return await self._deposit_rows(
            company_id,
            " AND (CAST(:branches AS uuid[]) IS NULL OR d.branch_id = ANY(CAST(:branches AS uuid[])))",
            {"branches": None if branch_ids is None else list(branch_ids)},
        )

    async def deposit(self, company_id: uuid.UUID, deposit_id: uuid.UUID) -> Deposit | None:
        found = await self._deposit_rows(company_id, " AND d.id = :id", {"id": deposit_id})
        return found[0] if found else None

    async def deposit_by_key(self, company_id: uuid.UUID, key: str) -> Deposit | None:
        found = await self._deposit_rows(company_id, " AND d.idempotency_key = :key", {"key": key})
        return found[0] if found else None

    async def slip_taken(self, company_id: uuid.UUID, bank_name: str, slip_number: str) -> bool:
        found = await self._session.scalar(
            text(
                "SELECT 1 FROM pos_deposits WHERE company_id = :company AND bank_name = :bank "
                "AND slip_number = :slip"
            ),
            {"company": company_id, "bank": bank_name, "slip": slip_number},
        )
        return found is not None

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
    ) -> uuid.UUID:
        await self._lock(f"pos_deposit_numbers:{company_id}")
        number = await self._session.scalar(
            text("SELECT COALESCE(max(number), 0) + 1 FROM pos_deposits WHERE company_id = :c"),
            {"c": company_id},
        )
        deposit_id = uuid.uuid4()
        try:
            await self._session.execute(
                text(
                    "INSERT INTO pos_deposits (id, company_id, branch_id, number, deposited_on, "
                    "bank_name, account_reference, slip_number, expected_amount, deposited_amount, "
                    "difference, notes, created_by_id, idempotency_key) VALUES (:id, :company, "
                    ":branch, :number, :on, :bank, :account, :slip, :expected, :deposited, "
                    ":difference, :notes, :actor, :key)"
                ),
                {
                    "id": deposit_id,
                    "company": company_id,
                    "branch": branch_id,
                    "number": number,
                    "on": deposited_on,
                    "bank": bank_name,
                    "account": account_reference,
                    "slip": slip_number,
                    "expected": expected_amount,
                    "deposited": deposited_amount,
                    "difference": difference,
                    "notes": notes,
                    "actor": actor_id,
                    "key": idempotency_key,
                },
            )
            await self._session.execute(
                text(
                    "INSERT INTO pos_deposit_shifts (company_id, deposit_id, shift_id, branch_id, "
                    "amount) VALUES (:company, :deposit, :shift, :branch, :amount)"
                ),
                [
                    {
                        "company": company_id,
                        "deposit": deposit_id,
                        "shift": item.shift_id,
                        "branch": branch_id,
                        "amount": item.amount,
                    }
                    for item in shifts
                ],
            )
        except IntegrityError as error:
            raise ConflictError(
                "Uno de los turnos o la boleta ya se registraron en otro depósito.",
                code="pos_deposit_conflict",
            ) from error
        return deposit_id

    # --- personas y PIN --------------------------------------------------------------------------

    async def person(self, user_id: uuid.UUID) -> Person | None:
        name = await self._session.scalar(text("SELECT pos_user_name(:user)"), {"user": user_id})
        return None if name is None else Person(user_id, name)

    async def supervisors(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> list[Person]:
        rows = await self._session.execute(
            text(_SUPERVISORS.format(name="pos_user_name(u.id)") + " ORDER BY 2"),
            {"company": company_id, "branch": branch_id},
        )
        return [Person(row.id, row.name) for row in rows]

    async def can_supervise(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        found = await self._session.scalar(
            text(_SUPERVISORS.format(name="u.username") + " AND u.id = :user"),
            {"company": company_id, "branch": branch_id, "user": user_id},
        )
        return found is not None

    async def has_pin(self, user_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            text("SELECT 1 FROM pos_supervisor_pins WHERE user_id = :user"), {"user": user_id}
        )
        return found is not None

    async def password_hash(self, user_id: uuid.UUID) -> str | None:
        found = await self._session.scalar(
            text(
                "SELECT password_hash FROM users WHERE id = :user AND is_active "
                "AND deleted_at IS NULL"
            ),
            {"user": user_id},
        )
        return None if found is None else str(found)

    async def set_pin(self, user_id: uuid.UUID, pin_hash: str) -> None:
        await self._session.execute(
            text(
                "INSERT INTO pos_supervisor_pins (user_id, pin_hash) VALUES (:user, :hash) "
                "ON CONFLICT (user_id) DO UPDATE SET pin_hash = EXCLUDED.pin_hash, "
                "failed_attempts = 0, locked_until = NULL, updated_at = now()"
            ),
            {"user": user_id, "hash": pin_hash},
        )


class SqlAlchemyPinAttempts:
    """Verifica el PIN en una transacción propia: el intento fallido queda aunque la petición falle."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        verify: Callable[[str, str], bool],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._factory = session_factory
        self._verify = verify
        self._clock = clock

    async def verify(self, user_id: uuid.UUID, pin: str) -> PinCheck:
        async with self._factory() as session, session.begin():
            row = (
                await session.execute(
                    text(
                        "SELECT pin_hash, failed_attempts, locked_until FROM pos_supervisor_pins "
                        "WHERE user_id = :user FOR UPDATE"
                    ),
                    {"user": user_id},
                )
            ).first()
            if row is None:
                return PinCheck(ok=False, configured=False, locked_until=None, remaining_attempts=0)
            now = self._clock()
            if row.locked_until is not None and row.locked_until > now:
                return PinCheck(
                    ok=False, configured=True, locked_until=row.locked_until, remaining_attempts=0
                )
            if self._verify(pin, row.pin_hash):
                await session.execute(
                    text(
                        "UPDATE pos_supervisor_pins SET failed_attempts = 0, locked_until = NULL "
                        "WHERE user_id = :user"
                    ),
                    {"user": user_id},
                )
                return PinCheck(
                    ok=True, configured=True, locked_until=None, remaining_attempts=MAX_PIN_ATTEMPTS
                )
            attempts = (0 if row.locked_until is not None else row.failed_attempts) + 1
            locked_until = (
                now + timedelta(minutes=PIN_LOCK_MINUTES) if attempts >= MAX_PIN_ATTEMPTS else None
            )
            await session.execute(
                text(
                    "UPDATE pos_supervisor_pins SET failed_attempts = :attempts, "
                    "locked_until = :locked WHERE user_id = :user"
                ),
                {
                    "user": user_id,
                    "attempts": 0 if locked_until is not None else attempts,
                    "locked": locked_until,
                },
            )
            return PinCheck(
                ok=False,
                configured=True,
                locked_until=locked_until,
                remaining_attempts=max(MAX_PIN_ATTEMPTS - attempts, 0),
            )
