"""Pure domain model and landed-cost allocation rules for retaceo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum

MONEY_QUANTUM = Decimal("0.000001")
PERCENT_QUANTUM = Decimal("0.000001")
ISO_CURRENCY_CODE_LENGTH = 3
RETACEO_COST_FILE_NAME_MAX_LENGTH = 255
RETACEO_COST_FILE_TYPE_MAX_LENGTH = 160
RETACEO_COST_TITLE_MAX_LENGTH = 160
FOB_CORRECTION_REASON_MIN_LENGTH = 20


class RetaceoStatus(StrEnum):
    """Lifecycle for an import landed-cost allocation."""

    DRAFT = "draft"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class RetaceoCostClass(StrEnum):
    """Accounting treatment selected for an actual landed-cost expense."""

    FREIGHT = "freight"
    EXPENSE = "expense"
    DAI = "dai"
    IMPORT_VAT = "import_vat"


RETACEO_TRANSITIONS: dict[RetaceoStatus, frozenset[RetaceoStatus]] = {
    RetaceoStatus.DRAFT: frozenset({RetaceoStatus.CALCULATED, RetaceoStatus.CANCELLED}),
    RetaceoStatus.CALCULATED: frozenset({RetaceoStatus.VERIFIED, RetaceoStatus.CANCELLED}),
    RetaceoStatus.VERIFIED: frozenset({RetaceoStatus.CLOSED}),
    RetaceoStatus.CANCELLED: frozenset(),
    RetaceoStatus.CLOSED: frozenset(),
}


class RetaceoTransitionError(ValueError):
    """Raised when a retaceo transition is not allowed."""

    def __init__(self, current: RetaceoStatus, target: RetaceoStatus) -> None:
        super().__init__(f"Transición de retaceo no permitida: {current} -> {target}.")
        self.current = current
        self.target = target


def ensure_retaceo_transition(current: RetaceoStatus, target: RetaceoStatus) -> None:
    if target not in RETACEO_TRANSITIONS[current]:
        raise RetaceoTransitionError(current, target)


def _ensure_positive(value: Decimal, label: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{label} debe ser mayor que cero.")


def _ensure_nonnegative(value: Decimal, label: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{label} no puede ser negativo.")


def _money(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("El monto debe ser finito.")
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _percentage(amount: Decimal, base: Decimal) -> Decimal:
    _ensure_positive(base, "El FOB total")
    return (amount * Decimal("100") / base).quantize(
        PERCENT_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


@dataclass(frozen=True, slots=True)
class RetaceoSourceLine:
    """Immutable purchase-detail snapshot used as allocation input."""

    purchase_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    cost_fob: Decimal

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ValueError("El producto del retaceo debe ser válido.")
        if self.unit_id <= 0:
            raise ValueError("La unidad del retaceo debe ser válida.")
        _ensure_positive(self.quantity, "La cantidad del retaceo")
        _ensure_nonnegative(self.cost_fob, "El costo FOB")


@dataclass(frozen=True, slots=True)
class RetaceoAllocationLine:
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


@dataclass(frozen=True, slots=True)
class RetaceoAllocation:
    lines: tuple[RetaceoAllocationLine, ...]
    total_fob: Decimal
    total_freight: Decimal
    total_expenses: Decimal
    total_dai: Decimal
    total_cost: Decimal


@dataclass(frozen=True, slots=True)
class RetaceoCostAllocation:
    purchase_detail_id: uuid.UUID
    amount: Decimal

    def __post_init__(self) -> None:
        _ensure_nonnegative(self.amount, "La distribución del gasto")


@dataclass(frozen=True, slots=True)
class RetaceoCostDocument:
    id: uuid.UUID
    retaceo_cost_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    file_type: str
    uploaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.file_name.strip() or len(self.file_name) > RETACEO_COST_FILE_NAME_MAX_LENGTH:
            raise ValueError("El nombre del comprobante no es válido.")
        if not self.file_type.strip() or len(self.file_type) > RETACEO_COST_FILE_TYPE_MAX_LENGTH:
            raise ValueError("El tipo del comprobante no es válido.")


@dataclass(frozen=True, slots=True)
class RetaceoCost:
    id: uuid.UUID
    retaceo_id: uuid.UUID
    classification: RetaceoCostClass
    title: str
    amount: Decimal
    allocations: tuple[RetaceoCostAllocation, ...] = ()
    documents: tuple[RetaceoCostDocument, ...] = ()
    source_purchase_order_expense_id: uuid.UUID | None = None
    expense_type_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    incurred_on: date | None = None

    def __post_init__(self) -> None:
        if not self.title.strip() or len(self.title) > RETACEO_COST_TITLE_MAX_LENGTH:
            raise ValueError(
                "El nombre del gasto es obligatorio y debe tener 160 caracteres o menos."
            )
        _ensure_positive(self.amount, "El monto del gasto")
        allocation_ids = [allocation.purchase_detail_id for allocation in self.allocations]
        if len(allocation_ids) != len(set(allocation_ids)):
            raise ValueError("Una línea recibida no puede repetirse dentro de un gasto.")
        if any(document.retaceo_cost_id != self.id for document in self.documents):
            raise ValueError("Todos los comprobantes deben pertenecer al gasto.")


@dataclass(frozen=True, slots=True)
class ManualRetaceoAllocation:
    lines: tuple[RetaceoAllocationLine, ...]
    total_fob: Decimal
    total_freight: Decimal
    total_expenses: Decimal
    total_dai: Decimal
    import_vat: Decimal
    total_cost: Decimal


def _apply_manual_retaceo_cost(
    cost: RetaceoCost,
    *,
    source_ids: set[uuid.UUID],
    allocated: dict[uuid.UUID, dict[RetaceoCostClass, Decimal]],
    totals: dict[RetaceoCostClass, Decimal],
    seen_costs: set[uuid.UUID],
) -> None:
    if not cost.is_active:
        return
    if cost.id in seen_costs:
        raise ValueError("Un gasto no puede repetirse en el retaceo.")
    seen_costs.add(cost.id)
    amount = _money(cost.amount)
    _ensure_positive(amount, "El monto del gasto")
    totals[cost.classification] += amount
    if cost.classification is RetaceoCostClass.IMPORT_VAT:
        if cost.allocations:
            raise ValueError(
                "El IVA de importación es informativo y no se distribuye por producto."
            )
        return

    allocated_for_cost = Decimal("0")
    for allocation in cost.allocations:
        if allocation.purchase_detail_id not in source_ids:
            raise ValueError("La distribución referencia una línea que no pertenece al retaceo.")
        amount_for_line = _money(allocation.amount)
        _ensure_nonnegative(amount_for_line, "La distribución del gasto")
        allocated[allocation.purchase_detail_id][cost.classification] += amount_for_line
        allocated_for_cost += amount_for_line
    if _money(allocated_for_cost) > amount:
        raise ValueError("La distribución de un gasto no puede superar su monto.")


def calculate_manual_retaceo_allocation(
    sources: tuple[RetaceoSourceLine, ...],
    costs: tuple[RetaceoCost, ...],
) -> ManualRetaceoAllocation:
    """Build item costs from explicit per-line allocations without auto-splitting."""

    if not sources:
        raise ValueError("El retaceo debe contener al menos un detalle de compra.")
    source_ids = {source.purchase_detail_id for source in sources}
    if len(source_ids) != len(sources):
        raise ValueError("Un detalle de compra no puede repetirse en el retaceo.")

    allocated: dict[uuid.UUID, dict[RetaceoCostClass, Decimal]] = {
        source.purchase_detail_id: {
            RetaceoCostClass.FREIGHT: Decimal("0"),
            RetaceoCostClass.EXPENSE: Decimal("0"),
            RetaceoCostClass.DAI: Decimal("0"),
        }
        for source in sources
    }
    totals = {kind: Decimal("0") for kind in RetaceoCostClass}
    seen_costs: set[uuid.UUID] = set()

    for cost in costs:
        _apply_manual_retaceo_cost(
            cost,
            source_ids=source_ids,
            allocated=allocated,
            totals=totals,
            seen_costs=seen_costs,
        )

    lines: list[RetaceoAllocationLine] = []
    for source in sources:
        buckets = allocated[source.purchase_detail_id]
        freight = _money(buckets[RetaceoCostClass.FREIGHT])
        expenses = _money(buckets[RetaceoCostClass.EXPENSE])
        dai = _money(buckets[RetaceoCostClass.DAI])
        fob = _money(source.cost_fob)
        total = _money(fob + freight + expenses + dai)
        lines.append(
            RetaceoAllocationLine(
                purchase_detail_id=source.purchase_detail_id,
                product_id=source.product_id,
                unit_id=source.unit_id,
                quantity=source.quantity,
                cost_fob=fob,
                freight=freight,
                expenses=expenses,
                dai=dai,
                total_cost=total,
                unit_cost=_money(total / source.quantity),
            )
        )

    total_fob = _money(sum((line.cost_fob for line in lines), Decimal("0")))
    total_freight = _money(sum((line.freight for line in lines), Decimal("0")))
    total_expenses = _money(sum((line.expenses for line in lines), Decimal("0")))
    total_dai = _money(sum((line.dai for line in lines), Decimal("0")))
    total_cost = _money(total_fob + total_freight + total_expenses + total_dai)
    return ManualRetaceoAllocation(
        lines=tuple(lines),
        total_fob=total_fob,
        total_freight=total_freight,
        total_expenses=total_expenses,
        total_dai=total_dai,
        import_vat=_money(totals[RetaceoCostClass.IMPORT_VAT]),
        total_cost=total_cost,
    )


def _allocate_bucket(total: Decimal, weights: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    """Allocate an amount by weight and reconcile to exactly six decimals.

    The allocation uses the largest-remainder method at MONEY_QUANTUM precision,
    so every line is non-negative and the distributed values add back exactly
    to the requested total.
    """

    total = _money(total)
    _ensure_nonnegative(total, "El monto a distribuir")
    total_weight = sum(weights, Decimal("0"))
    _ensure_positive(total_weight, "El FOB total")

    total_units = int(total / MONEY_QUANTUM)
    raw_units = tuple(
        Decimal(total_units) * weight / total_weight if weight > 0 else Decimal("0")
        for weight in weights
    )
    allocated_units = [int(raw.to_integral_value(rounding=ROUND_FLOOR)) for raw in raw_units]
    remainder_units = total_units - sum(allocated_units)

    if remainder_units:
        ranked = sorted(
            (index for index, weight in enumerate(weights) if weight > 0),
            key=lambda index: (
                raw_units[index] - Decimal(allocated_units[index]),
                weights[index],
                -index,
            ),
            reverse=True,
        )
        for index in ranked[:remainder_units]:
            allocated_units[index] += 1

    return tuple(Decimal(units) * MONEY_QUANTUM for units in allocated_units)


def calculate_retaceo_allocation(
    sources: tuple[RetaceoSourceLine, ...],
    *,
    total_freight: Decimal,
    total_expenses: Decimal,
    total_dai: Decimal,
) -> RetaceoAllocation:
    """Distribute freight, other expenses and DAI proportionally by FOB."""

    if not sources:
        raise ValueError("El retaceo debe contener al menos un detalle de compra.")

    detail_ids = [source.purchase_detail_id for source in sources]
    if len(detail_ids) != len(set(detail_ids)):
        raise ValueError("Un detalle de compra no puede repetirse en el retaceo.")

    weights = tuple(_money(source.cost_fob) for source in sources)
    total_fob = _money(sum(weights, Decimal("0")))
    _ensure_positive(total_fob, "El FOB total")

    total_freight = _money(total_freight)
    total_expenses = _money(total_expenses)
    total_dai = _money(total_dai)
    _ensure_nonnegative(total_freight, "El flete total")
    _ensure_nonnegative(total_expenses, "Los gastos totales")
    _ensure_nonnegative(total_dai, "El DAI total")

    freight = _allocate_bucket(total_freight, weights)
    expenses = _allocate_bucket(total_expenses, weights)
    dai = _allocate_bucket(total_dai, weights)

    lines = tuple(
        RetaceoAllocationLine(
            purchase_detail_id=source.purchase_detail_id,
            product_id=source.product_id,
            unit_id=source.unit_id,
            quantity=source.quantity,
            cost_fob=weights[index],
            freight=freight[index],
            expenses=expenses[index],
            dai=dai[index],
            total_cost=_money(weights[index] + freight[index] + expenses[index] + dai[index]),
            unit_cost=_money(
                (weights[index] + freight[index] + expenses[index] + dai[index]) / source.quantity
            ),
        )
        for index, source in enumerate(sources)
    )
    total_cost = _money(total_fob + total_freight + total_expenses + total_dai)
    return RetaceoAllocation(
        lines=lines,
        total_fob=total_fob,
        total_freight=total_freight,
        total_expenses=total_expenses,
        total_dai=total_dai,
        total_cost=total_cost,
    )


@dataclass(frozen=True, slots=True)
class RetaceoDetail:
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

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ValueError("El producto del detalle de retaceo debe ser válido.")
        if self.unit_id <= 0:
            raise ValueError("La unidad del detalle de retaceo debe ser válida.")
        _ensure_positive(self.quantity, "La cantidad del detalle de retaceo")
        for value, label in (
            (self.cost_fob, "El costo FOB"),
            (self.freight, "El flete"),
            (self.expenses, "Los gastos"),
            (self.dai, "El DAI"),
            (self.total_cost, "El costo total"),
            (self.unit_cost, "El costo unitario"),
        ):
            _ensure_nonnegative(value, label)

        expected_total = _money(self.cost_fob + self.freight + self.expenses + self.dai)
        if _money(self.total_cost) != expected_total:
            raise ValueError("El costo total del detalle no coincide con sus componentes.")

        expected_unit = _money(expected_total / self.quantity)
        if _money(self.unit_cost) != expected_unit:
            raise ValueError("El costo unitario del detalle no coincide con su costo total.")


@dataclass(frozen=True, slots=True)
class RetaceoImportData:
    origin_country: str | None = None
    import_invoice_number: str | None = None
    import_invoice_date: date | None = None
    import_policy_number: str | None = None
    import_policy_date: date | None = None


@dataclass(frozen=True, slots=True)
class Retaceo:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    purchase_id: uuid.UUID
    branch_id: uuid.UUID | None
    created_by_id: uuid.UUID
    currency: str
    details: tuple[RetaceoDetail, ...]
    total_fob: Decimal
    total_freight: Decimal
    total_expenses: Decimal
    total_dai: Decimal
    import_vat: Decimal
    total_cost: Decimal
    status: RetaceoStatus = RetaceoStatus.DRAFT
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    costs: tuple[RetaceoCost, ...] = ()
    applied_at: datetime | None = None
    applied_by: uuid.UUID | None = None
    origin_country: str | None = None
    import_invoice_number: str | None = None
    import_invoice_date: date | None = None
    import_policy_number: str | None = None
    import_policy_date: date | None = None
    manual_entry: bool = False

    @property
    def documents_historical_fob_correction(self) -> bool:
        """A manual retaceo can regularize value, never rewrite its source receipt."""
        return (
            self.manual_entry
            and len((self.notes or "").strip()) >= FOB_CORRECTION_REASON_MIN_LENGTH
        )

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("El código del retaceo es obligatorio.")
        if (
            len(self.currency) != ISO_CURRENCY_CODE_LENGTH
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("La moneda debe ser un código ISO de tres letras en mayúsculas.")
        if not self.details:
            raise ValueError("El retaceo debe contener al menos un detalle.")
        self._validate_detail_identity()
        self._validate_totals()

    def _validate_detail_identity(self) -> None:
        if any(detail.retaceo_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer al retaceo.")
        cost_ids = [cost.id for cost in self.costs]
        if len(cost_ids) != len(set(cost_ids)):
            raise ValueError("Un gasto no puede repetirse en el retaceo.")
        if any(cost.retaceo_id != self.id for cost in self.costs):
            raise ValueError("Todos los gastos deben pertenecer al retaceo.")

    def _validate_totals(self) -> None:
        _ensure_positive(self.total_fob, "El FOB total")
        for value, label in (
            (self.total_freight, "El flete total"),
            (self.total_expenses, "Los gastos totales"),
            (self.total_dai, "El DAI total"),
            (self.import_vat, "El IVA de importación"),
            (self.total_cost, "El costo total"),
        ):
            _ensure_nonnegative(value, label)

        checks = (
            ("FOB", self.total_fob, sum((d.cost_fob for d in self.details), Decimal("0"))),
            (
                "flete",
                self.total_freight,
                sum((d.freight for d in self.details), Decimal("0")),
            ),
            (
                "gastos",
                self.total_expenses,
                sum((d.expenses for d in self.details), Decimal("0")),
            ),
            ("DAI", self.total_dai, sum((d.dai for d in self.details), Decimal("0"))),
            (
                "costo total",
                self.total_cost,
                sum((d.total_cost for d in self.details), Decimal("0")),
            ),
        )
        for label, header_value, detail_value in checks:
            if _money(header_value) != _money(detail_value):
                raise ValueError(f"El {label} del retaceo no coincide con la suma de sus detalles.")

        expected_total = _money(
            self.total_fob + self.total_freight + self.total_expenses + self.total_dai
        )
        if _money(self.total_cost) != expected_total:
            raise ValueError(
                "El costo total del retaceo no coincide con FOB + flete + gastos + DAI."
            )

    @property
    def freight_percentage(self) -> Decimal:
        return _percentage(self.total_freight, self.total_fob)

    @property
    def expense_percentage(self) -> Decimal:
        return _percentage(self.total_expenses, self.total_fob)

    @property
    def dai_percentage(self) -> Decimal:
        return _percentage(self.total_dai, self.total_fob)
