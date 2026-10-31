"""A row lock must also refresh documents read before another request commits."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from app.application.sales.deliveries import SalesDeliveryService
from app.application.sales.returns import SalesReturnService
from app.application.sales.service import SalesService
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.inventory_adjustment import InventoryAdjustmentModel
from app.infrastructure.models.organization import Branch, UserCompany, Warehouse
from app.infrastructure.models.sales import SaleModel, SalesCustomerModel, SalesQuotationModel
from app.infrastructure.models.sales_delivery import SalesDeliveryModel
from app.infrastructure.models.sales_return import SalesReturnModel
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)
from sqlalchemy import select, update

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_type", "method", "model"),
    [
        (SalesService, "get_quotation", SalesQuotationModel),
        (SalesService, "get_sale", SaleModel),
        (SalesDeliveryService, "_sale", SaleModel),
        (SalesDeliveryService, "_delivery", SalesDeliveryModel),
        (SalesReturnService, "_sale", SaleModel),
        (SalesReturnService, "_return", SalesReturnModel),
        (SqlAlchemyInventoryAdjustmentRepository, "_header", InventoryAdjustmentModel),
    ],
)
async def test_locked_document_observes_change_committed_after_initial_read(
    service_type, method, model
):
    company_id = await get_test_company_id()
    suffix = uuid.uuid4().hex[:12]
    async with async_session_factory() as setup:
        actor_id = await setup.scalar(
            select(UserCompany.user_id).where(UserCompany.company_id == company_id).limit(1)
        )
        branch_id = await setup.scalar(
            select(Branch.id).where(Branch.company_id == company_id).limit(1)
        )
        common = {"company_id": company_id, "created_by_id": actor_id}
        today = datetime.now(UTC).date()
        customer = SalesCustomerModel(
            **common, updated_by_id=actor_id, code=f"LOCK-{suffix}", name="Lock refresh test"
        )
        setup.add(customer)
        await setup.flush()
        quote = SalesQuotationModel(
            **common,
            branch_id=branch_id,
            customer_id=customer.id,
            code=f"Q-{suffix}",
            quotation_date=today,
            valid_until=today,
        )
        setup.add(quote)
        await setup.flush()
        sale = SaleModel(
            **common,
            branch_id=branch_id,
            customer_id=customer.id,
            quotation_id=quote.id,
            code=f"S-{suffix}",
            subtotal=0,
            total=0,
        )
        setup.add(sale)
        await setup.flush()
        delivery = SalesDeliveryModel(
            **common, branch_id=branch_id, sale_id=sale.id, code=f"E-{suffix}"
        )
        returned = SalesReturnModel(
            **common,
            branch_id=branch_id,
            sale_id=sale.id,
            updated_by_id=actor_id,
            code=f"R-{suffix}",
        )
        setup.add_all([delivery, returned])
        warehouse_id = await setup.scalar(
            select(Warehouse.id)
            .where(Warehouse.company_id == company_id, Warehouse.is_transit.is_(False))
            .limit(1)
        )
        adjustment = InventoryAdjustmentModel(
            **common,
            code=f"A-{suffix}",
            warehouse_id=warehouse_id,
            operational_date=today,
            accounting_date=today,
            reason="Lock refresh test",
            document_reference=suffix,
            created_at=datetime.now(UTC),
        )
        setup.add(adjustment)
        await setup.flush()
        row_id = next(
            row.id
            for row in [quote, sale, delivery, returned, adjustment]
            if isinstance(row, model)
        )
        await setup.commit()

    try:
        async with async_session_factory() as reader:
            if service_type is SqlAlchemyInventoryAdjustmentRepository:
                args = (reader,)
            elif service_type is SalesService:
                args = (reader, MagicMock())
            else:
                args = (reader, MagicMock(), MagicMock())
            service = service_type(*args)
            cached = await getattr(service, method)(company_id, row_id)
            assert cached.notes is None
            # A different request commits while this request still holds its
            # previously loaded ORM instance (as authorization helpers can do).
            async with async_session_factory() as writer:
                await writer.execute(
                    update(model).where(model.id == row_id).values(notes="Concurrent change")
                )
                await writer.commit()
            locked = await getattr(service, method)(company_id, row_id, lock=True)
            assert locked.notes == "Concurrent change"
            await reader.rollback()
    finally:
        await dispose_engine()
