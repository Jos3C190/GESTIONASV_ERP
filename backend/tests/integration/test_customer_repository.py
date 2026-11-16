"""Clientes con identidad fiscal contra PostgreSQL: unicidades, genérico, entregas y aislamiento."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from decimal import Decimal

import pytest
from app.application.customers import CustomerUseCases
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.customer import (
    CustomerDraft,
    CustomerType,
    DeliveryAddressDraft,
    Geography,
    IdentityDocument,
)
from app.domain.entities.fiscal import PersonType, TaxpayerCategory
from app.domain.ports.customer_repository import CustomerFilters
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
    UserCompany,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.customer_repository import SqlAlchemyCustomerRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class Context:
    company_id: uuid.UUID
    branch_id: uuid.UUID
    actor_id: uuid.UUID
    geography: Geography


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as db:
        transaction = await db.begin()
        try:
            yield db
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


async def _san_miguel(db: AsyncSession) -> Geography:
    row = (
        await db.execute(
            select(GeographicDepartment.id, Municipality.id, District.id)
            .join(Municipality, Municipality.department_id == GeographicDepartment.id)
            .join(District, District.municipality_id == Municipality.id)
            .where(
                GeographicDepartment.name == "San Miguel",
                Municipality.name == "San Miguel Centro",
                District.name == "San Miguel",
            )
        )
    ).one()
    return Geography(row[0], row[1], row[2])


async def _context(db: AsyncSession, actor: User | None = None) -> Context:
    geography = await _san_miguel(db)
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        id=uuid.uuid4(),
        name=f"Clientes {suffix}, S.A. de C.V.",
        commercial_name=f"Clientes {suffix}",
        nit=f"{uuid.uuid4().int % 10**14:014d}",
        nrc=f"{uuid.uuid4().int % 10**6:06d}",
        address="San Miguel",
        department_id=geography.department_id,
        municipality_id=geography.municipality_id,
        district_id=geography.district_id,
        is_active=True,
    )
    db.add(company)
    await db.flush()
    if actor is None:
        actor = User(
            username=f"clientes-{suffix}",
            email=f"clientes-{suffix}@example.test",
            password_hash="integration-test-only",
            is_active=True,
            is_superuser=True,
        )
        db.add(actor)
        await db.flush()
        db.add(
            Employee(
                company_id=company.id,
                user_id=actor.id,
                employee_code=f"CLI-{suffix[:8].upper()}",
                first_name="Clientes",
                last_name="Prueba",
                status="activo",
            )
        )
    db.add(UserCompany(user_id=actor.id, company_id=company.id))
    branch = Branch(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Tienda {suffix}",
        code=f"T{suffix[:6]}",
        address="San Miguel",
        department_id=geography.department_id,
        municipality_id=geography.municipality_id,
        district_id=geography.district_id,
        operational_status="active",
    )
    db.add(branch)
    await db.flush()
    return Context(company.id, branch.id, actor.id, geography)


def _taxpayer(geography: Geography, **changes: object) -> CustomerDraft:
    draft = CustomerDraft(
        customer_type=CustomerType.TAXPAYER,
        name="Cafetería El Trigal, S.A. de C.V.",
        person_type=PersonType.LEGAL,
        taxpayer_category=TaxpayerCategory.OTHER,
        document_type=IdentityDocument.NIT,
        document_number="0614-010101-101-1",
        nrc="123456-7",
        activity_code="56101",
        geography=geography,
        address_line="Avenida Roosevelt 12",
        email="compras@trigal.example",
    )
    return replace(draft, **changes)  # type: ignore[arg-type]


@pytest.fixture
def use_cases(session: AsyncSession) -> CustomerUseCases:
    return CustomerUseCases(SqlAlchemyCustomerRepository(session))


async def test_taxpayer_is_stored_normalized_and_can_receive_tax_credit(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    customer = await use_cases.create_customer(
        ctx.company_id, _taxpayer(ctx.geography), ctx.actor_id
    )
    assert customer.code == "CLI-00001"
    assert customer.draft.document_number == "06140101011011"
    assert customer.address.department_code == "12"
    assert customer.address.district_code == "17"
    assert customer.activity_name is not None
    assert customer.receivable_documents == ["01", "03"]
    second = await use_cases.create_customer(
        ctx.company_id,
        CustomerDraft(CustomerType.FINAL_CONSUMER, "Ana López"),
        ctx.actor_id,
    )
    assert second.code == "CLI-00002"
    assert second.receivable_documents == ["01"]


async def test_duplicates_and_catalog_checks(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    await use_cases.create_customer(ctx.company_id, _taxpayer(ctx.geography), ctx.actor_id)
    with pytest.raises(ConflictError) as document:
        await use_cases.create_customer(
            ctx.company_id, _taxpayer(ctx.geography, nrc="7654321"), ctx.actor_id
        )
    assert document.value.code == "customer_document_duplicate"
    with pytest.raises(ConflictError) as nrc:
        await use_cases.create_customer(
            ctx.company_id,
            _taxpayer(ctx.geography, document_number="0614-020202-102-2"),
            ctx.actor_id,
        )
    assert nrc.value.code == "customer_nrc_duplicate"
    with pytest.raises(BusinessRuleError) as activity:
        await use_cases.create_customer(
            ctx.company_id,
            _taxpayer(
                ctx.geography,
                document_number="0614-030303-103-3",
                nrc="1111111",
                activity_code="99999",
            ),
            ctx.actor_id,
        )
    assert activity.value.code == "customer_activity_unknown"
    with pytest.raises(BusinessRuleError) as country:
        await use_cases.create_customer(
            ctx.company_id,
            CustomerDraft(CustomerType.FOREIGN, "Cliente", country_code="ZZ"),
            ctx.actor_id,
        )
    assert country.value.code == "customer_country_unknown"
    mixed = Geography(ctx.geography.department_id, ctx.geography.municipality_id, uuid.uuid4())
    with pytest.raises(BusinessRuleError) as geography:
        await use_cases.create_customer(
            ctx.company_id,
            CustomerDraft(CustomerType.FINAL_CONSUMER, "Ana", geography=mixed),
            ctx.actor_id,
        )
    assert geography.value.code == "customer_geography_invalid"


async def test_generic_customer_is_unique_per_branch_and_locked(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    generic, created = await use_cases.generic_customer(ctx.company_id, ctx.branch_id, ctx.actor_id)
    assert created is True
    assert generic.draft.name == "Consumidor final"
    again, created_again = await use_cases.generic_customer(
        ctx.company_id, ctx.branch_id, ctx.actor_id
    )
    assert (again.id, created_again) == (generic.id, False)
    with pytest.raises(BusinessRuleError) as locked:
        await use_cases.set_active(ctx.company_id, generic.id, False, ctx.actor_id)
    assert locked.value.code == "customer_generic_locked"
    listed, total = await use_cases.list_customers(
        ctx.company_id, CustomerFilters(), page=1, size=20
    )
    assert total == 0
    assert listed == []
    with_generic, _ = await use_cases.list_customers(
        ctx.company_id, CustomerFilters(include_generic=True), page=1, size=20
    )
    assert [c.id for c in with_generic] == [generic.id]


async def test_delivery_addresses_keep_one_default(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    customer = await use_cases.create_customer(
        ctx.company_id, _taxpayer(ctx.geography), ctx.actor_id
    )
    first = await use_cases.save_delivery_address(
        ctx.company_id,
        customer.id,
        DeliveryAddressDraft(
            "Cafetería centro",
            "2.ª Calle Oriente 5",
            geography=ctx.geography,
            latitude=Decimal("13.4810"),
            longitude=Decimal("-88.1770"),
        ),
    )
    assert first.is_default is True  # la primera queda como principal
    assert first.address.district_code == "17"
    second = await use_cases.save_delivery_address(
        ctx.company_id,
        customer.id,
        DeliveryAddressDraft("Bodega", "Km 5 carretera", is_default=True),
    )
    reloaded = await use_cases.get_customer(ctx.company_id, customer.id)
    defaults = [a.id for a in reloaded.delivery_addresses if a.is_default]
    assert defaults == [second.id]
    await use_cases.delete_delivery_address(ctx.company_id, customer.id, first.id)
    with pytest.raises(NotFoundError):
        await use_cases.delete_delivery_address(ctx.company_id, customer.id, first.id)


async def test_search_filters_and_updates(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    taxpayer = await use_cases.create_customer(
        ctx.company_id, _taxpayer(ctx.geography), ctx.actor_id
    )
    await use_cases.create_customer(
        ctx.company_id, CustomerDraft(CustomerType.FINAL_CONSUMER, "Ana López"), ctx.actor_id
    )
    by_nit, _ = await use_cases.list_customers(
        ctx.company_id, CustomerFilters(search="0614-010101"), page=1, size=20
    )
    assert [c.id for c in by_nit] == [taxpayer.id]
    taxpayers, total = await use_cases.list_customers(
        ctx.company_id, CustomerFilters(customer_type=CustomerType.TAXPAYER), page=1, size=20
    )
    assert total == 1
    updated = await use_cases.update_customer(
        ctx.company_id,
        taxpayer.id,
        _taxpayer(ctx.geography, nrc=None, credit_days=30),
        ctx.actor_id,
    )
    assert updated.draft.credit_days == 30
    assert "NRC." in updated.tax_credit_missing
    inactive = await use_cases.set_active(ctx.company_id, taxpayer.id, False, ctx.actor_id)
    assert inactive.is_active is False


async def test_companies_never_see_each_other(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    first = await _context(session)
    second = await _context(session)
    customer = await use_cases.create_customer(
        first.company_id, _taxpayer(first.geography), first.actor_id
    )
    with pytest.raises(NotFoundError):
        await use_cases.get_customer(second.company_id, customer.id)
    listed, total = await use_cases.list_customers(
        second.company_id, CustomerFilters(), page=1, size=20
    )
    assert (listed, total) == ([], 0)
    with pytest.raises(NotFoundError):
        await use_cases.generic_customer(second.company_id, first.branch_id, second.actor_id)
    # El mismo NIT y NRC pueden existir como cliente en otra empresa.
    other = await use_cases.create_customer(
        second.company_id, _taxpayer(second.geography), second.actor_id
    )
    assert other.code == "CLI-00001"


async def _employee(session: AsyncSession, company_id: uuid.UUID, first: str) -> uuid.UUID:
    employee = Employee(
        company_id=company_id,
        employee_code=f"VEN-{uuid.uuid4().hex[:6].upper()}",
        first_name=first,
        last_name="Vendedora",
        position="Ventas de mayoreo",
        status="activo",
    )
    session.add(employee)
    await session.flush()
    return employee.id


async def test_seller_options_and_assignment_stay_in_the_company(
    session: AsyncSession, use_cases: CustomerUseCases
) -> None:
    ctx = await _context(session)
    other = await _context(session)
    seller = await _employee(session, ctx.company_id, "Rosa")
    foreign_seller = await _employee(session, other.company_id, "Rosa")
    options = await use_cases.seller_options(ctx.company_id, search="rosa")
    assert [o.id for o in options] == [seller]
    assert options[0].name == "Rosa Vendedora"
    customer = await use_cases.create_customer(
        ctx.company_id,
        _taxpayer(ctx.geography, seller_employee_id=seller),
        ctx.actor_id,
    )
    assert customer.seller_name == "Rosa Vendedora"
    with pytest.raises(NotFoundError) as foreign:
        await use_cases.update_customer(
            ctx.company_id,
            customer.id,
            _taxpayer(ctx.geography, seller_employee_id=foreign_seller),
            ctx.actor_id,
        )
    assert foreign.value.code == "customer_seller_not_found"
