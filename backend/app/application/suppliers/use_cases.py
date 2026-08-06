"""Application use cases for Suppliers and Contacts."""

from __future__ import annotations

import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.supplier import Supplier, SupplierContact
from app.domain.ports.catalog_repository import CatalogRepository
from app.domain.ports.supplier_repository import SupplierRepository


class SupplierUseCases:
    def __init__(self, supplier_repo: SupplierRepository, catalog_repo: CatalogRepository) -> None:
        self._supplier_repo = supplier_repo
        self._catalog_repo = catalog_repo

    async def list_suppliers(
        self,
        country_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        return await self._supplier_repo.list_suppliers(
            country_id=country_id,
            search=search,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )

    async def get_supplier(self, supplier_id: int) -> Supplier:
        supplier = await self._supplier_repo.get_supplier_by_id(supplier_id)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

    async def get_supplier_by_uuid(self, supplier_uuid: uuid.UUID) -> Supplier:
        supplier = await self._supplier_repo.get_supplier_by_uuid(supplier_uuid)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

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
        # Validate unique code
        existing = await self._supplier_repo.get_supplier_by_code(code)
        if existing:
            raise ConflictError(f"El código de proveedor '{code}' ya existe", code="supplier_code_exists")

        # Validate country exists
        country = await self._catalog_repo.get_country_by_id(country_id)
        if not country:
            raise NotFoundError("País especificado no encontrado", code="country_not_found")

        return await self._supplier_repo.create_supplier(
            code=code,
            name=name,
            country_id=country_id,
            address=address,
            phone=phone,
            email=email,
            website=website,
        )

    async def update_supplier(self, supplier_id: int, **kwargs) -> Supplier:
        if "country_id" in kwargs and kwargs["country_id"] is not None:
            country = await self._catalog_repo.get_country_by_id(kwargs["country_id"])
            if not country:
                raise NotFoundError("País especificado no encontrado", code="country_not_found")

        supplier = await self._supplier_repo.update_supplier(supplier_id=supplier_id, **kwargs)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

    # Contacts
    async def add_contact(
        self,
        supplier_id: int,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> SupplierContact:
        await self.get_supplier(supplier_id)
        return await self._supplier_repo.add_contact(
            supplier_id=supplier_id, full_name=full_name, phone=phone, email=email
        )

    async def update_contact(
        self,
        contact_id: int,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
    ) -> SupplierContact:
        contact = await self._supplier_repo.update_contact(
            contact_id=contact_id,
            full_name=full_name,
            phone=phone,
            email=email,
            is_active=is_active,
        )
        if not contact:
            raise NotFoundError("Contacto de proveedor no encontrado", code="contact_not_found")
        return contact

    async def delete_contact(self, contact_id: int) -> bool:
        deleted = await self._supplier_repo.delete_contact(contact_id)
        if not deleted:
            raise NotFoundError("Contacto de proveedor no encontrado", code="contact_not_found")
        return True
