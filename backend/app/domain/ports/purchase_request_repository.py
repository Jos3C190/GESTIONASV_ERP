"""Purchase-request persistence port and procurement reference projections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.purchase_request import PurchaseRequest, PurchaseRequestStatus


@dataclass(frozen=True, slots=True)
class PurchaseProductReference:
    """Minimal product data needed to validate one purchase-request line."""

    product_id: int
    purchase_unit_id: int
    is_active: bool
    lifecycle_status: str
    can_purchase: bool
    unit_enabled: bool


class PurchaseRequestRepository(Protocol):
    async def list_requests(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseRequestStatus | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseRequest], int]: ...

    async def get_request(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest | None: ...

    async def get_request_for_update(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseRequest | None: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def is_branch_available(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
    ) -> bool: ...

    async def is_warehouse_available(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> bool: ...

    async def get_product_reference(
        self,
        company_id: uuid.UUID,
        product_id: int,
    ) -> PurchaseProductReference | None: ...

    async def add_request(self, request: PurchaseRequest) -> PurchaseRequest: ...

    async def replace_draft(self, request: PurchaseRequest) -> PurchaseRequest | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        status: PurchaseRequestStatus,
    ) -> PurchaseRequest | None: ...
