"""Company-wide moving average, independent of physical lot selection.

Original events are immutable. Landed-cost adjustments reference an inbound
event; replay calculates their effect on the remaining inventory and on each
intervening issue/return without overwriting those original events.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.domain.entities.inventory import InventoryOperationError

ZERO = Decimal("0")
QUANTUM = Decimal("0.000001")
INBOUND = frozenset({"opening", "receipt", "adjustment_in"})
OUTBOUND = frozenset({"issue", "supplier_return", "adjustment_out"})


def amount(value: Decimal) -> Decimal:
    if not value.is_finite():
        fail("El valor de inventario debe ser finito.")
    return value.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def fail(message: str) -> None:
    raise InventoryOperationError(message, code="inventory_valuation_invalid", status_code=409)


@dataclass(frozen=True)
class ValuationEvent:
    id: uuid.UUID
    kind: str
    quantity: Decimal = ZERO
    value: Decimal = ZERO
    original_id: uuid.UUID | None = None


@dataclass
class ValuationProjection:
    quantity: Decimal = ZERO
    value: Decimal = ZERO
    costs: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    returned_quantities: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    supplier_credits: dict[uuid.UUID, Decimal] = field(default_factory=dict)

    @property
    def average(self) -> Decimal:
        return amount(self.value / self.quantity) if self.quantity else ZERO


def project(events: list[ValuationEvent]) -> ValuationProjection:
    """Reconcile costs with current knowledge, retaining original event order.

    Six decimal monetary amounts are conserved at every issue. An issue of
    the entire balance consumes exactly its remaining value. Revaluations
    propagate through the *average*, not through physical remaining lot units.
    """
    with localcontext() as context:
        context.prec = 42
        return _project(events)


def _project(events: list[ValuationEvent]) -> ValuationProjection:  # noqa: C901
    known: dict[uuid.UUID, ValuationEvent] = {}
    revised: dict[uuid.UUID, Decimal] = {}
    for event in events:
        if event.id in known:
            fail("El evento de valoración está repetido.")
        if not event.quantity.is_finite() or not event.value.is_finite():
            fail("Las cantidades y costos deben ser finitos.")
        if event.quantity != amount(event.quantity) or event.value != amount(event.value):
            fail("Las cantidades y valores admiten hasta seis decimales.")
        if event.kind == "cost_adjustment":
            source = known.get(event.original_id)
            if source is None or source.kind not in INBOUND or event.quantity != ZERO:
                fail("El ajuste debe referenciar una entrada anterior sin modificar cantidades.")
            revised[source.id] = revised.get(source.id, source.value) + event.value
            if revised[source.id] < ZERO:
                fail("El costo ajustado de la entrada no puede ser negativo.")
        known[event.id] = event

    result = ValuationProjection()
    returned_values: dict[uuid.UUID, Decimal] = {}
    seen: dict[uuid.UUID, ValuationEvent] = {}
    for event in events:
        if event.kind in INBOUND:
            if event.quantity <= ZERO or event.value < ZERO or event.original_id is not None:
                fail("La entrada requiere cantidad positiva y costo no negativo.")
            value = revised.get(event.id, event.value)
            result.quantity += event.quantity
            result.value += value
            result.costs[event.id] = value
        elif event.kind in OUTBOUND:
            if event.quantity <= ZERO or event.quantity > result.quantity:
                fail("La salida excede la existencia valorada.")
            if event.value != ZERO or event.original_id is not None:
                fail("El costo de salida lo determina el promedio vigente.")
            cost = (
                result.value
                if event.quantity == result.quantity
                else amount(result.value * event.quantity / result.quantity)
            )
            result.quantity -= event.quantity
            result.value -= cost
            result.costs[event.id] = cost
        elif event.kind == "customer_return":
            source = seen.get(event.original_id)
            if source is None or source.kind != "issue" or event.value != ZERO:
                fail("La devolución de cliente requiere su salida original.")
            returned = result.returned_quantities.get(source.id, ZERO)
            if event.quantity <= ZERO or returned + event.quantity > source.quantity:
                fail("La devolución excede la cantidad pendiente de la salida original.")
            original_cost = result.costs[source.id]
            # The last return consumes the exact outstanding cost, not a
            # rounded unit cost multiplied again.
            cost = (
                original_cost - returned_values.get(source.id, ZERO)
                if returned + event.quantity == source.quantity
                else amount(
                    (original_cost - returned_values.get(source.id, ZERO))
                    * event.quantity
                    / (source.quantity - returned)
                )
            )
            result.returned_quantities[source.id] = returned + event.quantity
            returned_values[source.id] = returned_values.get(source.id, ZERO) + cost
            result.quantity += event.quantity
            result.value += cost
            result.costs[event.id] = cost
        elif event.kind == "supplier_credit":
            source = seen.get(event.original_id)
            if source is None or source.kind != "supplier_return":
                fail("El crédito requiere su devolución a proveedor.")
            if event.quantity != ZERO or event.value < ZERO or source.id in result.supplier_credits:
                fail("La devolución ya tiene liquidación o el importe no es válido.")
            result.supplier_credits[source.id] = event.value
        elif event.kind != "cost_adjustment":
            fail("Tipo de evento de valoración no admitido.")
        seen[event.id] = event
    if result.quantity < ZERO or result.value < ZERO or (not result.quantity and result.value):
        fail("La cantidad y el valor del inventario no concilian.")
    return result


def adjustment_breakdown(
    events: list[ValuationEvent],
    before: ValuationProjection,
    after: ValuationProjection,
) -> list[dict[str, str]]:
    """Signed expense deltas; customer returns reverse the original expense."""
    rows = []
    for event in events:
        if event.kind not in OUTBOUND | {"customer_return"}:
            continue
        delta = after.costs[event.id] - before.costs[event.id]
        if event.kind == "customer_return":
            delta = -delta
        if delta:
            rows.append({"event_id": str(event.id), "kind": event.kind, "cost_delta": str(delta)})
    return rows
