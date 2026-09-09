from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
)
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    ProductModel,
    UnitModel,
)
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
    UserCompany,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.purchase_request_repository import (
    SqlAlchemyPurchaseRequestRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class PurchaseRequestTestGraph:
    """ORM records owned by one purchase-request integration test."""

    department: GeographicDepartment
    municipality: Municipality
    district: District
    company: Company
    branch: Branch
    warehouse_category: WarehouseCategory
    warehouse: Warehouse
    user: User
    employee: Employee
    user_company: UserCompany
    unit: UnitModel
    company_unit: CompanyUnitModel
    category: CategoryModel
    product: ProductModel


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


async def _build_test_graph(session: AsyncSession) -> PurchaseRequestTestGraph:
    """Create the smallest valid, tenant-scoped ORM graph for this suite."""

    suffix = uuid.uuid4().hex[:12]
    department = GeographicDepartment(id=uuid.uuid4(), name=f"Purchase department {suffix}")
    session.add(department)
    await session.flush()

    municipality = Municipality(
        id=uuid.uuid4(),
        department_id=department.id,
        name=f"Purchase municipality {suffix}",
    )
    session.add(municipality)
    await session.flush()

    district = District(
        id=uuid.uuid4(),
        municipality_id=municipality.id,
        name=f"Purchase district {suffix}",
    )
    session.add(district)
    await session.flush()

    company = Company(
        id=uuid.uuid4(),
        name=f"Purchase company {suffix}, S.A. de C.V.",
        commercial_name=f"Purchase company {suffix}",
        nit=f"PUR-{suffix}-NIT",
        nrc=f"PUR-{suffix}-NRC",
        address="San Salvador, El Salvador",
        department_id=department.id,
        municipality_id=municipality.id,
        district_id=district.id,
        is_active=True,
    )
    session.add(company)
    await session.flush()

    branch = Branch(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Purchase branch {suffix}",
        code=f"PB-{suffix}",
        address="San Salvador, El Salvador",
        department_id=department.id,
        municipality_id=municipality.id,
        district_id=district.id,
        operational_status="active",
        is_active=True,
    )
    warehouse_category = WarehouseCategory(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Purchase warehouse category {suffix}",
        is_active=True,
    )
    session.add_all([branch, warehouse_category])
    await session.flush()

    warehouse = Warehouse(
        id=uuid.uuid4(),
        branch_id=branch.id,
        warehouse_category_id=warehouse_category.id,
        name=f"Purchase warehouse {suffix}",
        code=f"PW-{suffix}",
        operational_status="active",
        capacity_enforcement_mode="disabled",
        storage_eligible=True,
        is_active=True,
    )
    session.add(warehouse)
    await session.flush()

    user = User(
        id=uuid.uuid4(),
        username=f"purchase-{suffix}",
        email=f"purchase-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    employee = Employee(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user.id,
        employee_code=f"PUR-{suffix}-EMP",
        first_name="Purchase",
        last_name="Tester",
        status="activo",
    )
    session.add(employee)
    await session.flush()

    user_company = UserCompany(
        user_id=user.id,
        company_id=company.id,
        is_default=True,
        access_all_branches=True,
        last_branch_id=branch.id,
    )
    session.add(user_company)
    await session.flush()

    unit = UnitModel(
        owner_company_id=company.id,
        code=f"PUR-{suffix}-UNIT",
        symbol="u",
        name=f"Purchase unit {suffix}",
        type="quantity",
        is_standard=False,
        is_active=True,
    )
    session.add(unit)
    await session.flush()

    company_unit = CompanyUnitModel(
        company_id=company.id,
        unit_id=unit.id_unit,
        is_enabled=True,
    )
    session.add(company_unit)
    await session.flush()

    category = CategoryModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        name=f"Purchase category {suffix}",
        is_active=True,
    )
    session.add(category)
    await session.flush()

    product = ProductModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        id_category=category.id_category,
        sku=f"PUR-{suffix}-SKU",
        name=f"Purchase product {suffix}",
        product_kind="goods",
        lifecycle_status="active",
        can_purchase=True,
        can_sell=True,
        variant_mode="standalone",
        purchase_unit=unit.id_unit,
        sale_unit=unit.id_unit,
        is_active=True,
        keywords=[],
    )
    session.add(product)
    await session.flush()

    return PurchaseRequestTestGraph(
        department=department,
        municipality=municipality,
        district=district,
        company=company,
        branch=branch,
        warehouse_category=warehouse_category,
        warehouse=warehouse,
        user=user,
        employee=employee,
        user_company=user_company,
        unit=unit,
        company_unit=company_unit,
        category=category,
        product=product,
    )


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
    graph = await _build_test_graph(purchase_session)
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)

    assert await repository.is_branch_available(graph.company.id, graph.branch.id)
    assert await repository.is_warehouse_available(
        graph.company.id, graph.branch.id, graph.warehouse.id
    )
    assert not await repository.is_branch_available(uuid.uuid4(), graph.branch.id)
    assert not await repository.is_warehouse_available(
        graph.company.id, uuid.uuid4(), graph.warehouse.id
    )

    product = await repository.get_product_reference(graph.company.id, graph.product.id_product)
    assert product is not None
    assert product.product_id == graph.product.id_product
    assert product.purchase_unit_id == graph.unit.id_unit
    assert product.is_active
    assert product.can_purchase
    assert product.unit_enabled
    assert await repository.get_product_reference(uuid.uuid4(), graph.product.id_product) is None


@pytest.mark.asyncio
async def test_repository_exposes_non_eligible_product_flags(
    purchase_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(purchase_session)
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)

    graph.product.can_purchase = False
    await purchase_session.flush()
    not_purchasable = await repository.get_product_reference(
        graph.company.id, graph.product.id_product
    )

    assert not_purchasable is not None
    assert not not_purchasable.can_purchase
    assert not_purchasable.is_active
    assert not_purchasable.unit_enabled

    graph.product.can_purchase = True
    graph.company_unit.is_enabled = False
    await purchase_session.flush()
    disabled_unit = await repository.get_product_reference(
        graph.company.id, graph.product.id_product
    )

    assert disabled_unit is not None
    assert disabled_unit.can_purchase
    assert not disabled_unit.unit_enabled


@pytest.mark.asyncio
async def test_repository_persists_and_hides_request_from_other_tenant(
    purchase_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(purchase_session)
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=graph.company.id,
        branch_id=graph.branch.id,
        warehouse_id=graph.warehouse.id,
        user_id=graph.user.id,
        product_id=graph.product.id_product,
        unit_id=graph.unit.id_unit,
    )

    loaded = await repository.get_request(graph.company.id, saved.id)
    hidden = await repository.get_request(uuid.uuid4(), saved.id)
    items, total = await repository.list_requests(graph.company.id, limit=500)

    assert loaded is not None
    assert loaded.code == saved.code
    assert loaded.details[0].unit_id == graph.unit.id_unit
    assert hidden is None
    assert total >= 1
    assert saved.id in {item.id for item in items}


@pytest.mark.asyncio
async def test_code_allocator_advances_after_persisted_request(
    purchase_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(purchase_session)
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=graph.company.id,
        branch_id=graph.branch.id,
        warehouse_id=graph.warehouse.id,
        user_id=graph.user.id,
        product_id=graph.product.id_product,
        unit_id=graph.unit.id_unit,
    )

    next_code = await repository.allocate_next_code(graph.company.id)
    current_number = int(saved.code.removeprefix("SCR-"))
    next_number = int(next_code.removeprefix("SCR-"))

    assert next_number == current_number + 1


@pytest.mark.asyncio
async def test_repository_replaces_lines_and_updates_status(
    purchase_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(purchase_session)
    repository = SqlAlchemyPurchaseRequestRepository(purchase_session)
    saved = await _persist_request(
        repository,
        company_id=graph.company.id,
        branch_id=graph.branch.id,
        warehouse_id=graph.warehouse.id,
        user_id=graph.user.id,
        product_id=graph.product.id_product,
        unit_id=graph.unit.id_unit,
    )
    replacement_detail = PurchaseRequestDetail(
        id=uuid.uuid4(),
        purchase_request_id=saved.id,
        product_id=graph.product.id_product,
        unit_id=graph.unit.id_unit,
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
        graph.company.id,
        saved.id,
        PurchaseRequestStatus.SUBMITTED,
    )

    assert replaced is not None
    assert replaced.justification == "Solicitud corregida"
    assert replaced.details[0].quantity == Decimal("9.000000")
    assert submitted is not None
    assert submitted.status is PurchaseRequestStatus.SUBMITTED
