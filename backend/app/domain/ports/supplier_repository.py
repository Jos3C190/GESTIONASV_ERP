"""Supplier repository port interface."""
from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.supplier import Supplier, SupplierContact


class SupplierRepository(Protocol):
    async def list_suppliers(
        self,
        country_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        ...

    async def get_supplier_by_id(self, supplier_id: int) -> Supplier | None:
        ...

    async def get_supplier_by_uuid(self, supplier_uuid: uuid.UUID) -> Supplier | None:
        ...

    async def get_supplier_by_code(self, code: str) -> Supplier | None:
        ...

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
        ...

    async def update_supplier(
        self,
        supplier_id: int,
        **kwargs,
    ) -> Supplier | None:
        ...

    # Supplier Contacts
    async def add_contact(
        self,
        supplier_id: int,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> SupplierContact:
        ...

    async def update_contact(
        self,
        contact_id: int,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
    ) -> SupplierContact | None:
        ...

    async def delete_contact(self, contact_id: int) -> bool:
        ...
