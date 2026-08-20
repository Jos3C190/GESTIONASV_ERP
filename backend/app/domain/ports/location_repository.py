"""Port used by the warehouse-location application service."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from app.domain.entities.location import (
    CodeProjection,
    LocationBatchRecord,
    LocationCodeScheme,
    LocationRecord,
    WarehouseLocationScope,
)


class LocationRepository(Protocol):
    async def get_warehouse_scope(self, warehouse_id: uuid.UUID) -> WarehouseLocationScope: ...

    async def get_batch_scope(self, job_id: uuid.UUID) -> WarehouseLocationScope: ...

    async def get_scheme(
        self, warehouse_id: uuid.UUID, version: int | None = None
    ) -> LocationCodeScheme: ...

    async def create_scheme_version(
        self,
        warehouse_id: uuid.UUID,
        *,
        name: str,
        separator: str,
        segments: Sequence[Mapping[str, Any]],
        actor_id: uuid.UUID,
    ) -> LocationCodeScheme: ...

    async def check_projection_conflicts(
        self,
        warehouse_id: uuid.UUID,
        projection: CodeProjection,
        *,
        exclude_location_id: uuid.UUID | None = None,
    ) -> tuple[bool, bool]: ...

    async def get_location(
        self,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> LocationRecord: ...

    async def create_location(
        self,
        warehouse_id: uuid.UUID,
        *,
        projection: CodeProjection,
        values: Mapping[str, Any],
        actor_id: uuid.UUID,
    ) -> LocationRecord: ...

    async def update_location(
        self,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        projection: CodeProjection,
        values: Mapping[str, Any],
        actor_id: uuid.UUID,
        expected_updated_at: Any | None = None,
    ) -> LocationRecord: ...

    async def list_locations(
        self,
        warehouse_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None,
        area: str | None,
        location_type: str | None,
        lifecycle_status: str | None,
        is_active: bool | None,
        capacity_group_id: uuid.UUID | None,
        include_descendants: bool,
        unassigned: bool,
    ) -> tuple[list[LocationRecord], int]: ...

    async def location_summary(self, warehouse_id: uuid.UUID) -> dict[str, Any]: ...

    async def create_batch_preview(
        self,
        warehouse_id: uuid.UUID,
        *,
        kind: str,
        idempotency_key: str,
        input_checksum: str,
        scheme: LocationCodeScheme,
        source_rows: Sequence[Mapping[str, Any]],
        actor_id: uuid.UUID,
    ) -> LocationBatchRecord: ...

    async def get_batch(
        self,
        job_id: uuid.UUID,
        *,
        page: int = 1,
        size: int = 100,
    ) -> LocationBatchRecord: ...

    async def batch_required_permissions(self, job_id: uuid.UUID) -> tuple[str, ...]: ...

    async def publish_batch(
        self, job_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> LocationBatchRecord: ...
