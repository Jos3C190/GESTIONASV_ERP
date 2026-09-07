from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
)
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.organization import Branch, UserCompany, Warehouse
from app.infrastructure.models.user import User
from app.infrastructure.repositories.purchase_request_repository import (
    SqlAlchemyPurchaseRequestRepository,
)
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
async def purchase_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


async def _seed_references(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, int, int]:
    branch_row = (
        await session.execute(
            select(Branch.company_id, Branch.id, Warehouse.id)
            .join(Warehouse, Warehouse.branch_id == Branch.id)
            .where(
                Branch.deleted_at.is_(None),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
                Warehouse.deleted_at.is_(None),
                Warehouse.is_active.is_(True),
                Warehouse.operational_status == "active",
            )
            .limit(1)
        )
    ).one()
    company_id, branch_id, warehouse_id = branch_row

    # E2E fixtures intentionally delete all users between tests. Keep this
    # integration test independent from suite order by creating its own actor
    # inside the transaction that the fixture rolls back.
    suffix = uuid.uuid4().hex[:12]
    user = User(
        username=f"purchase-{suffix}",
        email=f"purchase-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        UserCompany(
            user_id=user.id,
            company_id=company_id,
            is_default=True,
            access_all_branches=True,
        )
    )
    await session.flush()

    product_row = (
        await session.execute(
            select(ProductModel.id_product, ProductModel.purchase_unit)
            .join(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.company_id == ProductModel.company_id,
                    CompanyUnitModel.unit_id == ProductModel.purchase_unit,
                ),
            )
            .where(
                ProductModel.company_id == company_id,
                ProductModel.deleted_at.is_(None),
                ProductModel.is_active.is_(True),
                ProductModel.lifecycle_status == "active",
                ProductModel.can_purchase.is_(True),
                CompanyUnitModel.is_enabled.is_(True),
            )
            .limit(1)
        )
    ).one()
    product_id, unit_id = product_row

    return company_id, branch_id, warehouse_id, user.id, product_id, unit_id


async def _persist_request(
    repository: SqlAlchemyPurchaseRequestRepository,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    user_id: uuid.UUID,
    product_id: int,
    unit_id: int,
) -> PurchaseRequest:
    request_id = uuid.uuid4()
    code = await repository.allocate_next_code(company_id)
    request = PurchaseRequest(
        id=request_id,
        company_id=company_id,
        code=code,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        requested_by_id=user_id,
        request_date=datetime.now(UTC),
        justification="Prueba de integración de compras",
        details=(
            PurchaseRequestDetail(
                id=uuid.uuid4(),
                purchase_request_id=request_id,
                product_id=product_id,
                unit_id=unit_id,
                quantity=Decimal("3.000000"),
            ),
        ),
    )
    return await repository.add_request(request)


@pytest.mark.asyncio
async def test_repository_resolves_tenant_scoped_references(
    purchase_session: AsyncSession,
) -> None:
    company_id, branch_id, warehouse_id, _user_id, product_id, unit_id = (
        await _seed_references(purchase_session)
    )
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)

    assert await repository.is_branch_available(company_id, branch_id)
    assert await repository.is_warehouse_available(company_id, branch_id, warehouse_id)
    assert not await repository.is_branch_available(uuid.uuid4(), branch_id)
    assert not await repository.is_warehouse_available(company_id, uuid.uuid4(), warehouse_id)

    product = await repository.get_product_reference(company_id, product_id)
    assert product is not None
    assert product.product_id == product_id
    assert product.purchase_unit_id == unit_id
    assert product.is_active
    assert product.can_purchase
    assert product.unit_enabled
    assert await repository.get_product_reference(uuid.uuid4(), product_id) is None


@pytest.mark.asyncio
async def test_repository_persists_and_hides_request_from_other_tenant(
    purchase_session: AsyncSession,
) -> None:
    company_id, branch_id, warehouse_id, user_id, product_id, unit_id = (
        await _seed_references(purchase_session)
    )
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        user_id=user_id,
        product_id=product_id,
        unit_id=unit_id,
    )

    loaded = await repository.get_request(company_id, saved.id)
    hidden = await repository.get_request(uuid.uuid4(), saved.id)
    items, total = await repository.list_requests(company_id, limit=500)

    assert loaded is not None
    assert loaded.code == saved.code
    assert loaded.details[0].unit_id == unit_id
    assert hidden is None
    assert total >= 1
    assert saved.id in {item.id for item in items}


@pytest.mark.asyncio
async def test_code_allocator_advances_after_persisted_request(
    purchase_session: AsyncSession,
) -> None:
    company_id, branch_id, warehouse_id, user_id, product_id, unit_id = (
        await _seed_references(purchase_session)
    )
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        user_id=user_id,
        product_id=product_id,
        unit_id=unit_id,
    )

    next_code = await repository.allocate_next_code(company_id)
    current_number = int(saved.code.removeprefix("SCR-"))
    next_number = int(next_code.removeprefix("SCR-"))

    assert next_number == current_number + 1


@pytest.mark.asyncio
async def test_repository_replaces_lines_and_updates_status(
    purchase_session: AsyncSession,
) -> None:
    company_id, branch_id, warehouse_id, user_id, product_id, unit_id = (
        await _seed_references(purchase_session)
    )
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        user_id=user_id,
        product_id=product_id,
        unit_id=unit_id,
    )
    replacement_detail = PurchaseRequestDetail(
        id=uuid.uuid4(),
        purchase_request_id=saved.id,
        product_id=product_id,
        unit_id=unit_id,
        quantity=Decimal("9.000000"),
        notes="Cantidad corregida",
    )
    replacement = PurchaseRequest(
        id=saved.id,
        company_id=saved.company_id,
        code=saved.code,
        branch_id=saved.branch_id,
        warehouse_id=saved.warehouse_id,
        requested_by_id=saved.requested_by_id,
        request_date=saved.request_date,
        required_date=saved.required_date,
        justification="Solicitud corregida",
        status=saved.status,
        notes=saved.notes,
        details=(replacement_detail,),
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )

    replaced = await repository.replace_draft(replacement)
    submitted = await repository.update_status(
        company_id,
        saved.id,
        PurchaseRequestStatus.SUBMITTED,
    )

    assert replaced is not None
    assert replaced.justification == "Solicitud corregida"
    assert replaced.details[0].quantity == Decimal("9.000000")
    assert submitted is not None
    assert submitted.status is PurchaseRequestStatus.SUBMITTED
