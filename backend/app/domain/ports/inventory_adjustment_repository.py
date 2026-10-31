"""Explicit persistence contract shared by adapters and application services."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol


class InventoryAdjustmentRepository(Protocol):
    async def list_options(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        q: str = "",
        limit: int | None = None,
        offset: int = 0,
        include_items: bool = True,
        include_locations: bool = True,
    ) -> dict[str, Any]: ...

    async def create_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        operational_date: date,
        accounting_date: date,
        reason: str,
        document_reference: str,
        notes: str | None,
        lines: list[dict[str, Any]],
        idempotency_key: str | None = None,
        correction_of_id: uuid.UUID | None = None,
        transfer_id: uuid.UUID | None = None,
        transfer_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    async def update_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        operational_date: date,
        accounting_date: date,
        reason: str,
        document_reference: str,
        notes: str | None,
        lines: list[dict[str, Any]],
        approval_revocation_reason: str | None = None,
    ) -> dict[str, Any]: ...

    async def approve_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
    ) -> dict[str, Any]: ...

    async def cancel_adjustment(
        self, *, company_id: uuid.UUID, adjustment_id: uuid.UUID, actor_id: uuid.UUID, reason: str
    ) -> dict[str, Any]: ...

    async def apply_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> dict[str, Any]: ...

    async def create_correction(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        document_reference: str,
        operational_date: date,
        accounting_date: date,
    ) -> dict[str, Any]: ...

    async def get_adjustment(
        self, company_id: uuid.UUID, adjustment_id: uuid.UUID
    ) -> dict[str, Any] | None: ...

    async def list_adjustments(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
        allowed_warehouse_ids: list[uuid.UUID] | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...
