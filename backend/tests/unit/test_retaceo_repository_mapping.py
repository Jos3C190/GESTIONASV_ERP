"""Unit tests for retaceo ORM metadata and repository mapping."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.entities.retaceo import Retaceo, RetaceoDetail, RetaceoStatus
from app.infrastructure.repositories.retaceo_repository import (
    SqlAlchemyRetaceoRepository,
    _to_entity,
)


def _item() -> Retaceo:
    retaceo_id = uuid.uuid4()
    detail = RetaceoDetail(
        id=uuid.uuid4(),
        retaceo_id=retaceo_id,
        purchase_detail_id=uuid.uuid4(),
        product_id=10,
        unit_id=3,
        quantity=Decimal("2"),
        cost_fob=Decimal("100.000000"),
        freight=Decimal("10.000000"),
        expenses=Decimal("5.000000"),
        dai=Decimal("15.000000"),
        total_cost=Decimal("130.000000"),
        unit_cost=Decimal("65.000000"),
    )
    return Retaceo(
        id=retaceo_id,
        company_id=uuid.uuid4(),
        code="RET-00001",
        purchase_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        created_by_id=uuid.uuid4(),
        currency="USD",
        details=(detail,),
        total_fob=Decimal("100.000000"),
        total_freight=Decimal("10.000000"),
        total_expenses=Decimal("5.000000"),
        total_dai=Decimal("15.000000"),
        import_vat=Decimal("13.000000"),
        total_cost=Decimal("130.000000"),
        status=RetaceoStatus.CALCULATED,
        notes="Prueba de mapeo",
    )


def test_repository_maps_retaceo_to_orm_with_exact_purchase_detail_identity() -> None:
    item = _item()

    model = SqlAlchemyRetaceoRepository._retaceo_model(item)

    assert model.id == item.id
    assert model.purchase_id == item.purchase_id
    assert model.branch_id == item.branch_id
    assert model.status == RetaceoStatus.CALCULATED.value
    assert len(model.details) == 1
    assert model.details[0].purchase_detail_id == item.details[0].purchase_detail_id
    assert model.details[0].unit_cost == Decimal("65.000000")


def test_repository_maps_orm_back_to_domain() -> None:
    item = _item()
    model = SqlAlchemyRetaceoRepository._retaceo_model(item)

    restored = _to_entity(model)

    assert restored == item
