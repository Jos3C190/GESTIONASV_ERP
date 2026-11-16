"""Clientes de demostración de Grupo Lorena con datos fiscales.

Cuatro clientes ficticios, uno por caso que la pantalla debe mostrar:
- un contribuyente completo, que puede recibir crédito fiscal;
- un contribuyente sin NRC, al que la ficha le dice qué le falta;
- un consumidor final identificado;
- un cliente del extranjero.

Además, el cliente genérico «Consumidor final» de cada sucursal. Los NIT, DUI y NRC son
ficticios (empiezan con 0000). Pasa por los casos de uso y solo crea lo que falta.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from app.application.customers import CustomerUseCases
from app.domain.entities.customer import (
    CustomerDraft,
    CustomerType,
    DeliveryAddressDraft,
    Geography,
    IdentityDocument,
)
from app.domain.entities.fiscal import PersonType, TaxpayerCategory
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.organization import (
    Branch,
    District,
    GeographicDepartment,
    Municipality,
)
from app.infrastructure.models.sales import SalesCustomerModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.customer_repository import SqlAlchemyCustomerRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seed.seed_grupo_lorena import COMPANY_ID, SUPER_ADMIN_USERNAME


@dataclass(frozen=True, slots=True)
class CustomerSeed:
    code: str
    draft: CustomerDraft
    with_san_miguel_address: bool = False
    delivery: DeliveryAddressDraft | None = None


CUSTOMERS: tuple[CustomerSeed, ...] = (
    CustomerSeed(
        "CLI-00001",
        CustomerDraft(
            customer_type=CustomerType.TAXPAYER,
            name="Cafetería El Trigal, S.A. de C.V.",
            person_type=PersonType.LEGAL,
            taxpayer_category=TaxpayerCategory.OTHER,
            commercial_name="Cafetería El Trigal",
            document_type=IdentityDocument.NIT,
            document_number="0000-010101-101-1",
            nrc="000001-1",
            activity_code="56101",
            address_line="Avenida Roosevelt Sur No. 12, barrio El Centro",
            phone="2660-0001",
            email="compras@eltrigal.example",
            credit_days=15,
            credit_limit=Decimal("500.00"),
        ),
        with_san_miguel_address=True,
        delivery=DeliveryAddressDraft(
            "Cafetería centro",
            "Avenida Roosevelt Sur No. 12, San Miguel",
            latitude=Decimal("13.480900"),
            longitude=Decimal("-88.177600"),
            contact_name="Encargado de compras",
            phone="2660-0001",
        ),
    ),
    CustomerSeed(
        "CLI-00002",
        CustomerDraft(
            customer_type=CustomerType.TAXPAYER,
            name="Distribuidora La Espiga, S.A. de C.V.",
            person_type=PersonType.LEGAL,
            taxpayer_category=TaxpayerCategory.MEDIUM,
            document_type=IdentityDocument.NIT,
            document_number="0000-020202-102-2",
            activity_code="46301",
            address_line="Carretera Panamericana km 140",
            email="pedidos@laespiga.example",
            credit_days=30,
        ),
        with_san_miguel_address=True,
    ),
    CustomerSeed(
        "CLI-00003",
        CustomerDraft(
            customer_type=CustomerType.FINAL_CONSUMER,
            name="María Fernanda Rivas",
            document_type=IdentityDocument.DUI,
            document_number="00000001-0",
            phone="7000-0003",
            email="mfrivas@correo.example",
        ),
    ),
    CustomerSeed(
        "CLI-00004",
        CustomerDraft(
            customer_type=CustomerType.FOREIGN,
            name="Panadería Centroamericana, S.A.",
            person_type=PersonType.LEGAL,
            document_type=IdentityDocument.OTHER,
            document_number="GT-0000004",
            country_code="GT",
            address_line="Zona 10, Ciudad de Guatemala",
            email="compras@centroamericana.example",
        ),
    ),
)


async def _san_miguel(session: AsyncSession) -> Geography:
    row = (
        await session.execute(
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


async def seed() -> bool:
    async with session_scope() as session:
        actor = await session.scalar(select(User.id).where(User.username == SUPER_ADMIN_USERNAME))
        if actor is None:
            print("[seed] Clientes: falta el superadministrador; se reintenta después.")
            return False
        customers = CustomerUseCases(SqlAlchemyCustomerRepository(session))
        san_miguel = await _san_miguel(session)
        existing = set(
            (
                await session.scalars(
                    select(SalesCustomerModel.code).where(
                        SalesCustomerModel.company_id == COMPANY_ID
                    )
                )
            ).all()
        )
        for item in CUSTOMERS:
            if item.code in existing:
                continue
            draft = (
                replace(item.draft, geography=san_miguel)
                if item.with_san_miguel_address
                else item.draft
            )
            created = await customers.create_customer(COMPANY_ID, draft, actor, code=item.code)
            if item.delivery is not None:
                await customers.save_delivery_address(
                    COMPANY_ID,
                    created.id,
                    replace(item.delivery, geography=san_miguel),
                )
        branches = (
            await session.scalars(
                select(Branch.id).where(
                    Branch.company_id == COMPANY_ID, Branch.deleted_at.is_(None)
                )
            )
        ).all()
        for branch_id in branches:
            await customers.generic_customer(COMPANY_ID, branch_id, actor)
    return True
