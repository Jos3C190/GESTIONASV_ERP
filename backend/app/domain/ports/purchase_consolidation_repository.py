"""Persistence port for purchase-demand consolidations."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from app.domain.entities.purchase_consolidation import (
    ConsolidationQuotationStatusChange,
    ConsolidationWorkItem,
    PurchaseConsolidation,
    PurchaseConsolidationAward,
)


class PurchaseConsolidationRepository(Protocol):
    async def list_work_items(
        self,
        company_id: uuid.UUID,
        *,
        item_type: str | None,
        status: str | None,
        query: str | None,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        category_id: int | None,
        date_from: date | None,
        date_to: date | None,
        consolidation_id: uuid.UUID | None,
        skip: int,
        limit: int,
    ) -> tuple[list[ConsolidationWorkItem], int]: ...

    async def list_approved_requests(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
        query: str | None,
        skip: int,
        limit: int,
        request_ids: tuple[uuid.UUID, ...] = (),
    ) -> tuple[list[dict[str, object]], int]: ...

    async def resolve_selected_requests(
        self, company_id: uuid.UUID, request_ids: tuple[uuid.UUID, ...]
    ) -> list[dict[str, object]]: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def central_warehouse_available(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> bool: ...

    async def has_active_source(self, company_id: uuid.UUID, detail_id: uuid.UUID) -> bool: ...

    async def create(self, consolidation: PurchaseConsolidation) -> PurchaseConsolidation: ...

    async def get(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID, *, for_update: bool = False
    ) -> PurchaseConsolidation | None: ...

    async def save_draft(
        self,
        consolidation: PurchaseConsolidation,
        *,
        actor_id: uuid.UUID,
        change_reason: str,
    ) -> PurchaseConsolidation | None: ...

    async def cancel(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidation | None: ...

    async def close(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        coverage_basis: str = "awarded_in_consolidation",
        unawarded_lines: tuple[dict[str, object], ...] = (),
        quotation_status_changes: tuple[ConsolidationQuotationStatusChange, ...] = (),
    ) -> PurchaseConsolidation | None: ...

    async def list_awards(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> tuple[PurchaseConsolidationAward, ...]: ...

    async def create_award(
        self, award: PurchaseConsolidationAward
    ) -> PurchaseConsolidationAward | None: ...

    async def revoke_award(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        award_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidationAward | None: ...
