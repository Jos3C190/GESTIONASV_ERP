from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderExpense,
    PurchaseOrderStatus,
)
from app.domain.entities.purchase_order_expense_document import PurchaseOrderExpenseDocument
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
from app.infrastructure.models.document import DocumentAssetModel
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
from app.infrastructure.repositories.purchase_order_expense_document_repository import (
    SqlAlchemyPurchaseOrderExpenseDocumentRepository,
)
from app.infrastructure.repositories.purchase_order_repository import (
    SqlAlchemyPurchaseOrderRepository,
)
from app.infrastructure.repositories.purchase_quotation_repository import (
    SqlAlchemyPurchaseQuotationRepository,
)
from app.infrastructure.repositories.purchase_request_repository import (
    SqlAlchemyPurchaseRequestRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class PurchaseOrderTestGraph:
    company: Company
    branch: Branch
    warehouse: Warehouse
    user: User
    unit: UnitModel
    product: ProductModel
    supplier: SupplierModel
    currency: CurrencyModel
    expense_type: ExpenseTypeModel


@pytest.fixture
async def order_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


async def _build_graph(session: AsyncSession) -> PurchaseOrderTestGraph:
    suffix = uuid.uuid4().hex[:10]
    department = GeographicDepartment(id=uuid.uuid4(), name=f"Order department {suffix}")
    session.add(department)
    await session.flush()
    municipality = Municipality(
        id=uuid.uuid4(),
        department_id=department.id,
        name=f"Order municipality {suffix}",
    )
    session.add(municipality)
    await session.flush()
    district = District(
        id=uuid.uuid4(),
        municipality_id=municipality.id,
        name=f"Order district {suffix}",
    )
    session.add(district)
    await session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Order company {suffix}, S.A. de C.V.",
        commercial_name=f"Order company {suffix}",
        nit=f"ORD-{suffix}-NIT",
        nrc=f"ORD-{suffix}-NRC",
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
        name=f"Order branch {suffix}",
        code=f"OB-{suffix}",
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
        name=f"Order warehouse category {suffix}",
        is_active=True,
    )
    session.add_all([branch, warehouse_category])
    await session.flush()
    warehouse = Warehouse(
        id=uuid.uuid4(),
        branch_id=branch.id,
        warehouse_category_id=warehouse_category.id,
        name=f"Order warehouse {suffix}",
        code=f"OW-{suffix}",
        operational_status="active",
        capacity_enforcement_mode="disabled",
        storage_eligible=True,
        is_active=True,
    )
    user = User(
        id=uuid.uuid4(),
        username=f"order-{suffix}",
        email=f"order-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
    )
    session.add_all([warehouse, user])
    await session.flush()
    employee = Employee(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user.id,
        employee_code=f"ORD-{suffix}-EMP",
        first_name="Order",
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
        code=f"ORD-{suffix}-UNIT",
        symbol="u",
        name=f"Order unit {suffix}",
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
        name=f"Order category {suffix}",
        is_active=True,
    )
    session.add(category)
    await session.flush()
    product = ProductModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        id_category=category.id_category,
        sku=f"ORD-{suffix}-A",
        name=f"Order product {suffix}",
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
    country = CountryModel(
        name=f"Order Country {suffix}",
        iso_code_2="OQ",
        iso_code_3="OQQ",
        phone_code="+998",
        is_active=True,
    )
    session.add(country)
    await session.flush()
    supplier = SupplierModel(
        company_id=company.id,
        uuid=uuid.uuid4(),
        code=f"OS-{suffix}",
        name=f"Order Supplier {suffix}",
        country_id=country.id_country,
        is_active=True,
        supplier_status="approved",
    )
    currency = CurrencyModel(
        code="OQQ",
        name="Order Test Currency",
        symbol="O",
        decimal_places=2,
        is_active=True,
    )
    expense_type = ExpenseTypeModel(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Order freight {suffix}",
        is_active=True,
    )
    session.add_all([supplier, currency, expense_type])
    await session.flush()
    return PurchaseOrderTestGraph(
        company=company,
        branch=branch,
        warehouse=warehouse,
        user=user,
        unit=unit,
        product=product,
        supplier=supplier,
        currency=currency,
        expense_type=expense_type,
    )


async def _persist_request(
    session: AsyncSession,
    graph: PurchaseOrderTestGraph,
    *,
    quantity: Decimal,
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
        justification="Prueba de integración de órdenes de compra",
        status=PurchaseRequestStatus.QUOTED,
        details=(
            PurchaseRequestDetail(
                id=uuid.uuid4(),
                purchase_request_id=request_id,
                product_id=graph.product.id_product,
                unit_id=graph.unit.id_unit,
                quantity=quantity,
            ),
        ),
    )
    return await repository.add_request(request)


async def _persist_selected_quotation(
    session: AsyncSession,
    graph: PurchaseOrderTestGraph,
    requests: tuple[PurchaseRequest, ...],
) -> PurchaseQuotation:
    repository = SqlAlchemyPurchaseQuotationRepository(session)
    quotation_id = uuid.uuid4()
    quotation_detail_id = uuid.uuid4()
    links: list[PurchaseQuotationRequest] = []
    total_quantity = Decimal("0")
    for request in requests:
        link_id = uuid.uuid4()
        request_detail = request.details[0]
        total_quantity += request_detail.quantity
        links.append(
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
            )
        )
    subtotal = total_quantity * Decimal("10")
    quotation = PurchaseQuotation(
        id=quotation_id,
        company_id=graph.company.id,
        code=await repository.allocate_next_code(graph.company.id),
        supplier_id=graph.supplier.id_supplier,
        quotation_date=datetime.now(UTC),
        currency=graph.currency.code,
        created_by_id=graph.user.id,
        request_links=tuple(links),
        details=(
            PurchaseQuotationDetail(
                id=quotation_detail_id,
                purchase_quotation_id=quotation_id,
                product_id=graph.product.id_product,
                unit_id=graph.unit.id_unit,
                quantity=total_quantity,
                available_quantity=total_quantity,
                unit_price=Decimal("10"),
                subtotal=subtotal,
                total=subtotal,
            ),
        ),
        payment_terms="30 días",
        subtotal=subtotal,
        total=subtotal,
        status=PurchaseQuotationStatus.SELECTED,
    )
    return await repository.add_quotation(quotation)


async def _build_order(
    repository: SqlAlchemyPurchaseOrderRepository,
    graph: PurchaseOrderTestGraph,
    quotation: PurchaseQuotation,
    *,
    quantity: Decimal,
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT,
) -> PurchaseOrder:
    order_id = uuid.uuid4()
    subtotal = quantity * Decimal("10")
    return PurchaseOrder(
        id=order_id,
        company_id=graph.company.id,
        code=await repository.allocate_next_code(graph.company.id),
        supplier_id=graph.supplier.id_supplier,
        branch_id=graph.branch.id,
        warehouse_id=graph.warehouse.id,
        purchase_quotation_id=quotation.id,
        created_by_id=graph.user.id,
        order_date=datetime.now(UTC),
        currency=graph.currency.code,
        payment_terms="30 días",
        status=status,
        details=(
            PurchaseOrderDetail(
                id=uuid.uuid4(),
                purchase_order_id=order_id,
                product_id=graph.product.id_product,
                quantity=quantity,
                unit_id=graph.unit.id_unit,
                unit_price=Decimal("10"),
                subtotal=subtotal,
                total=subtotal,
            ),
        ),
        subtotal=subtotal,
        total=subtotal,
    )


@pytest.mark.asyncio
async def test_repository_persists_tenant_scoped_order_and_resolves_references(
    order_session: AsyncSession,
) -> None:
    graph = await _build_graph(order_session)
    request = await _persist_request(order_session, graph, quantity=Decimal("4"))
    quotation = await _persist_selected_quotation(order_session, graph, (request,))
    repository = SqlAlchemyPurchaseOrderRepository(order_session)
    order = await _build_order(repository, graph, quotation, quantity=Decimal("2"))

    saved = await repository.add_order(order)
    loaded = await repository.get_order(graph.company.id, saved.id)
    hidden = await repository.get_order(uuid.uuid4(), saved.id)
    quotation_reference = await repository.get_quotation_reference_for_update(
        graph.company.id,
        quotation.id,
    )
    destination = await repository.get_destination_reference(
        graph.company.id,
        graph.branch.id,
        graph.warehouse.id,
    )

    assert loaded is not None
    assert loaded.code == saved.code
    assert hidden is None
    assert quotation_reference is not None
    assert quotation_reference.status is PurchaseQuotationStatus.SELECTED
    assert quotation_reference.details[0].id == quotation.details[0].id
    assert destination is not None
    assert destination.warehouse_storage_eligible
    assert (
        await repository.get_destination_reference(
            uuid.uuid4(),
            graph.branch.id,
            graph.warehouse.id,
        )
        is None
    )
    assert await repository.is_expense_type_active(
        graph.company.id,
        graph.expense_type.id,
    )
    assert not await repository.is_expense_type_active(
        uuid.uuid4(),
        graph.expense_type.id,
    )
    assert await repository.allocate_next_code(graph.company.id) == "OC-00002"


@pytest.mark.asyncio
async def test_repository_replaces_draft_and_tracks_reserved_quantities(
    order_session: AsyncSession,
) -> None:
    graph = await _build_graph(order_session)
    request = await _persist_request(order_session, graph, quantity=Decimal("6"))
    quotation = await _persist_selected_quotation(order_session, graph, (request,))
    repository = SqlAlchemyPurchaseOrderRepository(order_session)
    first = await repository.add_order(
        await _build_order(repository, graph, quotation, quantity=Decimal("1"))
    )
    second = await repository.add_order(
        await _build_order(repository, graph, quotation, quantity=Decimal("2"))
    )

    detail_id = quotation.details[0].id
    quantities = await repository.get_ordered_quantities(graph.company.id, quotation.id)
    assert quantities[detail_id] == Decimal("3")
    assert (
        await repository.get_ordered_quantities(
            graph.company.id,
            quotation.id,
            exclude_order_id=second.id,
        )
    )[detail_id] == Decimal("1")

    replacement_detail = replace(
        second.details[0],
        quantity=Decimal("3"),
        subtotal=Decimal("30"),
        total=Decimal("30"),
    )
    replacement = replace(
        second,
        details=(replacement_detail,),
        subtotal=Decimal("30"),
        total=Decimal("30"),
        notes="Actualizada",
    )
    updated = await repository.replace_draft(replacement)
    assert updated is not None
    assert updated.details[0].quantity == Decimal("3")
    assert updated.notes == "Actualizada"
    quantities = await repository.get_ordered_quantities(graph.company.id, quotation.id)
    assert quantities[detail_id] == Decimal("4")

    cancelled = await repository.update_status(
        graph.company.id,
        first.id,
        PurchaseOrderStatus.CANCELLED,
    )
    assert cancelled is not None
    quantities = await repository.get_ordered_quantities(graph.company.id, quotation.id)
    assert quantities[detail_id] == Decimal("3")


@pytest.mark.asyncio
async def test_repository_advances_single_request_from_partial_to_completed(
    order_session: AsyncSession,
) -> None:
    graph = await _build_graph(order_session)
    request = await _persist_request(order_session, graph, quantity=Decimal("4"))
    quotation = await _persist_selected_quotation(order_session, graph, (request,))
    order_repository = SqlAlchemyPurchaseOrderRepository(order_session)
    request_repository = SqlAlchemyPurchaseRequestRepository(order_session)

    first = await _build_order(
        order_repository,
        graph,
        quotation,
        quantity=Decimal("2"),
        status=PurchaseOrderStatus.SENT,
    )
    await order_repository.add_order(first)
    await order_repository.advance_purchase_request_order_statuses(
        graph.company.id,
        quotation.id,
    )
    partial = await request_repository.get_request(graph.company.id, request.id)

    second = await _build_order(
        order_repository,
        graph,
        quotation,
        quantity=Decimal("2"),
        status=PurchaseOrderStatus.SENT,
    )
    await order_repository.add_order(second)
    await order_repository.advance_purchase_request_order_statuses(
        graph.company.id,
        quotation.id,
    )
    completed = await request_repository.get_request(graph.company.id, request.id)

    assert partial is not None
    assert partial.status is PurchaseRequestStatus.PARTIALLY_ORDERED
    assert completed is not None
    assert completed.status is PurchaseRequestStatus.COMPLETED


@pytest.mark.asyncio
async def test_consolidated_partial_order_does_not_guess_request_allocation(
    order_session: AsyncSession,
) -> None:
    graph = await _build_graph(order_session)
    first_request = await _persist_request(order_session, graph, quantity=Decimal("2"))
    second_request = await _persist_request(order_session, graph, quantity=Decimal("2"))
    quotation = await _persist_selected_quotation(
        order_session,
        graph,
        (first_request, second_request),
    )
    order_repository = SqlAlchemyPurchaseOrderRepository(order_session)
    request_repository = SqlAlchemyPurchaseRequestRepository(order_session)

    partial_order = await _build_order(
        order_repository,
        graph,
        quotation,
        quantity=Decimal("2"),
        status=PurchaseOrderStatus.SENT,
    )
    await order_repository.add_order(partial_order)
    await order_repository.advance_purchase_request_order_statuses(
        graph.company.id,
        quotation.id,
    )
    first_after_partial = await request_repository.get_request(
        graph.company.id,
        first_request.id,
    )
    second_after_partial = await request_repository.get_request(
        graph.company.id,
        second_request.id,
    )

    assert first_after_partial is not None
    assert second_after_partial is not None
    assert first_after_partial.status is PurchaseRequestStatus.QUOTED
    assert second_after_partial.status is PurchaseRequestStatus.QUOTED

    remainder = await _build_order(
        order_repository,
        graph,
        quotation,
        quantity=Decimal("2"),
        status=PurchaseOrderStatus.SENT,
    )
    await order_repository.add_order(remainder)
    await order_repository.advance_purchase_request_order_statuses(
        graph.company.id,
        quotation.id,
    )
    first_completed = await request_repository.get_request(
        graph.company.id,
        first_request.id,
    )
    second_completed = await request_repository.get_request(
        graph.company.id,
        second_request.id,
    )

    assert first_completed is not None
    assert second_completed is not None
    assert first_completed.status is PurchaseRequestStatus.COMPLETED
    assert second_completed.status is PurchaseRequestStatus.COMPLETED


@pytest.mark.asyncio
async def test_expense_document_repository_is_tenant_scoped_and_marks_upload(
    order_session: AsyncSession,
) -> None:
    graph = await _build_graph(order_session)
    request = await _persist_request(order_session, graph, quantity=Decimal("2"))
    quotation = await _persist_selected_quotation(order_session, graph, (request,))
    order_repository = SqlAlchemyPurchaseOrderRepository(order_session)

    base_order = await _build_order(
        order_repository,
        graph,
        quotation,
        quantity=Decimal("2"),
        status=PurchaseOrderStatus.PENDING_APPROVAL,
    )
    expense_id = uuid.uuid4()
    order = replace(
        base_order,
        expenses=(
            PurchaseOrderExpense(
                id=expense_id,
                purchase_order_id=base_order.id,
                expense_type_id=graph.expense_type.id,
                amount=Decimal("5"),
                description="Flete",
            ),
        ),
        additional_expenses=Decimal("5"),
        total=base_order.total + Decimal("5"),
    )
    saved = await order_repository.add_order(order)

    document_id = uuid.uuid4()
    order_session.add(
        DocumentAssetModel(
            id=document_id,
            company_id=graph.company.id,
            original_filename="flete.pdf",
            extension=".pdf",
            declared_content_type="application/pdf",
            size_bytes=128,
            checksum_sha256="b" * 64,
            bucket="erp-documents",
            object_key=f"purchase-orders/{document_id}",
            status="pending_upload",
            upload_expires_at=datetime.now(UTC),
            uploaded_by=graph.user.id,
        )
    )
    await order_session.flush()

    repository = SqlAlchemyPurchaseOrderExpenseDocumentRepository(order_session)
    reference = await repository.get_expense_reference(
        graph.company.id,
        saved.id,
        expense_id,
    )
    assert reference is not None
    assert reference.status is PurchaseOrderStatus.PENDING_APPROVAL
    assert (
        await repository.get_expense_reference(
            uuid.uuid4(),
            saved.id,
            expense_id,
        )
        is None
    )

    attachment = await repository.add_document(
        PurchaseOrderExpenseDocument(
            id=uuid.uuid4(),
            company_id=graph.company.id,
            purchase_order_expense_id=expense_id,
            document_id=document_id,
            file_name="flete.pdf",
            file_type="application/pdf",
        )
    )
    loaded = await repository.get_document(
        graph.company.id,
        saved.id,
        expense_id,
        document_id,
    )
    assert loaded == attachment
    assert (
        await repository.get_document(
            uuid.uuid4(),
            saved.id,
            expense_id,
            document_id,
        )
        is None
    )

    listed = await repository.list_documents(
        graph.company.id,
        saved.id,
        expense_id,
    )
    assert [item.document_id for item in listed] == [document_id]

    uploaded_at = datetime.now(UTC)
    marked = await repository.mark_uploaded(
        graph.company.id,
        saved.id,
        expense_id,
        document_id,
        file_type="application/pdf",
        uploaded_at=uploaded_at,
    )
    assert marked is not None
    assert marked.uploaded_at == uploaded_at
