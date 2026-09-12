from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationRequest,
    PurchaseQuotationRequestDetail,
    PurchaseQuotationStatus,
)
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
)
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    CountryModel,
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
from app.infrastructure.models.purchase_quotation import ExpenseTypeModel
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import CurrencyModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.purchase_quotation_repository import (
    SqlAlchemyPurchaseQuotationRepository,
)
from app.infrastructure.repositories.purchase_request_repository import (
    SqlAlchemyPurchaseRequestRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class QuotationTestGraph:
    company: Company
    branch: Branch
    warehouse: Warehouse
    user: User
    unit: UnitModel
    products: tuple[ProductModel, ProductModel]
    supplier: SupplierModel
    currency: CurrencyModel
    expense_type: ExpenseTypeModel


@pytest.fixture
async def quotation_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


async def _build_test_graph(session: AsyncSession) -> QuotationTestGraph:
    suffix = uuid.uuid4().hex[:10]
    department = GeographicDepartment(id=uuid.uuid4(), name=f"Quotation department {suffix}")
    session.add(department)
    await session.flush()
    municipality = Municipality(
        id=uuid.uuid4(),
        department_id=department.id,
        name=f"Quotation municipality {suffix}",
    )
    session.add(municipality)
    await session.flush()
    district = District(
        id=uuid.uuid4(),
        municipality_id=municipality.id,
        name=f"Quotation district {suffix}",
    )
    session.add(district)
    await session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Quotation company {suffix}, S.A. de C.V.",
        commercial_name=f"Quotation company {suffix}",
        nit=f"QUO-{suffix}-NIT",
        nrc=f"QUO-{suffix}-NRC",
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
        name=f"Quotation branch {suffix}",
        code=f"QB-{suffix}",
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
        name=f"Quotation warehouse category {suffix}",
        is_active=True,
    )
    session.add_all([branch, warehouse_category])
    await session.flush()
    warehouse = Warehouse(
        id=uuid.uuid4(),
        branch_id=branch.id,
        warehouse_category_id=warehouse_category.id,
        name=f"Quotation warehouse {suffix}",
        code=f"QW-{suffix}",
        operational_status="active",
        capacity_enforcement_mode="disabled",
        storage_eligible=True,
        is_active=True,
    )
    session.add(warehouse)
    user = User(
        id=uuid.uuid4(),
        username=f"quotation-{suffix}",
        email=f"quotation-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
    )
    session.add_all([warehouse, user])
    await session.flush()
    employee = Employee(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user.id,
        employee_code=f"QUO-{suffix}-EMP",
        first_name="Quotation",
        last_name="Tester",
        status="activo",
    )
    user_company = UserCompany(
        user_id=user.id,
        company_id=company.id,
        is_default=True,
        access_all_branches=True,
        last_branch_id=branch.id,
    )
    session.add_all([employee, user_company])
    await session.flush()
    unit = UnitModel(
        owner_company_id=company.id,
        code=f"QUO-{suffix}-UNIT",
        symbol="u",
        name=f"Quotation unit {suffix}",
        type="quantity",
        is_standard=False,
        is_active=True,
    )
    session.add(unit)
    await session.flush()
    session.add(CompanyUnitModel(company_id=company.id, unit_id=unit.id_unit, is_enabled=True))
    category = CategoryModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        name=f"Quotation category {suffix}",
        is_active=True,
    )
    session.add(category)
    await session.flush()
    products = (
        ProductModel(
            company_id=company.id,
            uuid=uuid.uuid4(),
            id_category=category.id_category,
            sku=f"QUO-{suffix}-A",
            name=f"Quotation product A {suffix}",
            product_kind="goods",
            lifecycle_status="active",
            can_purchase=True,
            can_sell=True,
            variant_mode="standalone",
            purchase_unit=unit.id_unit,
            sale_unit=unit.id_unit,
            is_active=True,
            keywords=[],
        ),
        ProductModel(
            company_id=company.id,
            uuid=uuid.uuid4(),
            id_category=category.id_category,
            sku=f"QUO-{suffix}-B",
            name=f"Quotation product B {suffix}",
            product_kind="goods",
            lifecycle_status="active",
            can_purchase=True,
            can_sell=True,
            variant_mode="standalone",
            purchase_unit=unit.id_unit,
            sale_unit=unit.id_unit,
            is_active=True,
            keywords=[],
        ),
    )
    session.add_all(products)
    country = CountryModel(
        name=f"Quotation Country {suffix}",
        iso_code_2="QZ",
        iso_code_3="QZZ",
        phone_code="+999",
        is_active=True,
    )
    session.add(country)
    await session.flush()
    supplier = SupplierModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        code=f"QS-{suffix}",
        name=f"Quotation Supplier {suffix}",
        country_id=country.id_country,
        is_active=True,
        supplier_status="approved",
    )
    currency = CurrencyModel(
        code="QZZ",
        name="Quotation Test Currency",
        symbol="Q",
        decimal_places=2,
        is_active=True,
    )
    expense_type = ExpenseTypeModel(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Quotation freight {suffix}",
        is_active=True,
    )
    session.add_all([supplier, currency, expense_type])
    await session.flush()
    return QuotationTestGraph(
        company=company,
        branch=branch,
        warehouse=warehouse,
        user=user,
        unit=unit,
        products=products,
        supplier=supplier,
        currency=currency,
        expense_type=expense_type,
    )


async def _persist_approved_request(
    session: AsyncSession,
    graph: QuotationTestGraph,
) -> PurchaseRequest:
    repository = SqlAlchemyPurchaseRequestRepository(session)
    request_id = uuid.uuid4()
    request = PurchaseRequest(
        id=request_id,
        company_id=graph.company.id,
        code=await repository.allocate_next_code(graph.company.id),
        branch_id=graph.branch.id,
        warehouse_id=graph.warehouse.id,
        requested_by_id=graph.user.id,
        request_date=datetime.now(UTC),
        justification="Prueba de integración de cotizaciones",
        status=PurchaseRequestStatus.APPROVED,
        details=tuple(
            PurchaseRequestDetail(
                id=uuid.uuid4(),
                purchase_request_id=request_id,
                product_id=product.id_product,
                unit_id=graph.unit.id_unit,
                quantity=Decimal("4.000000"),
            )
            for product in graph.products
        ),
    )
    return await repository.add_request(request)


def _quotation_for_detail(
    *,
    graph: QuotationTestGraph,
    request: PurchaseRequest,
    request_detail: PurchaseRequestDetail,
    code: str,
) -> PurchaseQuotation:
    quotation_id = uuid.uuid4()
    link_id = uuid.uuid4()
    quotation_detail_id = uuid.uuid4()
    return PurchaseQuotation(
        id=quotation_id,
        company_id=graph.company.id,
        code=code,
        supplier_id=graph.supplier.id_supplier,
        quotation_date=datetime.now(UTC),
        currency=graph.currency.code,
        created_by_id=graph.user.id,
        status=PurchaseQuotationStatus.REQUESTED,
        request_links=(
            PurchaseQuotationRequest(
                id=link_id,
                purchase_quotation_id=quotation_id,
                purchase_request_id=request.id,
                details=(
                    PurchaseQuotationRequestDetail(
                        id=uuid.uuid4(),
                        purchase_quotation_request_id=link_id,
                        purchase_quotation_detail_id=quotation_detail_id,
                        purchase_request_detail_id=request_detail.id,
                        quantity=request_detail.quantity,
                    ),
                ),
            ),
        ),
        details=(
            PurchaseQuotationDetail(
                id=quotation_detail_id,
                purchase_quotation_id=quotation_id,
                product_id=request_detail.product_id,
                unit_id=request_detail.unit_id,
                quantity=request_detail.quantity,
                unit_price=Decimal("0"),
            ),
        ),
    )


def _received_version(
    quotation: PurchaseQuotation,
    request_detail: PurchaseRequestDetail,
) -> PurchaseQuotation:
    line_total = request_detail.quantity * Decimal("10")
    return PurchaseQuotation(
        id=quotation.id,
        company_id=quotation.company_id,
        code=quotation.code,
        supplier_id=quotation.supplier_id,
        quotation_date=datetime.now(UTC),
        currency=quotation.currency,
        created_by_id=quotation.created_by_id,
        request_links=quotation.request_links,
        details=(
            PurchaseQuotationDetail(
                id=quotation.details[0].id,
                purchase_quotation_id=quotation.id,
                product_id=request_detail.product_id,
                unit_id=request_detail.unit_id,
                quantity=request_detail.quantity,
                unit_price=Decimal("10"),
                subtotal=line_total,
                total=line_total,
            ),
        ),
        subtotal=line_total,
        total=line_total,
        status=PurchaseQuotationStatus.RECEIVED,
    )


@pytest.mark.asyncio
async def test_repository_persists_and_hides_quotation_from_other_tenant(
    quotation_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(quotation_session)
    request = await _persist_approved_request(quotation_session, graph)
    repository = SqlAlchemyPurchaseQuotationRepository(quotation_session)
    quotation = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[0],
        code=await repository.allocate_next_code(graph.company.id),
    )

    saved = await repository.add_quotation(quotation)
    loaded = await repository.get_quotation(graph.company.id, saved.id)
    hidden = await repository.get_quotation(uuid.uuid4(), saved.id)

    assert loaded is not None
    assert loaded.code == saved.code
    assert loaded.request_links[0].purchase_request_id == request.id
    assert hidden is None
    assert await repository.allocate_next_code(graph.company.id) == "COT-00002"


@pytest.mark.asyncio
async def test_repository_resolves_tenant_scoped_supplier_currency_and_coverage(
    quotation_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(quotation_session)
    request = await _persist_approved_request(quotation_session, graph)
    repository = SqlAlchemyPurchaseQuotationRepository(quotation_session)
    quotation = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[0],
        code=await repository.allocate_next_code(graph.company.id),
    )
    saved = await repository.add_quotation(quotation)

    supplier = await repository.get_supplier_reference(
        graph.company.id,
        graph.supplier.id_supplier,
    )
    hidden_supplier = await repository.get_supplier_reference(
        uuid.uuid4(),
        graph.supplier.id_supplier,
    )
    reference = await repository.get_request_reference(graph.company.id, request.id)
    coverage = await repository.get_coverage_references(graph.company.id, saved.id)

    assert supplier is not None
    assert supplier.supplier_status == "approved"
    assert hidden_supplier is None
    assert await repository.is_currency_active(graph.currency.code)
    assert reference is not None
    assert len(reference.details) == 2
    assert coverage[0].purchase_request_detail_id == request.details[0].id
    assert coverage[0].purchase_quotation_detail_id == saved.details[0].id
    assert await repository.is_expense_type_active(graph.company.id, graph.expense_type.id)
    assert not await repository.is_expense_type_active(uuid.uuid4(), graph.expense_type.id)


@pytest.mark.asyncio
async def test_repository_advances_request_from_partial_to_fully_quoted(
    quotation_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(quotation_session)
    request = await _persist_approved_request(quotation_session, graph)
    quotation_repository = SqlAlchemyPurchaseQuotationRepository(quotation_session)
    request_repository = SqlAlchemyPurchaseRequestRepository(quotation_session)

    first = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[0],
        code=await quotation_repository.allocate_next_code(graph.company.id),
    )
    await quotation_repository.add_quotation(first)
    await quotation_repository.replace_response(_received_version(first, request.details[0]))
    await quotation_repository.advance_purchase_request_quotation_statuses(
        graph.company.id,
        (request.id,),
    )
    partial = await request_repository.get_request(graph.company.id, request.id)

    second = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[1],
        code=await quotation_repository.allocate_next_code(graph.company.id),
    )
    await quotation_repository.add_quotation(second)
    await quotation_repository.replace_response(_received_version(second, request.details[1]))
    await quotation_repository.advance_purchase_request_quotation_statuses(
        graph.company.id,
        (request.id,),
    )
    quoted = await request_repository.get_request(graph.company.id, request.id)

    assert partial is not None
    assert partial.status is PurchaseRequestStatus.PARTIALLY_QUOTED
    assert quoted is not None
    assert quoted.status is PurchaseRequestStatus.QUOTED


@pytest.mark.asyncio
async def test_repository_lists_only_comparable_quotes_for_requested_purchase_request(
    quotation_session: AsyncSession,
) -> None:
    graph = await _build_test_graph(quotation_session)
    request = await _persist_approved_request(quotation_session, graph)
    repository = SqlAlchemyPurchaseQuotationRepository(quotation_session)
    first = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[0],
        code=await repository.allocate_next_code(graph.company.id),
    )
    await repository.add_quotation(first)
    received = await repository.replace_response(_received_version(first, request.details[0]))
    assert received is not None

    draft = _quotation_for_detail(
        graph=graph,
        request=request,
        request_detail=request.details[1],
        code=await repository.allocate_next_code(graph.company.id),
    )
    draft = PurchaseQuotation(
        id=draft.id,
        company_id=draft.company_id,
        code=draft.code,
        supplier_id=draft.supplier_id,
        quotation_date=draft.quotation_date,
        currency=draft.currency,
        created_by_id=draft.created_by_id,
        request_links=draft.request_links,
        details=draft.details,
        status=PurchaseQuotationStatus.DRAFT,
    )
    await repository.add_quotation(draft)

    comparable = await repository.list_comparable(graph.company.id, request.id)
    hidden = await repository.list_comparable(uuid.uuid4(), request.id)

    assert [item.id for item in comparable] == [received.id]
    assert hidden == []
