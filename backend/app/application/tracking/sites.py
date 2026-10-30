"""Fixed places of a company on the tracking map: branches and warehouses.

The ERP is the only source: a branch is a point where it has coordinates; a
warehouse shares its branch's point unless it sits in another building with
its own coordinates. Each point also has an automatic arrival/departure
geofence in Traccar, reconciled from these same rules.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.application.tracking.devices import COMPANY_ATTRIBUTE
from app.application.tracking.geofences import build_area

SITE_TYPE_ATTRIBUTE = "erpSiteType"
SITE_ID_ATTRIBUTE = "erpSiteId"
#: Branches and warehouses in these states are real, operating places.
VISIBLE_STATUSES = frozenset({"active", "maintenance"})
DEFAULT_RADIUS_M = 150

__all__ = [
    "SITE_ID_ATTRIBUTE",
    "SITE_TYPE_ATTRIBUTE",
    "Site",
    "SitePlan",
    "build_sites",
    "effective_location",
    "is_site_geofence",
    "plan_site_geofences",
    "site_geofence_body",
]


@dataclass(slots=True)
class Site:
    kind: str  # "branch" | "warehouse"
    id: uuid.UUID
    name: str
    code: str | None
    address: str | None
    latitude: float
    longitude: float
    radius_m: int
    status: str
    branch_id: uuid.UUID
    branch_name: str
    warehouses: list[dict[str, Any]] = field(default_factory=list)


def _visible(record: Any) -> bool:
    return (
        bool(getattr(record, "is_active", True))
        and getattr(record, "deleted_at", None) is None
        and record.operational_status in VISIBLE_STATUSES
    )


def _coords(record: Any) -> tuple[float, float] | None:
    if record.latitude is None or record.longitude is None:
        return None
    return float(record.latitude), float(record.longitude)


def effective_location(warehouse: Any, branch: Any | None) -> tuple[float, float, int] | None:
    """Where a warehouse physically is: its own building or its branch's point."""
    if warehouse.location_mode == "own":
        own = _coords(warehouse)
        if own is None:
            return None
        return own[0], own[1], int(warehouse.geofence_radius_m or DEFAULT_RADIUS_M)
    if branch is None:
        return None
    point = _coords(branch)
    if point is None:
        return None
    return point[0], point[1], int(branch.geofence_radius_m or DEFAULT_RADIUS_M)


def _warehouse_summary(warehouse: Any) -> dict[str, Any]:
    return {
        "id": warehouse.id,
        "name": warehouse.name,
        "code": warehouse.code,
        "is_central": bool(warehouse.is_central),
        "status": warehouse.operational_status,
    }


def build_sites(
    branches: Sequence[Any], warehouses: Iterable[Any]
) -> tuple[list[Site], list[dict[str, Any]]]:
    """Points to draw and the places that cannot be drawn for lack of coordinates."""
    by_id = {branch.id: branch for branch in branches if _visible(branch)}
    sites: dict[uuid.UUID, Site] = {}
    missing: list[dict[str, Any]] = []
    for branch in by_id.values():
        point = _coords(branch)
        if point is None:
            missing.append({"kind": "branch", "id": branch.id, "name": branch.name})
            continue
        sites[branch.id] = Site(
            kind="branch",
            id=branch.id,
            name=branch.name,
            code=branch.code,
            address=branch.address,
            latitude=point[0],
            longitude=point[1],
            radius_m=int(branch.geofence_radius_m or DEFAULT_RADIUS_M),
            status=branch.operational_status,
            branch_id=branch.id,
            branch_name=branch.name,
        )
    own: list[Site] = []
    for warehouse in warehouses:
        branch = by_id.get(warehouse.branch_id)
        # Los almacenes de tránsito son los vehículos; los de sucursales ocultas no se muestran.
        if warehouse.is_transit or branch is None or not _visible(warehouse):
            continue
        if warehouse.location_mode == "own":
            point = _coords(warehouse)
            if point is None:
                missing.append({"kind": "warehouse", "id": warehouse.id, "name": warehouse.name})
                continue
            own.append(
                Site(
                    kind="warehouse",
                    id=warehouse.id,
                    name=warehouse.name,
                    code=warehouse.code,
                    address=warehouse.physical_location,
                    latitude=point[0],
                    longitude=point[1],
                    radius_m=int(warehouse.geofence_radius_m or DEFAULT_RADIUS_M),
                    status=warehouse.operational_status,
                    branch_id=branch.id,
                    branch_name=branch.name,
                    warehouses=[_warehouse_summary(warehouse)],
                )
            )
        elif branch.id in sites:
            sites[branch.id].warehouses.append(_warehouse_summary(warehouse))
        else:
            missing.append({"kind": "warehouse", "id": warehouse.id, "name": warehouse.name})
    ordered = sorted(sites.values(), key=lambda site: site.name.lower())
    ordered += sorted(own, key=lambda site: site.name.lower())
    for site in ordered:
        site.warehouses.sort(key=lambda item: (not item["is_central"], item["name"].lower()))
    return ordered, sorted(missing, key=lambda item: (item["kind"], item["name"].lower()))


def _label(site: Site) -> str:
    return f"{'Sucursal' if site.kind == 'branch' else 'Almacén'} {site.name}"


def site_geofence_body(site: Site, company_id: uuid.UUID) -> dict[str, Any]:
    """Traccar geofence for a site: company-wide (no branch) so every vehicle reports it."""
    return {
        "name": _label(site),
        "description": site.address or "",
        "area": build_area(
            {
                "type": "circle",
                "center": [site.longitude, site.latitude],
                "radius_m": site.radius_m,
            }
        ),
        "attributes": {
            COMPANY_ATTRIBUTE: str(company_id),
            SITE_TYPE_ATTRIBUTE: site.kind,
            SITE_ID_ATTRIBUTE: str(site.id),
        },
    }


def is_site_geofence(item: dict[str, Any]) -> bool:
    return bool(str((item.get("attributes") or {}).get(SITE_ID_ATTRIBUTE, "")).strip())


@dataclass(slots=True)
class SitePlan:
    create: list[dict[str, Any]] = field(default_factory=list)
    update: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.create or self.update or self.delete)


def plan_site_geofences(
    desired: Sequence[dict[str, Any]], existing: Sequence[dict[str, Any]]
) -> SitePlan:
    """Changes that make the company's site geofences in Traccar match the ERP.

    ``existing`` holds only the company's site geofences. Duplicates of one site
    (e.g. after an interrupted sync) keep the first and delete the rest.
    """
    plan = SitePlan()
    current: dict[str, dict[str, Any]] = {}
    for item in existing:
        key = str((item.get("attributes") or {}).get(SITE_ID_ATTRIBUTE, ""))
        if key in current:
            plan.delete.append(int(item["id"]))
        else:
            current[key] = item
    wanted = {body["attributes"][SITE_ID_ATTRIBUTE]: body for body in desired}
    for key, body in wanted.items():
        found = current.get(key)
        if found is None:
            plan.create.append(body)
        elif any(
            (found.get(field) or "") != (body[field] or "")
            for field in ("name", "description", "area")
        ) or (
            (found.get("attributes") or {}).get(SITE_TYPE_ATTRIBUTE)
            != body["attributes"][SITE_TYPE_ATTRIBUTE]
        ):
            attributes = {**(found.get("attributes") or {}), **body["attributes"]}
            plan.update.append((int(found["id"]), {**found, **body, "attributes": attributes}))
    plan.delete.extend(int(item["id"]) for key, item in current.items() if key not in wanted)
    return plan
