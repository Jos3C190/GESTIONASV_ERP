"""Explicitly assigned central warehouses stay available to scoped consolidation flows."""

from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.organization import Branch, Company, Warehouse, WarehouseCategory
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e


async def test_branch_scoped_catalogue_includes_mother_only_when_requested(e2e_client) -> None:
    password = "Mother!Warehouse2026"
    await seed_user(
        username="mother-warehouse-admin",
        email="mother-warehouse-admin@example.com",
        password=password,
        is_superuser=True,
    )
    login = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "mother-warehouse-admin", "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    company_id = await get_test_company_id()
    auth = {"Authorization": f"Bearer {token}", "X-Company-ID": str(company_id)}

    branches_response = await e2e_client.get(
        f"/api/v1/branches?company_id={company_id}", headers=auth
    )
    assert branches_response.status_code == 200, branches_response.text
    branches = branches_response.json()
    branch_id = next(item["id"] for item in branches if not item["is_headquarters"])
    headquarters_id = next(
        (item["id"] for item in branches if item["is_headquarters"]), None
    )
    if headquarters_id is None:
        create_headquarters = await e2e_client.post(
            "/api/v1/branches",
            headers=auth,
            json={
                "company_id": str(company_id),
                "is_headquarters": True,
                "name": "Casa matriz de prueba",
            },
        )
        assert create_headquarters.status_code == 201, create_headquarters.text
        headquarters_id = create_headquarters.json()["id"]

    created_mother_id: uuid.UUID | None = None
    async with async_session_factory() as session:
        category_id = await session.scalar(
            select(WarehouseCategory.id)
            .where(
                WarehouseCategory.company_id == company_id,
                WarehouseCategory.is_active.is_(True),
                WarehouseCategory.deleted_at.is_(None),
            )
            .order_by(WarehouseCategory.name)
            .limit(1)
        )
        mother_id = await session.scalar(
            select(Warehouse.id).where(
                Warehouse.company_id == company_id,
                Warehouse.is_central.is_(True),
                Warehouse.is_active.is_(True),
                Warehouse.operational_status == "active",
                Warehouse.deleted_at.is_(None),
            )
        )
    assert category_id is not None

    if mother_id is None:
        create_mother = await e2e_client.post(
            "/api/v1/warehouses",
            headers=auth,
            json={
                "company_id": str(company_id),
                "branch_id": str(headquarters_id),
                "warehouse_category_id": str(category_id),
                "code": f"BM-{uuid.uuid4().hex[:10]}",
                "name": f"Bodega madre prueba {uuid.uuid4().hex[:8]}",
                "is_central": True,
            },
        )
        assert create_mother.status_code == 201, create_mother.text
        created_mother_id = uuid.UUID(create_mother.json()["id"])
        mother_id = created_mother_id

    store_warehouse = await e2e_client.get(
        "/api/v1/warehouses/catalogue",
        params={"company_id": str(company_id), "branch_id": branch_id},
        headers=auth,
    )
    assert store_warehouse.status_code == 200, store_warehouse.text
    store_warehouse_ids = {item["id"] for item in store_warehouse.json()}
    if not store_warehouse_ids:
        create_store_warehouse = await e2e_client.post(
            "/api/v1/warehouses",
            headers=auth,
            json={
                "company_id": str(company_id),
                "branch_id": branch_id,
                "warehouse_category_id": str(category_id),
                "code": f"ST-B01-{uuid.uuid4().hex[:8]}",
                "name": "Bodega de sucursal prueba B01",
                "is_central": False,
            },
        )
        assert create_store_warehouse.status_code == 201, create_store_warehouse.text
        store_warehouse_ids.add(create_store_warehouse.json()["id"])

    try:
        regular_catalogue = await e2e_client.get(
            "/api/v1/warehouses/catalogue",
            params={"company_id": str(company_id), "branch_id": branch_id},
            headers=auth,
        )
        consolidation_catalogue = await e2e_client.get(
            "/api/v1/warehouses/catalogue",
            params={
                "company_id": str(company_id),
                "branch_id": branch_id,
                "include_company_central": "true",
            },
            headers=auth,
        )
        global_catalogue = await e2e_client.get(
            "/api/v1/warehouses/catalogue",
            params={"company_id": str(company_id)},
            headers=auth,
        )
        assert regular_catalogue.status_code == 200, regular_catalogue.text
        assert consolidation_catalogue.status_code == 200, consolidation_catalogue.text
        assert global_catalogue.status_code == 200, global_catalogue.text
        assert str(mother_id) not in {item["id"] for item in regular_catalogue.json()}
        assert str(mother_id) in {item["id"] for item in consolidation_catalogue.json()}
        all_company_warehouse_ids = {item["id"] for item in global_catalogue.json()}
        assert str(mother_id) in all_company_warehouse_ids
        assert store_warehouse_ids & all_company_warehouse_ids, (
            "El usuario global debe conservar acceso a bodegas de sucursal."
        )
        assert all(
            item["branch_id"] == branch_id
            or (
                item["id"] == str(mother_id)
                and item["is_central"]
                and item["branch_id"] == str(headquarters_id)
            )
            for item in consolidation_catalogue.json()
        )

        duplicate_headquarters = await e2e_client.post(
            "/api/v1/branches",
            headers=auth,
            json={
                "company_id": str(company_id),
                "is_headquarters": True,
                "name": "Matriz duplicada de prueba",
            },
        )
        assert duplicate_headquarters.status_code == 409, duplicate_headquarters.text

        async with async_session_factory() as session:
            source_company = await session.get(Company, company_id)
            assert source_company is not None
            suffix = uuid.uuid4().hex[:10]
            other_company = Company(
                name=f"Empresa aislada B01 {suffix}",
                commercial_name=f"Empresa aislada B01 {suffix}",
                nit=f"B01{suffix}",
                nrc=f"B01{suffix}",
                address=source_company.address,
                department_id=source_company.department_id,
                municipality_id=source_company.municipality_id,
                district_id=source_company.district_id,
            )
            session.add(other_company)
            await session.flush()
            other_company_id = other_company.id
            other_headquarters = Branch(
                company_id=other_company_id,
                is_headquarters=True,
                name=f"Matriz aislada B01 {suffix}",
                code=f"B01-{suffix}",
                address=source_company.address,
                department_id=source_company.department_id,
                municipality_id=source_company.municipality_id,
                district_id=source_company.district_id,
            )
            session.add(other_headquarters)
            await session.flush()
            other_headquarters_id = other_headquarters.id
            await session.commit()

        foreign_branch_warehouse = await e2e_client.post(
            "/api/v1/warehouses",
            headers=auth,
            json={
                "company_id": str(company_id),
                "branch_id": str(other_headquarters_id),
                "warehouse_category_id": str(category_id),
                "code": f"B01-X-{uuid.uuid4().hex[:8]}",
                "name": "No debe aceptar matriz de otra empresa",
                "is_central": True,
            },
        )
        assert foreign_branch_warehouse.status_code == 404, foreign_branch_warehouse.text

        async with async_session_factory() as session:
            session.add(
                Warehouse(
                    company_id=company_id,
                    branch_id=other_headquarters_id,
                    warehouse_category_id=category_id,
                    code=f"B01-X-{uuid.uuid4().hex[:8]}",
                    name="Integridad compuesta B01",
                    is_central=False,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
    finally:
        if created_mother_id is not None:
            async with async_session_factory() as session:
                await session.execute(delete(Warehouse).where(Warehouse.id == created_mother_id))
                await session.commit()
