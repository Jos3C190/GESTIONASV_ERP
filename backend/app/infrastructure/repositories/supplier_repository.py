"""SQLAlchemy implementation of SupplierRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.supplier import Supplier, SupplierContact
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel


def _to_supplier_contact(orm: SupplierContactModel) -> SupplierContact:
    return SupplierContact(
        id=orm.id_supplier_contact,
        supplier_id=orm.id_supplier,
        full_name=orm.full_name,
        phone=orm.phone,
        email=orm.email,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_supplier(orm: SupplierModel) -> Supplier:
    contacts = (
        tuple(_to_supplier_contact(c) for c in orm.contacts)
        if hasattr(orm, "contacts") and orm.contacts
        else ()
    )
    return Supplier(
        id=orm.id_supplier,
        uuid=orm.uuid,
        code=orm.code,
        name=orm.name,
        country_id=orm.country_id,
        address=orm.address,
        phone=orm.phone,
        email=orm.email,
        website=orm.website,
        is_active=orm.is_active,
        contacts=contacts,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemySupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_suppliers(
        self,
        country_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        conditions = []
        if country_id is not None:
            conditions.append(SupplierModel.country_id == country_id)
        if active_only:
            conditions.append(SupplierModel.is_active.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    SupplierModel.name.ilike(pattern),
                    SupplierModel.code.ilike(pattern),
                    SupplierModel.email.ilike(pattern),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(SupplierModel).where(*conditions)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        # Query items
        stmt = (
            select(SupplierModel)
            .options(selectinload(SupplierModel.contacts))
            .where(*conditions)
            .order_by(SupplierModel.name)
            .offset(skip)
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        items = [_to_supplier(s) for s in res.scalars().all()]
        return items, total

    async def get_supplier_by_id(self, supplier_id: int) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(selectinload(SupplierModel.contacts))
            .where(SupplierModel.id_supplier == supplier_id)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def get_supplier_by_uuid(self, supplier_uuid: uuid.UUID) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(selectinload(SupplierModel.contacts))
            .where(SupplierModel.uuid == supplier_uuid)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def get_supplier_by_code(self, code: str) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(selectinload(SupplierModel.contacts))
            .where(SupplierModel.code == code)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def create_supplier(
        self,
        code: str,
        name: str,
        country_id: int,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
    ) -> Supplier:
        orm = SupplierModel(
            code=code,
            name=name,
            country_id=country_id,
            address=address,
            phone=phone,
            email=email,
            website=website,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_supplier(orm)

    async def update_supplier(self, supplier_id: int, **kwargs) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(selectinload(SupplierModel.contacts))
            .where(SupplierModel.id_supplier == supplier_id)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        for key, value in kwargs.items():
            if hasattr(orm, key) and value is not None:
                setattr(orm, key, value)
        await self._session.flush()
        return _to_supplier(orm)

    # Contacts
    async def add_contact(
        self,
        supplier_id: int,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> SupplierContact:
        orm = SupplierContactModel(
            id_supplier=supplier_id,
            full_name=full_name,
            phone=phone,
            email=email,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_supplier_contact(orm)

    async def update_contact(
        self,
        contact_id: int,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
    ) -> SupplierContact | None:
        stmt = select(SupplierContactModel).where(SupplierContactModel.id_supplier_contact == contact_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if full_name is not None:
            orm.full_name = full_name
        if phone is not None:
            orm.phone = phone
        if email is not None:
            orm.email = email
        if is_active is not None:
            orm.is_active = is_active
        await self._session.flush()
        return _to_supplier_contact(orm)

    async def delete_contact(self, contact_id: int) -> bool:
        stmt = delete(SupplierContactModel).where(SupplierContactModel.id_supplier_contact == contact_id)
        res = await self._session.execute(stmt)
        return res.rowcount > 0
