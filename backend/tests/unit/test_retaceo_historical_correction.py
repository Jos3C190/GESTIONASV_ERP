"""A retaceo never rewrites the receipt FOB; value-only comparisons keep stock intact."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_valuation import ValuationEvent
from app.infrastructure.repositories.retaceo_average_comparison import _existing_receipt_comparison

from tests.unit.test_purchase_conversion import RetaceoSession, RetaceoValuation

D = Decimal


@pytest.mark.asyncio
async def test_fob_that_differs_from_the_receipt_is_rejected_even_with_a_long_note():
    """The historical FOB correction was removed: notes can no longer bypass the check."""
    retaceo = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        purchase_id=uuid.uuid4(),
        currency="CRC",
        code="RET-CORRECCION",
        notes="Descuento corregido según confirmación del responsable y factura original.",
        details=[
            SimpleNamespace(
                purchase_detail_id=uuid.uuid4(), cost_fob=D("1000"), total_cost=D("1200")
            )
        ],
    )
    session = RetaceoSession(retaceo.company_id, retaceo.purchase_id)
    session.receipt.source_value = D("0")
    with pytest.raises(InventoryOperationError) as failure:
        await RetaceoValuation(session).apply_retaceo(retaceo, uuid.uuid4())
    assert failure.value.code == "retaceo_receipt_cost_mismatch"
    assert session.added == []
    assert session.receipt.source_value == D("0")


@pytest.mark.asyncio
async def test_correction_preview_revalues_remaining_stock_and_never_adds_quantity():
    source_id, item_id, detail_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source = SimpleNamespace(
        id=source_id,
        inventory_item_id=item_id,
        purchase_detail_id=detail_id,
        quantity_base=D("10"),
        source_value=D("0"),
    )
    original = [
        ValuationEvent(source_id, "receipt", D("10"), D("0")),
        ValuationEvent(uuid.uuid4(), "issue", D("2")),
    ]

    class Session:
        async def scalars(self, query):
            return SimpleNamespace(all=lambda: [source])

        async def get(self, model, key):
            return SimpleNamespace(product_id=4, base_unit_id=2)

    class Valuation:
        session = Session()

        async def _rows(self, company_id, item):
            return original

        def _event(self, row):
            return row

    retaceo = SimpleNamespace(
        company_id=uuid.uuid4(),
        details=[SimpleNamespace(purchase_detail_id=detail_id, total_cost=D("100"))],
    )
    result = await _existing_receipt_comparison(Valuation(), retaceo, "USD", None)
    line = result.lines[0]
    assert result.value_only
    assert line.previous_quantity == line.resulting_quantity == D("8")
    assert line.incoming_quantity == D("0")
    assert line.incoming_value == line.resulting_value == D("80")
    assert line.resulting_average == D("10")
    assert original[0].value == D("0")
