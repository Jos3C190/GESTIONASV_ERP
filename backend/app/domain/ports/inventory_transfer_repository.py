"""Explicit persistence contract shared by adapters and application services."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.domain.entities.inventory_transfer import TransferPolicy


class InventoryTransferRepository(Protocol):
    async def create_transfer(
        self,
        *,
        company_id: uuid.UUID,
        origin_warehouse_id: uuid.UUID,
        destination_warehouse_id: uuid.UUID,
        lines: list[dict[str, Any]],
        idempotency_key: str,
        actor_id: uuid.UUID,
        notes: str | None = None,
        vehicle_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    async def update_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        lines: list[dict[str, Any]],
        origin_warehouse_id: uuid.UUID | None = None,
        destination_warehouse_id: uuid.UUID | None = None,
        vehicle_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]: ...

    async def cancel_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    async def submit_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    async def withdraw_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    async def approve_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        expected_round: int,
        allow_self_approval: bool = False,
    ) -> dict[str, Any]: ...

    async def reject_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        expected_round: int,
        reason: str,
        allow_self_approval: bool = False,
    ) -> dict[str, Any]: ...

    async def dispatch_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        driver_id: uuid.UUID | None = None,
        compliance_override_reason: str | None = None,
    ) -> dict[str, Any]: ...

    async def receive_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        lines: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def open_incident(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        reason: str,
        evidence_reference: str | None = None,
    ) -> dict[str, Any]: ...

    async def resolve_incident(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        resolution: str,
        resolution_notes: str,
    ) -> dict[str, Any]: ...

    async def get_transfer(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> dict[str, Any] | None: ...

    async def list_transfers(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        branch_ids: list[uuid.UUID] | None = None,
        status_filter: str | None = None,
        route_type: str | None = None,
        side: str | None = None,
        awaiting_approval_by: uuid.UUID | None = None,
        allow_self_approval: bool = False,
        approver_branch_ids: list[uuid.UUID] | None = None,
        page: int = 1,
        size: int = 50,
    ) -> list[dict[str, Any]]: ...

    async def get_policy(self, company_id: uuid.UUID) -> TransferPolicy: ...

    async def route_options(
        self,
        *,
        company_id: uuid.UUID,
        can_move: bool,
        branch_ids: list[uuid.UUID] | None = None,
        warehouse_ids: list[uuid.UUID] | None = None,
        origin_warehouse_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    async def pending_approval_count(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_self_approval: bool = False,
        approver_branch_ids: list[uuid.UUID] | None = None,
    ) -> int: ...

    async def list_demand(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        product_id: int | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...

    async def create_vehicle(
        self, *, company_id: uuid.UUID, code: str, name: str, actor_id: uuid.UUID
    ) -> dict[str, Any]: ...

    async def list_vehicles(
        self, company_id: uuid.UUID, branch_ids: list[uuid.UUID] | None = None
    ) -> list[dict[str, Any]]: ...

    async def set_vehicle_status(
        self, *, company_id: uuid.UUID, vehicle_id: uuid.UUID, status: str
    ) -> dict[str, Any]: ...
