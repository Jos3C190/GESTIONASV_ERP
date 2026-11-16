"""SQLAlchemy implementation of the customer repository. Every query filters by company."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.customer import (
    Customer,
    CustomerAddress,
    CustomerDraft,
    CustomerType,
    DeliveryAddress,
    DeliveryAddressDraft,
    Geography,
    IdentityDocument,
)
from app.domain.entities.fiscal import PersonType, TaxpayerCategory
from app.domain.ports.customer_repository import CustomerFilters
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fiscal import HaciendaCatalogItemModel
from app.infrastructure.models.organization import (
    Branch,
    District,
    GeographicDepartment,
    Municipality,
)
from app.infrastructure.models.sales import (
    SalesCustomerDeliveryAddressModel,
    SalesCustomerModel,
)

_CODE = re.compile(r"^CLI-(\d+)$")


def _now() -> datetime:
    return datetime.now(UTC)


def _geography(row: SalesCustomerModel | SalesCustomerDeliveryAddressModel) -> Geography | None:
    if row.department_id is None or row.municipality_id is None or row.district_id is None:
        return None
    return Geography(row.department_id, row.municipality_id, row.district_id)


def _draft(row: SalesCustomerModel) -> CustomerDraft:
    return CustomerDraft(
        customer_type=CustomerType(row.customer_type),
        name=row.name,
        person_type=PersonType(row.person_type),
        taxpayer_category=TaxpayerCategory(row.taxpayer_category)
        if row.taxpayer_category
        else None,
        is_withholding_agent=row.is_withholding_agent,
        commercial_name=row.commercial_name,
        document_type=IdentityDocument(row.document_type) if row.document_type else None,
        document_number=row.document_number,
        nrc=row.nrc,
        activity_code=row.activity_code,
        geography=_geography(row),
        address_line=row.address_line,
        country_code=row.country_code,
        phone=row.phone,
        email=row.email,
        credit_days=row.credit_days,
        credit_limit=row.credit_limit,
        seller_employee_id=row.seller_employee_id,
    )


class SqlAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- reads ---
    async def _addresses(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, CustomerAddress]:
        """Names and Hacienda codes of the given district ids."""
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                select(District, Municipality, GeographicDepartment)
                .join(Municipality, Municipality.id == District.municipality_id)
                .join(GeographicDepartment, GeographicDepartment.id == Municipality.department_id)
                .where(District.id.in_(ids))
            )
        ).all()
        return {
            district.id: CustomerAddress(
                department=department.name,
                department_code=department.hacienda_code,
                municipality=municipality.name,
                municipality_code=municipality.hacienda_code,
                district=district.name,
                district_code=district.hacienda_code,
            )
            for district, municipality, department in rows
        }

    async def _catalog_names(self, catalog_code: str, codes: set[str]) -> dict[str, str]:
        if not codes:
            return {}
        rows = await self._session.execute(
            select(HaciendaCatalogItemModel.code, HaciendaCatalogItemModel.name).where(
                HaciendaCatalogItemModel.catalog_code == catalog_code,
                HaciendaCatalogItemModel.group_code == "",
                HaciendaCatalogItemModel.code.in_(codes),
            )
        )
        return dict(rows.tuples().all())

    async def _hydrate(
        self, rows: list[SalesCustomerModel], *, with_delivery: bool
    ) -> list[Customer]:
        delivery_rows: list[SalesCustomerDeliveryAddressModel] = []
        if with_delivery and rows:
            delivery_rows = list(
                (
                    await self._session.execute(
                        select(SalesCustomerDeliveryAddressModel)
                        .where(
                            SalesCustomerDeliveryAddressModel.company_id == rows[0].company_id,
                            SalesCustomerDeliveryAddressModel.customer_id.in_([r.id for r in rows]),
                        )
                        .order_by(
                            SalesCustomerDeliveryAddressModel.is_default.desc(),
                            SalesCustomerDeliveryAddressModel.label,
                        )
                    )
                )
                .scalars()
                .all()
            )
        districts = {r.district_id for r in rows if r.district_id} | {
            d.district_id for d in delivery_rows if d.district_id
        }
        addresses = await self._addresses(districts)
        activities = await self._catalog_names(
            "CAT-019", {r.activity_code for r in rows if r.activity_code}
        )
        countries = await self._catalog_names(
            "CAT-020", {r.country_code for r in rows if r.country_code}
        )
        by_customer: dict[uuid.UUID, list[DeliveryAddress]] = {}
        for item in delivery_rows:
            by_customer.setdefault(item.customer_id, []).append(
                self._delivery(item, addresses.get(item.district_id) if item.district_id else None)
            )
        return [
            Customer(
                id=row.id,
                company_id=row.company_id,
                code=row.code,
                draft=_draft(row),
                address=addresses.get(row.district_id, CustomerAddress())
                if row.district_id
                else CustomerAddress(),
                activity_name=activities.get(row.activity_code or ""),
                country_name=countries.get(row.country_code or ""),
                is_active=row.is_active,
                is_generic=row.is_generic,
                branch_id=row.branch_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                delivery_addresses=tuple(by_customer.get(row.id, ())),
            )
            for row in rows
        ]

    @staticmethod
    def _delivery(
        row: SalesCustomerDeliveryAddressModel, address: CustomerAddress | None
    ) -> DeliveryAddress:
        return DeliveryAddress(
            id=row.id,
            label=row.label,
            address_line=row.address_line,
            geography=_geography(row),
            address=address or CustomerAddress(),
            latitude=row.latitude,
            longitude=row.longitude,
            contact_name=row.contact_name,
            phone=row.phone,
            is_default=row.is_default,
            is_active=row.is_active,
        )

    async def list_customers(
        self, company_id: uuid.UUID, filters: CustomerFilters, *, page: int, size: int
    ) -> tuple[list[Customer], int]:
        conditions = [SalesCustomerModel.company_id == company_id]
        if not filters.include_generic:
            conditions.append(SalesCustomerModel.is_generic.is_(False))
        if filters.customer_type is not None:
            conditions.append(SalesCustomerModel.customer_type == filters.customer_type.value)
        if filters.active is not None:
            conditions.append(SalesCustomerModel.is_active.is_(filters.active))
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            digits = re.sub(r"\D", "", filters.search)
            options = [
                SalesCustomerModel.code.ilike(pattern),
                SalesCustomerModel.name.ilike(pattern),
                SalesCustomerModel.commercial_name.ilike(pattern),
            ]
            if len(digits) >= 3:  # noqa: PLR2004 - evita coincidencias por un solo dígito
                options += [
                    SalesCustomerModel.document_number.like(f"%{digits}%"),
                    SalesCustomerModel.nrc.like(f"%{digits}%"),
                ]
            conditions.append(or_(*options))
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(SalesCustomerModel).where(*conditions)
            )
            or 0
        )
        rows = (
            (
                await self._session.execute(
                    select(SalesCustomerModel)
                    .where(*conditions)
                    .order_by(SalesCustomerModel.is_generic.desc(), SalesCustomerModel.name)
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )
        return await self._hydrate(list(rows), with_delivery=False), total

    async def _row(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> SalesCustomerModel | None:
        row: SalesCustomerModel | None = await self._session.scalar(
            select(SalesCustomerModel).where(
                SalesCustomerModel.company_id == company_id, SalesCustomerModel.id == customer_id
            )
        )
        return row

    async def get_customer(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> Customer | None:
        row = await self._row(company_id, customer_id)
        if row is None:
            return None
        return (await self._hydrate([row], with_delivery=True))[0]

    async def _exists(self, *conditions: ColumnElement[bool]) -> bool:
        return bool(await self._session.scalar(select(exists().where(*conditions))))

    async def code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [
            SalesCustomerModel.company_id == company_id,
            func.lower(SalesCustomerModel.code) == code.lower(),
        ]
        if exclude_id is not None:
            conditions.append(SalesCustomerModel.id != exclude_id)
        return await self._exists(*conditions)

    async def next_code(self, company_id: uuid.UUID) -> str:
        codes = (
            await self._session.execute(
                select(SalesCustomerModel.code).where(
                    SalesCustomerModel.company_id == company_id,
                    SalesCustomerModel.code.like("CLI-%"),
                )
            )
        ).scalars()
        numbers = [int(m.group(1)) for c in codes if (m := _CODE.match(c))]
        return f"CLI-{max(numbers, default=0) + 1:05d}"

    async def document_taken(
        self,
        company_id: uuid.UUID,
        document_type: IdentityDocument,
        number: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        conditions = [
            SalesCustomerModel.company_id == company_id,
            SalesCustomerModel.document_type == document_type.value,
            SalesCustomerModel.document_number == number,
        ]
        if exclude_id is not None:
            conditions.append(SalesCustomerModel.id != exclude_id)
        return await self._exists(*conditions)

    async def nrc_taken(
        self, company_id: uuid.UUID, nrc: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [SalesCustomerModel.company_id == company_id, SalesCustomerModel.nrc == nrc]
        if exclude_id is not None:
            conditions.append(SalesCustomerModel.id != exclude_id)
        return await self._exists(*conditions)

    async def catalog_has(self, catalog_code: str, code: str) -> bool:
        return await self._exists(
            HaciendaCatalogItemModel.catalog_code == catalog_code,
            HaciendaCatalogItemModel.group_code == "",
            HaciendaCatalogItemModel.code == code,
            HaciendaCatalogItemModel.is_active.is_(True),
        )

    async def geography_consistent(self, geography: Geography) -> bool:
        found = await self._session.scalar(
            select(District.id)
            .join(Municipality, Municipality.id == District.municipality_id)
            .where(
                District.id == geography.district_id,
                Municipality.id == geography.municipality_id,
                Municipality.department_id == geography.department_id,
            )
        )
        return found is not None

    async def employee_in_company(self, company_id: uuid.UUID, employee_id: uuid.UUID) -> bool:
        return await self._exists(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )

    async def branch_exists(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
        return await self._exists(
            Branch.id == branch_id, Branch.company_id == company_id, Branch.deleted_at.is_(None)
        )

    # --- writes ---
    @staticmethod
    def _assign(row: SalesCustomerModel, draft: CustomerDraft) -> None:
        geography = draft.geography
        row.customer_type = draft.customer_type.value
        row.name = draft.name
        row.person_type = draft.person_type.value
        row.taxpayer_category = draft.taxpayer_category.value if draft.taxpayer_category else None
        row.is_withholding_agent = draft.is_withholding_agent
        row.commercial_name = draft.commercial_name
        row.document_type = draft.document_type.value if draft.document_type else None
        row.document_number = draft.document_number
        row.nrc = draft.nrc
        row.activity_code = draft.activity_code
        row.department_id = geography.department_id if geography else None
        row.municipality_id = geography.municipality_id if geography else None
        row.district_id = geography.district_id if geography else None
        row.address_line = draft.address_line
        row.country_code = draft.country_code
        row.phone = draft.phone
        row.email = draft.email
        row.credit_days = draft.credit_days
        row.credit_limit = draft.credit_limit
        row.seller_employee_id = draft.seller_employee_id

    async def create_customer(
        self,
        company_id: uuid.UUID,
        code: str,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
        *,
        generic_branch_id: uuid.UUID | None = None,
    ) -> Customer:
        row = SalesCustomerModel(
            company_id=company_id,
            code=code,
            created_by_id=actor_id,
            updated_by_id=actor_id,
            is_generic=generic_branch_id is not None,
            branch_id=generic_branch_id,
        )
        self._assign(row, draft)
        self._session.add(row)
        await self._session.flush()
        created = await self.get_customer(company_id, row.id)
        assert created is not None
        return created

    async def update_customer(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
    ) -> Customer:
        row = await self._row(company_id, customer_id)
        assert row is not None
        self._assign(row, draft)
        row.updated_by_id = actor_id
        row.updated_at = _now()
        await self._session.flush()
        updated = await self.get_customer(company_id, customer_id)
        assert updated is not None
        return updated

    async def set_active(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, active: bool, actor_id: uuid.UUID
    ) -> Customer:
        await self._session.execute(
            update(SalesCustomerModel)
            .where(
                SalesCustomerModel.company_id == company_id, SalesCustomerModel.id == customer_id
            )
            .values(is_active=active, updated_by_id=actor_id, updated_at=_now())
        )
        await self._session.flush()
        customer = await self.get_customer(company_id, customer_id)
        assert customer is not None
        return customer

    async def generic_customer(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> Customer | None:
        row = await self._session.scalar(
            select(SalesCustomerModel).where(
                SalesCustomerModel.company_id == company_id,
                SalesCustomerModel.branch_id == branch_id,
                SalesCustomerModel.is_generic.is_(True),
            )
        )
        return (await self._hydrate([row], with_delivery=False))[0] if row is not None else None

    # --- delivery addresses ---
    async def _delivery_row(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> SalesCustomerDeliveryAddressModel | None:
        row: SalesCustomerDeliveryAddressModel | None = await self._session.scalar(
            select(SalesCustomerDeliveryAddressModel).where(
                SalesCustomerDeliveryAddressModel.company_id == company_id,
                SalesCustomerDeliveryAddressModel.customer_id == customer_id,
                SalesCustomerDeliveryAddressModel.id == address_id,
            )
        )
        return row

    async def get_delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress | None:
        row = await self._delivery_row(company_id, customer_id, address_id)
        if row is None:
            return None
        addresses = await self._addresses({row.district_id} if row.district_id else set())
        return self._delivery(row, addresses.get(row.district_id) if row.district_id else None)

    async def save_delivery_address(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: DeliveryAddressDraft,
        *,
        address_id: uuid.UUID | None = None,
    ) -> DeliveryAddress:
        if draft.is_default:
            # Only one default per customer (partial unique index): clear it first.
            await self._session.execute(
                update(SalesCustomerDeliveryAddressModel)
                .where(
                    SalesCustomerDeliveryAddressModel.company_id == company_id,
                    SalesCustomerDeliveryAddressModel.customer_id == customer_id,
                    SalesCustomerDeliveryAddressModel.is_default.is_(True),
                )
                .values(is_default=False, updated_at=_now())
            )
        row = (
            await self._delivery_row(company_id, customer_id, address_id)
            if address_id is not None
            else None
        )
        if row is None:
            row = SalesCustomerDeliveryAddressModel(company_id=company_id, customer_id=customer_id)
            self._session.add(row)
        geography = draft.geography
        row.label = draft.label
        row.address_line = draft.address_line
        row.department_id = geography.department_id if geography else None
        row.municipality_id = geography.municipality_id if geography else None
        row.district_id = geography.district_id if geography else None
        row.latitude = draft.latitude
        row.longitude = draft.longitude
        row.contact_name = draft.contact_name
        row.phone = draft.phone
        row.is_default = draft.is_default
        row.is_active = draft.is_active
        row.updated_at = _now()
        await self._session.flush()
        saved = await self.get_delivery_address(company_id, customer_id, row.id)
        assert saved is not None
        return saved

    async def delete_delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            delete(SalesCustomerDeliveryAddressModel).where(
                SalesCustomerDeliveryAddressModel.company_id == company_id,
                SalesCustomerDeliveryAddressModel.customer_id == customer_id,
                SalesCustomerDeliveryAddressModel.id == address_id,
            )
        )
        await self._session.flush()
