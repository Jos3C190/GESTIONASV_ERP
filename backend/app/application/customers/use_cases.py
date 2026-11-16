"""Casos de uso del maestro de clientes con identidad fiscal."""

from __future__ import annotations

import uuid
from dataclasses import replace

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.customer import (
    GENERIC_NAME,
    Customer,
    CustomerDraft,
    CustomerType,
    DeliveryAddress,
    DeliveryAddressDraft,
    SellerOption,
    require_editable,
    validate_delivery_address,
    validate_draft,
)
from app.domain.ports.customer_repository import CustomerFilters, CustomerRepository

MAX_PAGE_SIZE = 100


class CustomerUseCases:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repo = repository

    async def list_customers(
        self, company_id: uuid.UUID, filters: CustomerFilters, *, page: int, size: int
    ) -> tuple[list[Customer], int]:
        return await self._repo.list_customers(
            company_id, filters, page=max(page, 1), size=max(1, min(size, MAX_PAGE_SIZE))
        )

    async def seller_options(
        self, company_id: uuid.UUID, *, search: str | None, limit: int = 20
    ) -> list[SellerOption]:
        return await self._repo.seller_options(
            company_id, search=search, limit=max(1, min(limit, MAX_PAGE_SIZE))
        )

    async def get_customer(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        customer = await self._repo.get_customer(company_id, customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        return customer

    async def _checked(
        self, company_id: uuid.UUID, draft: CustomerDraft, exclude_id: uuid.UUID | None = None
    ) -> CustomerDraft:
        draft = validate_draft(draft)
        if (
            draft.document_type
            and draft.document_number
            and await self._repo.document_taken(
                company_id, draft.document_type, draft.document_number, exclude_id=exclude_id
            )
        ):
            raise ConflictError(
                "Ya hay un cliente con ese documento de identidad.",
                code="customer_document_duplicate",
            )
        if draft.nrc and await self._repo.nrc_taken(company_id, draft.nrc, exclude_id=exclude_id):
            raise ConflictError("Ya hay un cliente con ese NRC.", code="customer_nrc_duplicate")
        if draft.activity_code and not await self._repo.catalog_has("CAT-019", draft.activity_code):
            raise BusinessRuleError(
                "Ese código no está en el catálogo de actividades económicas de Hacienda.",
                code="customer_activity_unknown",
            )
        if draft.country_code and not await self._repo.catalog_has("CAT-020", draft.country_code):
            raise BusinessRuleError(
                "Ese país no está en el catálogo de Hacienda.", code="customer_country_unknown"
            )
        if draft.geography is not None and not await self._repo.geography_consistent(
            draft.geography
        ):
            raise BusinessRuleError(
                "El distrito no pertenece al municipio o el municipio no pertenece al "
                "departamento.",
                code="customer_geography_invalid",
            )
        if draft.seller_employee_id is not None and not await self._repo.employee_in_company(
            company_id, draft.seller_employee_id
        ):
            raise NotFoundError(
                "No se encontró ese vendedor en la empresa.", code="customer_seller_not_found"
            )
        if draft.price_list_id is not None and not await self._repo.price_list_active(
            company_id, draft.price_list_id
        ):
            raise BusinessRuleError(
                "Esa lista de precios no existe en la empresa o está inactiva.",
                code="customer_price_list_invalid",
            )
        return draft

    async def create_customer(
        self,
        company_id: uuid.UUID,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
        *,
        code: str | None = None,
    ) -> Customer:
        draft = await self._checked(company_id, draft)
        code = (code or "").strip().upper() or await self._repo.next_code(company_id)
        if await self._repo.code_taken(company_id, code):
            raise ConflictError(
                "Ya existe un cliente con ese código.", code="sales_customer_code_exists"
            )
        return await self._repo.create_customer(company_id, code, draft, actor_id)

    async def update_customer(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: CustomerDraft,
        actor_id: uuid.UUID,
    ) -> Customer:
        require_editable(await self.get_customer(company_id, customer_id))
        draft = await self._checked(company_id, draft, exclude_id=customer_id)
        return await self._repo.update_customer(company_id, customer_id, draft, actor_id)

    async def set_active(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, active: bool, actor_id: uuid.UUID
    ) -> Customer:
        customer = await self.get_customer(company_id, customer_id)
        require_editable(customer)
        if customer.is_active == active:
            return customer
        return await self._repo.set_active(company_id, customer_id, active, actor_id)

    async def generic_customer(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, actor_id: uuid.UUID
    ) -> tuple[Customer, bool]:
        """Cliente «Consumidor final» de la sucursal; lo crea la primera vez."""
        existing = await self._repo.generic_customer(company_id, branch_id)
        if existing is not None:
            return existing, False
        if not await self._repo.branch_exists(company_id, branch_id):
            raise NotFoundError(
                "No se encontró esa sucursal en la empresa.", code="customer_branch_not_found"
            )
        branch_code = await self._repo.branch_code(company_id, branch_id)
        code = f"CF-{branch_code or str(branch_id)[:8]}".upper()[:40]
        if await self._repo.code_taken(company_id, code):
            code = f"CF-{str(branch_id)[:8]}".upper()
        created = await self._repo.create_customer(
            company_id,
            code,
            CustomerDraft(CustomerType.FINAL_CONSUMER, GENERIC_NAME),
            actor_id,
            generic_branch_id=branch_id,
        )
        return created, True

    # --- delivery addresses ---
    async def save_delivery_address(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        draft: DeliveryAddressDraft,
        *,
        address_id: uuid.UUID | None = None,
    ) -> DeliveryAddress:
        customer = await self.get_customer(company_id, customer_id)
        require_editable(customer)
        if address_id is not None:
            await self._delivery_or_404(company_id, customer_id, address_id)
        draft = validate_delivery_address(draft)
        if draft.geography is not None and not await self._repo.geography_consistent(
            draft.geography
        ):
            raise BusinessRuleError(
                "El distrito no pertenece al municipio o el municipio no pertenece al "
                "departamento.",
                code="customer_geography_invalid",
            )
        if not customer.delivery_addresses and draft.is_active:
            draft = replace(draft, is_default=True)
        return await self._repo.save_delivery_address(
            company_id, customer_id, draft, address_id=address_id
        )

    async def _delivery_or_404(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress:
        address = await self._repo.get_delivery_address(company_id, customer_id, address_id)
        if address is None:
            raise NotFoundError(
                "No se encontró esa dirección de entrega.", code="customer_delivery_not_found"
            )
        return address

    async def delete_delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress:
        require_editable(await self.get_customer(company_id, customer_id))
        address = await self._delivery_or_404(company_id, customer_id, address_id)
        await self._repo.delete_delivery_address(company_id, customer_id, address_id)
        return address
