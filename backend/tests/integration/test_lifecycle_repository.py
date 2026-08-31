"""PostgreSQL integration tests for the enterprise record lifecycle.

The suite uses a transaction per test and always rolls it back.  It therefore
exercises the real schema, partial indexes and global ORM visibility rule
without leaving test records in the developer database.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest
from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.employee import (
    Department,
    DepartmentBranchAssignment,
    Employee,
)
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
    UserCompany,
    WarehouseCategory,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.document_repository import SqlAlchemyDocumentRepository
from app.infrastructure.repositories.lifecycle_repository import (
    SqlAlchemyLifecycleRepository,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
async def lifecycle_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


async def _add_geography(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    suffix = _suffix()
    department = GeographicDepartment(id=uuid.uuid4(), name=f"Pruebas {suffix}")
    municipality = Municipality(
        id=uuid.uuid4(),
        department_id=department.id,
        name=f"Municipio {suffix}",
    )
    district = District(
        id=uuid.uuid4(),
        municipality_id=municipality.id,
        name=f"Distrito {suffix}",
    )
    session.add(department)
    await session.flush()
    session.add(municipality)
    await session.flush()
    session.add(district)
    await session.flush()
    return department.id, municipality.id, district.id


async def _add_company(session: AsyncSession, *, label: str) -> Company:
    department_id, municipality_id, district_id = await _add_geography(session)
    suffix = _suffix()
    company = Company(
        id=uuid.uuid4(),
        name=f"Empresa {label} {suffix}, S.A. de C.V.",
        commercial_name=f"Empresa {label} {suffix}",
        nit=f"TST-{suffix}-NIT",
        nrc=f"TST-{suffix}-NRC",
        address="San Salvador, El Salvador",
        department_id=department_id,
        municipality_id=municipality_id,
        district_id=district_id,
        is_active=True,
    )
    session.add(company)
    await session.flush()
    return company


async def _add_user(
    session: AsyncSession,
    *,
    username: str,
    is_superuser: bool = False,
) -> User:
    suffix = _suffix()
    user = User(
        id=uuid.uuid4(),
        username=f"{username}_{suffix}",
        email=f"{username}.{suffix}@example.test",
        password_hash="not-a-real-password-hash",
        is_active=True,
        is_superuser=is_superuser,
    )
    session.add(user)
    await session.flush()
    return user


async def test_tenant_isolation_visibility_restore_and_idempotency(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="auditor")
    company_a = await _add_company(session, label="A")
    company_b = await _add_company(session, label="B")
    department = Department(
        id=uuid.uuid4(),
        company_id=company_a.id,
        name=f"Operaciones {_suffix()}",
    )
    session.add(department)
    await session.flush()
    repository = SqlAlchemyLifecycleRepository(session)

    with pytest.raises(NotFoundError) as wrong_delete:
        await repository.soft_delete(
            "departments",
            str(department.id),
            company_id=company_b.id,
            actor_id=actor.id,
            reason="Registro duplicado",
        )
    assert wrong_delete.value.code == "lifecycle_record_not_found"

    deleted = await repository.soft_delete(
        "departments",
        str(department.id),
        company_id=company_a.id,
        actor_id=actor.id,
        reason="Registro duplicado",
    )
    repeated_delete = await repository.soft_delete(
        "departments",
        str(department.id),
        company_id=company_a.id,
        actor_id=actor.id,
        reason="Segundo intento",
    )

    assert deleted.operation_applied is True
    assert repeated_delete.operation_applied is False
    assert repeated_delete.deletion_reason == "Registro duplicado"
    assert await session.scalar(select(Department).where(Department.id == department.id)) is None
    recoverable = await session.scalar(
        select(Department)
        .where(Department.id == department.id)
        .execution_options(include_deleted=True)
    )
    assert recoverable is not None

    company_a_items, company_a_total = await repository.list_deleted(
        company_a.id,
        page=1,
        size=20,
        resource="departments",
    )
    company_b_items, company_b_total = await repository.list_deleted(
        company_b.id,
        page=1,
        size=20,
        resource="departments",
    )
    assert company_a_total == 1
    assert company_a_items[0].record_id == str(department.id)
    assert company_b_total == 0
    assert company_b_items == []

    with pytest.raises(NotFoundError) as wrong_restore:
        await repository.restore(
            "departments",
            str(department.id),
            company_id=company_b.id,
            actor_id=actor.id,
        )
    assert wrong_restore.value.code == "lifecycle_record_not_found"

    restored = await repository.restore(
        "departments",
        str(department.id),
        company_id=company_a.id,
        actor_id=actor.id,
    )
    repeated_restore = await repository.restore(
        "departments",
        str(department.id),
        company_id=company_a.id,
        actor_id=actor.id,
    )
    assert restored.operation_applied is True
    assert repeated_restore.operation_applied is False
    assert await session.scalar(select(Department).where(Department.id == department.id))


async def test_documents_are_paginated_tenant_scoped_and_restorable(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="document_manager")
    company_a = await _add_company(session, label="Documentos A")
    company_b = await _add_company(session, label="Documentos B")
    documents = [
        DocumentAssetModel(
            id=uuid.uuid4(),
            company_id=company_a.id,
            original_filename=f"contrato-{index}.pdf",
            extension=".pdf",
            declared_content_type="application/pdf",
            detected_content_type="application/pdf",
            size_bytes=100 + index,
            checksum_sha256=f"{index + 1:064x}",
            bucket="erp-documents",
            object_key=f"companies/{company_a.id}/documents/{uuid.uuid4()}",
            status="active",
            upload_expires_at=datetime.now(UTC) + timedelta(minutes=10),
            uploaded_by=actor.id,
        )
        for index in range(3)
    ]
    session.add_all(documents)
    await session.flush()
    repository = SqlAlchemyDocumentRepository(session)
    lifecycle = SqlAlchemyLifecycleRepository(session)

    first_page, total = await repository.list(
        company_a.id, page=1, size=2, search="contrato", status="active"
    )
    other_company, other_total = await repository.list(
        company_b.id, page=1, size=20, search=None, status=None
    )
    assert total == 3
    assert len(first_page) == 2
    assert other_company == []
    assert other_total == 0

    with pytest.raises(NotFoundError):
        await lifecycle.soft_delete(
            "documents",
            str(documents[0].id),
            company_id=company_b.id,
            actor_id=actor.id,
            reason="Cruce de empresa",
        )

    deleted = await lifecycle.soft_delete(
        "documents",
        str(documents[0].id),
        company_id=company_a.id,
        actor_id=actor.id,
        reason="Documento reemplazado",
    )
    assert deleted.operation_applied is True
    assert await repository.get(documents[0].id) is None
    trash, trash_total = await lifecycle.list_deleted(
        company_a.id, page=1, size=20, resource="documents"
    )
    assert trash_total == 1
    assert trash[0].record_id == str(documents[0].id)

    restored = await lifecycle.restore(
        "documents",
        str(documents[0].id),
        company_id=company_a.id,
        actor_id=actor.id,
    )
    assert restored.operation_applied is True
    assert await repository.get(documents[0].id) is not None


async def test_only_active_assignments_block_branch_deletion(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="auditor")
    company = await _add_company(session, label="Dependencias")
    department = Department(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Logística {_suffix()}",
    )
    branch = Branch(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Sucursal {_suffix()}",
        code=f"TST-{_suffix()[:8]}",
        address="San Salvador, El Salvador",
        department_id=company.department_id,
        municipality_id=company.municipality_id,
        district_id=company.district_id,
        is_active=True,
    )
    historical_assignment = DepartmentBranchAssignment(
        id=uuid.uuid4(),
        department_id=department.id,
        branch_id=branch.id,
        opened_at=date(2025, 1, 1),
        closed_at=date(2025, 12, 31),
        is_active=False,
    )
    session.add_all([department, branch])
    await session.flush()
    session.add(historical_assignment)
    await session.flush()
    repository = SqlAlchemyLifecycleRepository(session)

    deleted = await repository.soft_delete(
        "branches",
        str(branch.id),
        company_id=company.id,
        actor_id=actor.id,
        reason="Sucursal creada por error",
    )
    assert deleted.operation_applied is True
    await repository.restore(
        "branches",
        str(branch.id),
        company_id=company.id,
        actor_id=actor.id,
    )

    historical_assignment.is_active = True
    historical_assignment.closed_at = None
    await session.flush()

    with pytest.raises(ConflictError) as blocked:
        await repository.soft_delete(
            "branches",
            str(branch.id),
            company_id=company.id,
            actor_id=actor.id,
            reason="Sucursal creada por error",
        )
    assert blocked.value.code == "record_has_dependencies"
    assert "asignaciones de departamentos" in blocked.value.message


async def test_combined_trash_paginates_across_resources_in_database_bounded_batches(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="auditor")
    company = await _add_company(session, label="Paginación")
    departments = [
        Department(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Departamento {index} {_suffix()}",
        )
        for index in range(2)
    ]
    categories = [
        WarehouseCategory(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Categoría {index} {_suffix()}",
            is_active=True,
        )
        for index in range(2)
    ]
    session.add_all([*departments, *categories])
    await session.flush()
    repository = SqlAlchemyLifecycleRepository(session)
    deleted_records = []
    for resource, record in (
        ("departments", departments[0]),
        ("warehouse_categories", categories[0]),
        ("departments", departments[1]),
        ("warehouse_categories", categories[1]),
    ):
        deleted_records.append(
            await repository.soft_delete(
                resource,
                str(record.id),
                company_id=company.id,
                actor_id=actor.id,
                reason="Registro temporal",
            )
        )

    expected_ids = [
        item.record_id
        for item in sorted(
            deleted_records,
            key=lambda item: (item.deleted_at, item.resource, item.label),
            reverse=True,
        )
    ]
    page_one, total_one = await repository.list_deleted(company.id, page=1, size=2)
    page_two, total_two = await repository.list_deleted(company.id, page=2, size=2)

    assert total_one == total_two == 4
    assert [item.record_id for item in [*page_one, *page_two]] == expected_ids


async def test_deleting_user_revokes_sessions_and_restore_keeps_account_inactive(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="supervisor", is_superuser=True)
    target = await _add_user(session, username="colaborador")
    company_a = await _add_company(session, label="Sesiones A")
    company_b = await _add_company(session, label="Sesiones B")
    session.add_all(
        [
            UserCompany(
                user_id=target.id,
                company_id=company_a.id,
                is_default=True,
                access_all_branches=True,
            ),
            UserCompany(
                user_id=target.id,
                company_id=company_b.id,
                is_default=False,
                access_all_branches=True,
            ),
            Employee(
                id=uuid.uuid4(),
                company_id=company_a.id,
                user_id=target.id,
                employee_code=f"TST-{_suffix()[:10]}",
                first_name="María",
                last_name="López",
                status="activo",
            ),
        ]
    )
    now = datetime.now(UTC)
    refresh = RefreshToken(
        id=uuid.uuid4(),
        user_id=target.id,
        token_hash=f"refresh-{_suffix()}",
        expires_at=now + timedelta(days=1),
    )
    reset = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=target.id,
        token_hash=f"reset-{_suffix()}",
        expires_at=now + timedelta(hours=1),
    )
    session.add_all([refresh, reset])
    await session.flush()
    repository = SqlAlchemyLifecycleRepository(session)

    await repository.soft_delete(
        "users",
        str(target.id),
        company_id=company_a.id,
        actor_id=actor.id,
        reason="Cuenta duplicada",
        allow_global=True,
    )
    await session.refresh(refresh)
    await session.refresh(reset)

    assert target.is_active is False
    assert refresh.revoked_at is not None
    assert reset.used_at is not None
    assert await session.scalar(select(User).where(User.id == target.id)) is None

    with pytest.raises(ConflictError) as tenant_restore:
        await repository.restore(
            "users",
            str(target.id),
            company_id=company_a.id,
            actor_id=actor.id,
            allow_global=False,
        )
    assert tenant_restore.value.code == "restore_parent_deleted"
    assert "otras empresas" in tenant_restore.value.message

    await repository.restore(
        "users",
        str(target.id),
        company_id=company_a.id,
        actor_id=actor.id,
        allow_global=True,
    )
    assert await session.scalar(select(User).where(User.id == target.id)) is not None
    assert target.is_active is False
    assert refresh.revoked_at is not None
    assert reset.used_at is not None


async def test_operational_user_deactivation_revokes_credentials_without_using_trash(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    target = await _add_user(session, username="operational_deactivation")
    now = datetime.now(UTC)
    refresh = RefreshToken(
        id=uuid.uuid4(),
        user_id=target.id,
        token_hash=f"refresh-{_suffix()}",
        expires_at=now + timedelta(days=1),
    )
    reset = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=target.id,
        token_hash=f"reset-{_suffix()}",
        expires_at=now + timedelta(hours=1),
    )
    session.add_all([refresh, reset])
    await session.flush()
    repository = SqlAlchemyUserRepository(session)

    changed = await repository.deactivate(target.id)
    repeated = await repository.deactivate(target.id)
    await session.refresh(target)
    await session.refresh(refresh)
    await session.refresh(reset)

    assert changed is True
    assert repeated is False
    assert target.is_active is False
    assert target.deleted_at is None
    assert refresh.revoked_at is not None
    assert reset.used_at is not None
    assert await session.scalar(select(User).where(User.id == target.id)) is target


async def test_deleted_company_is_listable_and_restorable_without_active_company_context(
    lifecycle_session: AsyncSession,
) -> None:
    session = lifecycle_session
    actor = await _add_user(session, username="superadmin", is_superuser=True)
    company = await _add_company(session, label="Temporal")
    repository = SqlAlchemyLifecycleRepository(session)

    await repository.soft_delete(
        "companies",
        str(company.id),
        company_id=company.id,
        actor_id=actor.id,
        reason="Empresa registrada por error",
        allow_global=True,
    )

    assert await session.scalar(select(Company).where(Company.id == company.id)) is None
    items, total = await repository.list_deleted(
        uuid.UUID(int=0),
        page=1,
        size=100,
        resource="companies",
        include_all_companies=True,
    )
    assert total >= 1
    listed = next(item for item in items if item.record_id == str(company.id))
    assert listed.company_id == company.id

    restored = await repository.restore(
        "companies",
        str(company.id),
        company_id=company.id,
        actor_id=actor.id,
        allow_global=True,
    )
    assert restored.operation_applied is True
    assert await session.scalar(select(Company).where(Company.id == company.id)) is not None
