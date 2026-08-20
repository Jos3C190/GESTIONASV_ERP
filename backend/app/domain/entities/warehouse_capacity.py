"""Physical weight and usable-volume rules for warehouse storage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

CapacityProfile = Literal[
    "general_mixed",
    "rack",
    "bulk_floor",
    "cold",
    "oversize_manual",
    "transit",
]
CapacityEnforcementMode = Literal["disabled", "observe", "enforce"]
CapacityStatus = Literal[
    "not_configured",
    "incomplete",
    "available",
    "warning",
    "critical",
    "full",
    "over_operational",
    "over_certified",
]

CAPACITY_PROFILES: frozenset[str] = frozenset(
    {
        "general_mixed",
        "rack",
        "bulk_floor",
        "cold",
        "oversize_manual",
        "transit",
    }
)
CAPACITY_ENFORCEMENT_MODES: frozenset[str] = frozenset({"disabled", "observe", "enforce"})


@dataclass(frozen=True, slots=True)
class PhysicalCapacity:
    """Certified and operational limits for one physical storage scope.

    Certified limits are safety ceilings. Operational limits are the lower
    day-to-day ceilings used by the warehouse. No inventory usage is modeled
    here; :attr:`status` only reports configuration completeness.
    """

    certified_max_weight_kg: Decimal | float | None = None
    operational_max_weight_kg: Decimal | float | None = None
    certified_usable_volume_m3: Decimal | float | None = None
    operational_usable_volume_m3: Decimal | float | None = None
    capacity_profile: CapacityProfile = "general_mixed"
    capacity_enforcement_mode: CapacityEnforcementMode = "disabled"
    storage_eligible: bool = True
    usable_length_m: Decimal | float | None = None
    usable_width_m: Decimal | float | None = None
    usable_height_m: Decimal | float | None = None

    def __post_init__(self) -> None:  # noqa: C901 - one cohesive physical invariant matrix
        if self.capacity_profile not in CAPACITY_PROFILES:
            raise ValueError("El perfil de capacidad no es válido.")
        if self.capacity_enforcement_mode not in CAPACITY_ENFORCEMENT_MODES:
            raise ValueError("El modo de control de capacidad no es válido.")

        metrics = {
            "El peso certificado": self.certified_max_weight_kg,
            "El peso operativo": self.operational_max_weight_kg,
            "El volumen útil certificado": self.certified_usable_volume_m3,
            "El volumen útil operativo": self.operational_usable_volume_m3,
            "El largo útil": self.usable_length_m,
            "El ancho útil": self.usable_width_m,
            "El alto útil": self.usable_height_m,
        }
        for label, value in metrics.items():
            if value is not None and value <= 0:
                raise ValueError(f"{label} debe ser mayor que cero.")

        if self.operational_max_weight_kg is not None and self.certified_max_weight_kg is None:
            raise ValueError("El peso operativo requiere un peso certificado.")
        if (
            self.operational_usable_volume_m3 is not None
            and self.certified_usable_volume_m3 is None
        ):
            raise ValueError("El volumen operativo requiere un volumen certificado.")
        if (
            self.operational_max_weight_kg is not None
            and self.certified_max_weight_kg is not None
            and self.operational_max_weight_kg > self.certified_max_weight_kg
        ):
            raise ValueError("El peso operativo no puede superar el certificado.")
        if (
            self.operational_usable_volume_m3 is not None
            and self.certified_usable_volume_m3 is not None
            and self.operational_usable_volume_m3 > self.certified_usable_volume_m3
        ):
            raise ValueError("El volumen operativo no puede superar el certificado.")

        dimensions = (self.usable_length_m, self.usable_width_m, self.usable_height_m)
        if any(value is not None for value in dimensions) and not all(
            value is not None for value in dimensions
        ):
            raise ValueError("Las dimensiones útiles deben registrarse completas.")
        if not self.storage_eligible and self.capacity_enforcement_mode != "disabled":
            raise ValueError(
                "Una ubicación no almacenable debe tener desactivado el control de capacidad."
            )
        if self.capacity_enforcement_mode == "enforce" and not self.complete:
            raise ValueError(
                "El modo enforce requiere límites certificados y operativos de peso y volumen."
            )

    @property
    def configured(self) -> bool:
        return any(
            value is not None
            for value in (
                self.certified_max_weight_kg,
                self.operational_max_weight_kg,
                self.certified_usable_volume_m3,
                self.operational_usable_volume_m3,
            )
        )

    @property
    def complete(self) -> bool:
        return self.storage_eligible and all(
            value is not None
            for value in (
                self.certified_max_weight_kg,
                self.operational_max_weight_kg,
                self.certified_usable_volume_m3,
                self.operational_usable_volume_m3,
            )
        )

    @property
    def status(self) -> CapacityStatus:
        if not self.storage_eligible or not self.configured:
            return "not_configured"
        return "available" if self.complete else "incomplete"


def capacity_status_for(resource: object) -> CapacityStatus:
    """Derive configuration status from a warehouse or location-like object."""

    return PhysicalCapacity(
        certified_max_weight_kg=getattr(resource, "certified_max_weight_kg", None),
        operational_max_weight_kg=getattr(resource, "operational_max_weight_kg", None),
        certified_usable_volume_m3=getattr(resource, "certified_usable_volume_m3", None),
        operational_usable_volume_m3=getattr(resource, "operational_usable_volume_m3", None),
        capacity_profile=getattr(resource, "capacity_profile", "general_mixed"),
        capacity_enforcement_mode=getattr(resource, "capacity_enforcement_mode", "disabled"),
        storage_eligible=bool(getattr(resource, "storage_eligible", True)),
        usable_length_m=getattr(resource, "usable_length_m", None),
        usable_width_m=getattr(resource, "usable_width_m", None),
        usable_height_m=getattr(resource, "usable_height_m", None),
    ).status


def occupancy_without_inventory(resource: object | None = None) -> dict[str, object | None]:
    """Return an explicit unknown occupancy snapshot.

    Master-data endpoints can expose capacity configuration before the inventory
    ledger is queried.  Unknown occupancy must stay ``None``; treating it as
    zero would falsely present an empty warehouse.  When a resource is supplied,
    the status is derived solely from its physical-capacity configuration.
    """

    result: dict[str, object | None] = {
        "occupied_weight_kg": None,
        "reserved_weight_kg": None,
        "projected_weight_kg": None,
        "available_operational_weight_kg": None,
        "weight_utilization_pct": None,
        "occupied_volume_m3": None,
        "reserved_volume_m3": None,
        "projected_volume_m3": None,
        "available_operational_volume_m3": None,
        "volume_utilization_pct": None,
        "effective_utilization_pct": None,
        "limiting_dimension": None,
        "occupancy_data_status": "not_loaded",
    }
    if resource is not None:
        result["capacity_status"] = capacity_status_for(resource)
    return result
