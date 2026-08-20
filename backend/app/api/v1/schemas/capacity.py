"""Shared API contracts for certified weight and usable-volume capacity."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.entities.warehouse_capacity import (
    CapacityEnforcementMode,
    CapacityProfile,
    CapacityStatus,
    PhysicalCapacity,
)


class CapacityConfigurationIn(BaseModel):
    certified_max_weight_kg: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    operational_max_weight_kg: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    certified_usable_volume_m3: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    operational_usable_volume_m3: Decimal | None = Field(
        None, gt=0, max_digits=18, decimal_places=6
    )
    capacity_profile: CapacityProfile = "general_mixed"
    capacity_enforcement_mode: CapacityEnforcementMode = "disabled"
    storage_eligible: bool = True
    usable_length_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    usable_width_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    usable_height_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)

    @model_validator(mode="after")
    def validate_physical_capacity(self) -> CapacityConfigurationIn:
        PhysicalCapacity(
            certified_max_weight_kg=self.certified_max_weight_kg,
            operational_max_weight_kg=self.operational_max_weight_kg,
            certified_usable_volume_m3=self.certified_usable_volume_m3,
            operational_usable_volume_m3=self.operational_usable_volume_m3,
            capacity_profile=self.capacity_profile,
            capacity_enforcement_mode=self.capacity_enforcement_mode,
            storage_eligible=self.storage_eligible,
            usable_length_m=self.usable_length_m,
            usable_width_m=self.usable_width_m,
            usable_height_m=self.usable_height_m,
        )
        return self


class CapacityConfigurationOut(CapacityConfigurationIn):
    capacity_status: CapacityStatus


class CapacityConfigurationIssueOut(BaseModel):
    severity: Literal["error", "warning"]
    code: Literal[
        "capacity_child_limit_exceeds_parent",
        "parent_limit_not_configured",
        "nominal_capacity_overallocated",
    ]
    scope_type: Literal["warehouse", "capacity_group", "location"]
    scope_id: str
    parent_scope_type: Literal["warehouse", "capacity_group"] | None
    parent_scope_id: str | None
    metric: Literal["weight", "volume"]
    limit_kind: Literal["certified", "operational"]
    child_limit: Decimal | None = None
    parent_limit: Decimal | None = None
    allocated_children_total: Decimal | None = None
    allocation_ratio_pct: Decimal | None = None


class CapacityConfigurationDiagnosticsOut(BaseModel):
    warehouse_id: uuid.UUID
    issues: list[CapacityConfigurationIssueOut]
