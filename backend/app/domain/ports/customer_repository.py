"""Puerto del repositorio de clientes. Toda operación recibe la empresa."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.customer import (
    Customer,
    CustomerDraft,
    CustomerType,
    DeliveryAddress,
    DeliveryAddressDraft,
    Geography,
    IdentityDocument,
    SellerOption,
)


@dataclass(frozen=True, slots=True)
class CustomerFilters:
    search: str | None = None
    customer_type: CustomerType | None = None
    active: bool | None = None
    include_generic: bool = False


class CustomerRepository(Protocol):
    async def list_customers(
        self, company_id: uuid.UUID, filters: CustomerFilters, *, page: int, size: int
    ) -> tuple[list[Customer], int]: ...

    async def get_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None: ...

    async def code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool: ...

    async def next_code(self, company_id: uuid.UUID) -> str: ...

    async def document_taken(
        self,
        company_id: uuid.UUID,
        document_type: IdentityDocument,
        number: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def nrc_taken(
        self, company_id: uuid.UUID, nrc: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool: ...

    async def catalog_has(self, catalog_code: str, code: str) -> bool: ...

    async def geography_consistent(self, geography: Geography) -> bool: ...

    async def employee_in_company(self, company_id: uuid.UUID, employee_id: uuid.UUID) -> bool: ...

    async def seller_options(
        self, company_id: uuid.UUID, *, search: str | None, limit: int
    ) -> list[SellerOption]: ...

    async def branch_exists(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool: ...

    async def branch_code(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> str | None: ...

    async def create_customer(
        self,
        company_id: uuid.UUID,
        code: str,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
        *,
        generic_branch_id: uuid.UUID | None = None,
    ) -> Customer: ...

    async def update_customer(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
    ) -> Customer: ...

    async def set_active(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, active: bool, actor_id: uuid.UUID
    ) -> Customer: ...

    async def generic_customer(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> Customer | None: ...

    async def get_delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress | None: ...

    async def save_delivery_address(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: DeliveryAddressDraft,
        *,
        address_id: uuid.UUID | None = None,
    ) -> DeliveryAddress: ...

    async def delete_delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> None: ...
