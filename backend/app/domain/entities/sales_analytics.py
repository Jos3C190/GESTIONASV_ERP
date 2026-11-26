"""Análisis comercial (V9a): metas por sucursal y cifras derivadas.

Las cifras de ingreso son sin IVA. El costo y el margen solo se entregan a quien puede ver costos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError

ZERO = Decimal("0")
CENT = Decimal("0.01")
HUNDRED = Decimal("100")
MAX_GOAL = Decimal("999999999999.99")
MAX_RANGE_DAYS = 366


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def percent(part: Decimal, whole: Decimal) -> Decimal | None:
    """Porcentaje con dos decimales; ``None`` si no hay base."""

    if whole <= ZERO:
        return None
    return (part / whole * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def require_range(start: date, end: date) -> None:
    if end < start:
        raise BusinessRuleError(
            "La fecha final no puede ser anterior a la inicial.",
            code="sales_analytics_range_invalid",
        )
    if (end - start).days >= MAX_RANGE_DAYS:
        raise BusinessRuleError(
            "Consulta como máximo un año a la vez.", code="sales_analytics_range_too_long"
        )


def require_goal(amount: Decimal) -> Decimal:
    if amount <= ZERO or amount > MAX_GOAL:
        raise BusinessRuleError(
            "La meta debe ser un monto mayor que cero.", code="sales_goal_amount_invalid"
        )
    return money(amount)


def month_start(day: date) -> date:
    return day.replace(day=1)


@dataclass(frozen=True, slots=True)
class Goal:
    branch_id: uuid.UUID
    amount: Decimal


@dataclass(slots=True)
class Totals:
    net_sales: Decimal = ZERO
    documents: int = 0
    returns: Decimal = ZERO
    cost: Decimal | None = None

    @property
    def average_ticket(self) -> Decimal | None:
        return money(self.net_sales / self.documents) if self.documents else None

    @property
    def returns_percent(self) -> Decimal | None:
        return percent(self.returns, self.net_sales)

    @property
    def margin(self) -> Decimal | None:
        return None if self.cost is None else money(self.net_sales - self.cost)

    @property
    def margin_percent(self) -> Decimal | None:
        margin = self.margin
        return None if margin is None else percent(margin, self.net_sales)


@dataclass(slots=True)
class Bucket:
    """Una fila de un corte (día, hora, sucursal, categoría, cliente o producto)."""

    key: str
    label: str
    net_sales: Decimal = ZERO
    documents: int = 0
    quantity: Decimal = ZERO
    cost: Decimal | None = None
    goal: Decimal | None = None

    @property
    def margin(self) -> Decimal | None:
        return None if self.cost is None else money(self.net_sales - self.cost)

    @property
    def margin_percent(self) -> Decimal | None:
        margin = self.margin
        return None if margin is None else percent(margin, self.net_sales)

    @property
    def goal_percent(self) -> Decimal | None:
        return None if self.goal is None else percent(self.net_sales, self.goal)


@dataclass(slots=True)
class Analysis:
    start: date
    end: date
    costs_visible: bool
    totals: Totals
    by_day: list[Bucket] = field(default_factory=list)
    by_hour: list[Bucket] = field(default_factory=list)
    by_branch: list[Bucket] = field(default_factory=list)
    by_category: list[Bucket] = field(default_factory=list)
    top_customers: list[Bucket] = field(default_factory=list)
    top_products: list[Bucket] = field(default_factory=list)
    bottom_products: list[Bucket] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LineFact:
    """Una línea vendida en un documento vigente del rango (montos sin IVA)."""

    document_id: uuid.UUID
    day: date
    hour: int
    branch_id: uuid.UUID
    branch_name: str
    customer_id: uuid.UUID
    customer_name: str
    category: str
    product_key: str
    product_name: str
    quantity: Decimal
    unit_name: str
    net: Decimal
    cost: Decimal


@dataclass(frozen=True, slots=True)
class ReturnFact:
    day: date
    branch_id: uuid.UUID
    net: Decimal


TOP = 10
BOTTOM = 5


def _bucket(
    buckets: dict[str, Bucket], key: str, label: str, fact: LineFact, costs: bool
) -> Bucket:
    item = buckets.get(key)
    if item is None:
        item = buckets[key] = Bucket(key=key, label=label, cost=ZERO if costs else None)
    item.net_sales += fact.net
    item.quantity += fact.quantity
    if costs and item.cost is not None:
        item.cost += fact.cost
    return item


def _finish(buckets: dict[str, Bucket], documents: dict[str, set[uuid.UUID]]) -> list[Bucket]:
    for key, item in buckets.items():
        item.net_sales = money(item.net_sales)
        if item.cost is not None:
            item.cost = money(item.cost)
        item.documents = len(documents.get(key, set()))
    return list(buckets.values())


def build_analysis(
    start: date,
    end: date,
    facts: list[LineFact],
    returns: list[ReturnFact],
    goals: dict[uuid.UUID, Decimal],
    *,
    costs_visible: bool,
) -> Analysis:
    """Agrega las líneas en los cortes del análisis; el costo solo si se puede ver."""

    names = ("day", "hour", "branch", "category", "customer", "product")
    buckets: dict[str, dict[str, Bucket]] = {name: {} for name in names}
    documents: dict[str, dict[str, set[uuid.UUID]]] = {name: {} for name in names}
    totals = Totals(cost=ZERO if costs_visible else None)
    seen: set[uuid.UUID] = set()
    for fact in facts:
        seen.add(fact.document_id)
        totals.net_sales += fact.net
        if totals.cost is not None:
            totals.cost += fact.cost
        keys = {
            "day": (fact.day.isoformat(), fact.day.isoformat()),
            "hour": (f"{fact.hour:02d}", f"{fact.hour:02d}:00"),
            "branch": (str(fact.branch_id), fact.branch_name),
            "category": (fact.category, fact.category),
            "customer": (str(fact.customer_id), fact.customer_name),
            "product": (fact.product_key, f"{fact.product_name} ({fact.unit_name})"),
        }
        for name, (key, label) in keys.items():
            _bucket(buckets[name], key, label, fact, costs_visible)
            documents[name].setdefault(key, set()).add(fact.document_id)
    totals.net_sales = money(totals.net_sales)
    totals.documents = len(seen)
    totals.returns = money(sum((item.net for item in returns), ZERO))
    if totals.cost is not None:
        totals.cost = money(totals.cost)

    by_branch = _finish(buckets["branch"], documents["branch"])
    known = {item.key for item in by_branch}
    for branch_id in goals:
        if str(branch_id) not in known:
            by_branch.append(
                Bucket(key=str(branch_id), label="", cost=ZERO if costs_visible else None)
            )
    for item in by_branch:
        item.goal = goals.get(uuid.UUID(item.key))
    products = sorted(
        _finish(buckets["product"], documents["product"]), key=lambda item: item.net_sales
    )
    return Analysis(
        start=start,
        end=end,
        costs_visible=costs_visible,
        totals=totals,
        by_day=sorted(_finish(buckets["day"], documents["day"]), key=lambda item: item.key),
        by_hour=sorted(_finish(buckets["hour"], documents["hour"]), key=lambda item: item.key),
        by_branch=sorted(by_branch, key=lambda item: item.net_sales, reverse=True),
        by_category=sorted(
            _finish(buckets["category"], documents["category"]),
            key=lambda item: item.net_sales,
            reverse=True,
        ),
        top_customers=sorted(
            _finish(buckets["customer"], documents["customer"]),
            key=lambda item: item.net_sales,
            reverse=True,
        )[:TOP],
        top_products=list(reversed(products))[:TOP],
        bottom_products=products[:BOTTOM] if len(products) > TOP else [],
    )
