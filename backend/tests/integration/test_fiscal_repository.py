"""Base fiscal del emisor contra PostgreSQL: reglas, unicidades y aislamiento entre empresas."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from app.application.fiscal import FiscalSettingsUseCases
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.fiscal import (
    CertificationStatus,
    EstablishmentType,
    OperatingMode,
    PersonType,
    TaxpayerCategory,
)
from app.domain.ports.fiscal_repository import ProfileValues
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fiscal_repository import SqlAlchemyFiscalRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

BAKERY = "10712"  # Fabricación de pan, galletas y barquillos
RETAIL = "47215"  # Venta al por menor de productos de panadería


@dataclass(frozen=True, slots=True)
class Issuer:
    company_id: uuid.UUID
    branch_id: uuid.UUID
    second_branch_id: uuid.UUID


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


async def _san_salvador(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    row = (
        await db.execute(
            select(GeographicDepartment.id, Municipality.id, District.id)
            .join(Municipality, Municipality.department_id == GeographicDepartment.id)
            .join(District, District.municipality_id == Municipality.id)
            .where(
                GeographicDepartment.name == "San Salvador",
                Municipality.name == "San Salvador Centro",
                District.name == "San Salvador",
            )
        )
    ).one()
    return row[0], row[1], row[2]


async def _issuer(db: AsyncSession, actor: uuid.UUID, label: str) -> Issuer:
    department, municipality, district = await _san_salvador(db)
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        id=uuid.uuid4(),
        name=f"{label} {suffix}, S.A. de C.V.",
        commercial_name=f"{label} {suffix}",
        nit=f"{uuid.uuid4().int % 10**14:014d}",
        nrc=f"{uuid.uuid4().int % 10**6:06d}",
        address="Colonia Escalón",
        department_id=department,
        municipality_id=municipality,
        district_id=district,
        is_active=True,
    )
    db.add(company)
    await db.flush()
    has_employee = await db.scalar(select(Employee.id).where(Employee.user_id == actor))
    if has_employee is None:
        db.add(
            Employee(
                company_id=company.id,
                user_id=actor,
                employee_code=f"FIS-{suffix[:8].upper()}",
                first_name="Fiscal",
                last_name="Test",
                status="activo",
            )
        )
    branches = []
    for index in range(2):
        branch = Branch(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Tienda {index} {suffix}",
            code=f"T{index}{suffix[:6]}",
            address=f"Calle {index}, San Salvador",
            department_id=department,
            municipality_id=municipality,
            district_id=district,
            operational_status="active",
        )
        db.add(branch)
        branches.append(branch.id)
    await db.flush()
    return Issuer(company.id, branches[0], branches[1])


@pytest.fixture
async def actor(session: AsyncSession) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        username=f"fiscal-{suffix}",
        email=f"fiscal-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
        is_superuser=True,
    )
    session.add(user)
    await session.flush()
    return user.id


@pytest.fixture
def use_cases(session: AsyncSession) -> FiscalSettingsUseCases:
    return FiscalSettingsUseCases(SqlAlchemyFiscalRepository(session))


async def test_profile_defaults_then_saved(
    session: AsyncSession, actor: uuid.UUID, use_cases: FiscalSettingsUseCases
) -> None:
    issuer = await _issuer(session, actor, "Perfil")
    profile = await use_cases.get_profile(issuer.company_id)
    assert profile.configured is False
    assert profile.operating_mode == OperatingMode.SIMULATED
    saved = await use_cases.update_profile(
        issuer.company_id,
        ProfileValues(
            TaxpayerCategory.MEDIUM, PersonType.LEGAL, OperatingMode.TEST, "dte@x.test", None
        ),
        actor,
    )
    assert saved.configured is True
    assert saved.operating_mode == OperatingMode.TEST
    assert saved.dte_email == "dte@x.test"


async def test_catalog_search_ignores_accents(use_cases: FiscalSettingsUseCases) -> None:
    found = await use_cases.list_catalog("CAT-019", group_code=None, search="galletas", limit=50)
    assert any(item.code == BAKERY for item in found)
    districts = await use_cases.list_catalog("CAT-008", group_code="06", search=None, limit=500)
    assert len(districts) == 19
    with pytest.raises(NotFoundError):
        await use_cases.list_catalog("CAT-099", group_code=None, search=None, limit=10)


async def test_activities_primary_duplicates_and_unknown_codes(
    session: AsyncSession, actor: uuid.UUID, use_cases: FiscalSettingsUseCases
) -> None:
    issuer = await _issuer(session, actor, "Actividades")
    first = await use_cases.add_activity(
        issuer.company_id, BAKERY, is_primary=False, actor_id=actor
    )
    assert first.is_primary is True  # la primera siempre es la principal
    assert first.description == "Fabricación de pan, galletas y barquillos"
    second = await use_cases.add_activity(
        issuer.company_id, RETAIL, is_primary=True, actor_id=actor
    )
    activities = await use_cases.list_activities(issuer.company_id)
    assert [a.code for a in activities if a.is_primary] == [RETAIL]
    with pytest.raises(ConflictError) as duplicate:
        await use_cases.add_activity(issuer.company_id, BAKERY, is_primary=False, actor_id=actor)
    assert duplicate.value.code == "fiscal_activity_duplicate"
    with pytest.raises(BusinessRuleError) as unknown:
        await use_cases.add_activity(issuer.company_id, "99999", is_primary=False, actor_id=actor)
    assert unknown.value.code == "fiscal_activity_unknown"

    await use_cases.create_establishment(
        issuer.company_id,
        branch_id=issuer.branch_id,
        establishment_type=EstablishmentType.HEADQUARTERS,
        code="M001",
        activity_id=second.id,
        actor_id=actor,
    )
    with pytest.raises(ConflictError) as in_use:
        await use_cases.delete_activity(issuer.company_id, second.id)
    assert in_use.value.code == "fiscal_activity_in_use"
    await use_cases.delete_activity(issuer.company_id, first.id)


async def test_establishments_points_of_sale_and_address_codes(
    session: AsyncSession, actor: uuid.UUID, use_cases: FiscalSettingsUseCases
) -> None:
    issuer = await _issuer(session, actor, "Establecimientos")
    main = await use_cases.create_establishment(
        issuer.company_id,
        branch_id=issuer.branch_id,
        establishment_type=EstablishmentType.HEADQUARTERS,
        code="m001",
        activity_id=None,
        actor_id=actor,
    )
    assert main.code == "M001"
    assert (main.address.department_code, main.address.municipality_code) == ("06", "23")
    assert main.address.district_code == "14"
    assert main.address.complete is True

    with pytest.raises(ConflictError) as same_branch:
        await use_cases.create_establishment(
            issuer.company_id,
            branch_id=issuer.branch_id,
            establishment_type=EstablishmentType.BRANCH,
            code="S001",
            activity_id=None,
            actor_id=actor,
        )
    assert same_branch.value.code == "fiscal_branch_already_establishment"
    with pytest.raises(ConflictError) as same_code:
        await use_cases.create_establishment(
            issuer.company_id,
            branch_id=issuer.second_branch_id,
            establishment_type=EstablishmentType.HEADQUARTERS,
            code="M001",
            activity_id=None,
            actor_id=actor,
        )
    assert same_code.value.code == "fiscal_establishment_code_duplicate"
    with pytest.raises(BusinessRuleError):
        await use_cases.create_establishment(
            issuer.company_id,
            branch_id=issuer.second_branch_id,
            establishment_type=EstablishmentType.BRANCH,
            code="M002",
            activity_id=None,
            actor_id=actor,
        )
    store = await use_cases.create_establishment(
        issuer.company_id,
        branch_id=issuer.second_branch_id,
        establishment_type=EstablishmentType.BRANCH,
        code="S001",
        activity_id=None,
        actor_id=actor,
    )

    pos = await use_cases.create_point_of_sale(
        issuer.company_id, main.id, code="p001", name="Caja 1", actor_id=actor
    )
    assert pos.code == "P001"
    # El mismo código en otro establecimiento es válido: el número de control los distingue.
    await use_cases.create_point_of_sale(
        issuer.company_id, store.id, code="P001", name="Caja 1", actor_id=actor
    )
    with pytest.raises(ConflictError) as duplicate:
        await use_cases.create_point_of_sale(
            issuer.company_id, main.id, code="P001", name="Otra", actor_id=actor
        )
    assert duplicate.value.code == "fiscal_point_of_sale_code_duplicate"
    renamed = await use_cases.update_point_of_sale(
        issuer.company_id,
        pos.id,
        code="P002",
        name="Caja principal",
        is_active=True,
        actor_id=actor,
    )
    assert (renamed.code, renamed.name) == ("P002", "Caja principal")
    listed = await use_cases.list_establishments(issuer.company_id)
    assert [e.code for e in listed] == ["M001", "S001"]
    assert [p.code for p in listed[0].points_of_sale] == ["P002"]


async def _make_ready(
    use_cases: FiscalSettingsUseCases, issuer: Issuer, actor: uuid.UUID
) -> uuid.UUID:
    await use_cases.add_activity(issuer.company_id, BAKERY, is_primary=True, actor_id=actor)
    est = await use_cases.create_establishment(
        issuer.company_id,
        branch_id=issuer.branch_id,
        establishment_type=EstablishmentType.HEADQUARTERS,
        code="M001",
        activity_id=None,
        actor_id=actor,
    )
    await use_cases.create_point_of_sale(
        issuer.company_id, est.id, code="P001", name="Caja 1", actor_id=actor
    )
    return est.id


async def test_production_needs_a_ready_issuer_and_stays_ready(
    session: AsyncSession, actor: uuid.UUID, use_cases: FiscalSettingsUseCases
) -> None:
    issuer = await _issuer(session, actor, "Produccion")
    documents = await use_cases.list_document_types(issuer.company_id)
    assert len(documents) == 13
    assert not any(d.is_enabled for d in documents)
    production = ProfileValues(
        TaxpayerCategory.OTHER, PersonType.LEGAL, OperatingMode.PRODUCTION, None, None
    )
    with pytest.raises(BusinessRuleError) as not_ready:
        await use_cases.update_profile(issuer.company_id, production, actor)
    assert not_ready.value.code == "fiscal_production_not_ready"
    assert "NIT" not in not_ready.value.message  # el NIT y el NRC de la prueba son válidos

    establishment_id = await _make_ready(use_cases, issuer, actor)
    # En simulado se habilita sin certificar; para producción hay que aprobar las pruebas.
    await use_cases.update_document_type(
        issuer.company_id,
        "01",
        is_enabled=True,
        certification_status=CertificationStatus.PENDING,
        notes=None,
        actor_id=actor,
    )
    with pytest.raises(BusinessRuleError):
        await use_cases.update_profile(issuer.company_id, production, actor)
    approved = await use_cases.update_document_type(
        issuer.company_id,
        "01",
        is_enabled=True,
        certification_status=CertificationStatus.APPROVED,
        notes="Pruebas aprobadas",
        actor_id=actor,
    )
    assert approved.certified_at is not None
    assert (
        await use_cases.update_profile(issuer.company_id, production, actor)
    ).operating_mode == (OperatingMode.PRODUCTION)
    assert await use_cases.production_blockers(issuer.company_id) == []

    with pytest.raises(BusinessRuleError) as uncertified:
        await use_cases.update_document_type(
            issuer.company_id,
            "03",
            is_enabled=True,
            certification_status=CertificationStatus.IN_PROGRESS,
            notes=None,
            actor_id=actor,
        )
    assert uncertified.value.code == "fiscal_document_not_certified"
    with pytest.raises(BusinessRuleError) as breaks:
        await use_cases.update_document_type(
            issuer.company_id,
            "01",
            is_enabled=False,
            certification_status=CertificationStatus.APPROVED,
            notes=None,
            actor_id=actor,
        )
    assert breaks.value.code == "fiscal_production_would_break"
    with pytest.raises(BusinessRuleError):
        await use_cases.update_establishment(
            issuer.company_id,
            establishment_id,
            establishment_type=EstablishmentType.HEADQUARTERS,
            code="M001",
            activity_id=None,
            is_active=False,
            actor_id=actor,
        )


async def test_companies_never_see_each_other(
    session: AsyncSession, actor: uuid.UUID, use_cases: FiscalSettingsUseCases
) -> None:
    first = await _issuer(session, actor, "Empresa A")
    second = await _issuer(session, actor, "Empresa B")
    establishment_id = await _make_ready(use_cases, first, actor)
    activity = (await use_cases.list_activities(first.company_id))[0]
    point = (await use_cases.list_establishments(first.company_id))[0].points_of_sale[0]

    assert await use_cases.list_activities(second.company_id) == []
    assert await use_cases.list_establishments(second.company_id) == []
    with pytest.raises(NotFoundError):
        await use_cases.get_establishment(second.company_id, establishment_id)
    with pytest.raises(NotFoundError):
        await use_cases.set_primary_activity(second.company_id, activity.id)
    with pytest.raises(NotFoundError):
        await use_cases.get_point_of_sale(second.company_id, point.id)
    with pytest.raises(NotFoundError) as foreign_branch:
        await use_cases.create_establishment(
            second.company_id,
            branch_id=first.second_branch_id,
            establishment_type=EstablishmentType.BRANCH,
            code="S001",
            activity_id=None,
            actor_id=actor,
        )
    assert foreign_branch.value.code == "fiscal_branch_not_found"
    with pytest.raises(NotFoundError):
        await use_cases.create_establishment(
            second.company_id,
            branch_id=second.branch_id,
            establishment_type=EstablishmentType.HEADQUARTERS,
            code="M001",
            activity_id=activity.id,
            actor_id=actor,
        )
    # Mismos códigos en otra empresa: cada emisor numera por su cuenta.
    await _make_ready(use_cases, second, actor)
