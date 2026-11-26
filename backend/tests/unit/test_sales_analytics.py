"""Análisis comercial (V9a): cortes, costo solo con permiso, metas y permisos del catálogo."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.api.v1.routers.sales_analytics import analysis_out
from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_analytics import (
    LineFact,
    ReturnFact,
    build_analysis,
    require_goal,
    require_range,
)

BRANCH_A, BRANCH_B = uuid.uuid4(), uuid.uuid4()
DOC_1, DOC_2 = uuid.uuid4(), uuid.uuid4()
CUSTOMER = uuid.uuid4()


def _fact(
    document: uuid.UUID, product: str, net: str, cost: str, *, branch: uuid.UUID = BRANCH_A
) -> LineFact:
    return LineFact(
        document_id=document,
        day=date(2026, 11, 3),
        hour=9,
        branch_id=branch,
        branch_name="Centro" if branch == BRANCH_A else "Norte",
        customer_id=CUSTOMER,
        customer_name="Cafetería",
        category="Harinas",
        product_key=product,
        product_name=f"Producto {product}",
        quantity=Decimal("2"),
        unit_name="u",
        net=Decimal(net),
        cost=Decimal(cost),
    )


def _analysis(costs: bool = True):
    facts = [
        _fact(DOC_1, "1", "60.00", "40.00"),
        _fact(DOC_1, "2", "40.00", "30.00"),
        _fact(DOC_2, "1", "100.00", "70.00", branch=BRANCH_B),
    ]
    returns = [ReturnFact(date(2026, 11, 4), BRANCH_A, Decimal("20.00"))]
    goals = {BRANCH_A: Decimal("400.00"), uuid.uuid4(): Decimal("50.00")}
    return build_analysis(
        date(2026, 11, 1), date(2026, 11, 30), facts, returns, goals, costs_visible=costs
    )


def test_totals_and_cuts() -> None:
    result = _analysis()
    totals = result.totals
    assert totals.net_sales == Decimal("200.00")
    assert totals.documents == 2
    assert totals.average_ticket == Decimal("100.00")
    assert totals.returns_percent == Decimal("10.00")
    assert totals.margin == Decimal("60.00")
    assert totals.margin_percent == Decimal("30.00")
    assert [item.net_sales for item in result.top_products] == [Decimal("160.00"), Decimal("40.00")]
    assert result.top_products[0].documents == 2
    assert result.bottom_products == []  # con pocos productos no hay «menos vendidos»
    assert result.by_hour[0].label == "09:00"
    centro = next(item for item in result.by_branch if item.key == str(BRANCH_A))
    assert centro.goal_percent == Decimal("25.00")
    # La sucursal con meta y sin ventas también aparece.
    assert any(item.net_sales == 0 and item.goal == Decimal("50.00") for item in result.by_branch)


def test_costs_hidden_without_permission() -> None:
    out = analysis_out(_analysis(costs=False))
    assert out.costs_visible is False
    assert out.totals.cost is None
    assert out.totals.margin is None
    assert all(item.cost is None and item.margin is None for item in out.top_products)


def test_rules() -> None:
    with pytest.raises(BusinessRuleError) as error:
        require_range(date(2026, 11, 2), date(2026, 11, 1))
    assert error.value.code == "sales_analytics_range_invalid"
    with pytest.raises(BusinessRuleError) as error:
        require_range(date(2025, 1, 1), date(2026, 11, 1))
    assert error.value.code == "sales_analytics_range_too_long"
    assert require_goal(Decimal("1500.555")) == Decimal("1500.56")
    with pytest.raises(BusinessRuleError):
        require_goal(Decimal("0"))


def test_catalogue_has_the_migrated_permissions() -> None:
    expected = {
        "sales_analytics:read",
        "sales_goals:manage",
        "fiscal_books:read",
        "fiscal_books:manage",
        "fiscal_periods:manage",
        "sales_credit:authorize",
        "sales_invoices:contingency",
        "sales_invoices:invalidate",
        "sales_invoices:notes",
        "sales_invoices:returns",
        "sales_receivables:read",
        "sales_receivables:collect",
    }
    assert expected <= ALL_PERMISSION_CODES
