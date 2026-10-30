"""ERP labels on Traccar devices and geofences.

Devices are matched to fleet vehicles by the Traccar id stored in the ERP, never
by name. Geofences carry the company and, optionally, the branch they apply
to; a geofence without branch applies to the whole company.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.application.tracking.traccar import COMPANY_ATTRIBUTE

BRANCH_ATTRIBUTE = "erpBranchId"
VEHICLE_ATTRIBUTE = "erpVehicleId"

__all__ = [
    "BRANCH_ATTRIBUTE",
    "COMPANY_ATTRIBUTE",
    "VEHICLE_ATTRIBUTE",
    "device_body",
    "device_owner",
    "geofence_applies",
    "geofence_branch",
    "geofence_visible",
]


class _Scope(Protocol):
    @property
    def company_id(self) -> uuid.UUID: ...

    def allows(self, branch_id: uuid.UUID | None) -> bool: ...


def _attribute(item: dict[str, Any], key: str) -> str:
    return str((item.get("attributes") or {}).get(key, "")).strip().lower()


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def geofence_branch(item: dict[str, Any]) -> uuid.UUID | None:
    return _uuid(_attribute(item, BRANCH_ATTRIBUTE))


def geofence_visible(item: dict[str, Any], scope: _Scope) -> bool:
    """Company-wide geofences of the company, or those of a branch in scope."""
    if _attribute(item, COMPANY_ATTRIBUTE) != str(scope.company_id):
        return False
    branch = geofence_branch(item)
    return branch is None or scope.allows(branch)


def geofence_applies(item: dict[str, Any], company_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
    """Whether a vehicle based at ``branch_id`` must be linked to the geofence."""
    if _attribute(item, COMPANY_ATTRIBUTE) != str(company_id):
        return False
    branch = geofence_branch(item)
    return branch is None or branch == branch_id


def device_owner(item: dict[str, Any]) -> uuid.UUID | None:
    """Company a Traccar device was registered to by the ERP, if any."""
    return _uuid(_attribute(item, COMPANY_ATTRIBUTE))


def device_body(
    *,
    existing: dict[str, Any] | None,
    unique_id: str,
    code: str,
    plate: str,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    vehicle_id: uuid.UUID,
) -> dict[str, Any]:
    """Traccar device payload named after the fleet code, keeping foreign attributes."""
    attributes = dict((existing or {}).get("attributes") or {})
    attributes.update(
        {
            COMPANY_ATTRIBUTE: str(company_id),
            BRANCH_ATTRIBUTE: str(branch_id),
            VEHICLE_ATTRIBUTE: str(vehicle_id),
        }
    )
    body = dict(existing or {})
    body.update(
        {
            "name": code,
            "uniqueId": unique_id,
            "category": "truck",
            "contact": plate,
            "attributes": attributes,
        }
    )
    return body
