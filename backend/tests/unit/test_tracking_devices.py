import uuid
from dataclasses import dataclass, field

from app.application.tracking.devices import (
    device_body,
    device_owner,
    geofence_applies,
    geofence_visible,
)

COMPANY = uuid.UUID("8f6c1a52-3d0b-4c39-9a51-1e2f5f7a9b10")
BRANCH_A = uuid.uuid4()
BRANCH_B = uuid.uuid4()


@dataclass
class Scope:
    company_id: uuid.UUID = COMPANY
    branches: set[uuid.UUID] = field(default_factory=lambda: {BRANCH_A})

    def allows(self, branch_id: uuid.UUID | None) -> bool:
        return branch_id in self.branches


def _geofence(company: uuid.UUID | str, branch: uuid.UUID | None = None) -> dict[str, object]:
    attributes = {"erpCompanyId": str(company)}
    if branch is not None:
        attributes["erpBranchId"] = str(branch)
    return {"id": 1, "attributes": attributes}


def test_branch_user_sees_company_and_own_branch_geofences_only() -> None:
    scope = Scope()
    assert geofence_visible(_geofence(COMPANY), scope)
    assert geofence_visible(_geofence(COMPANY, BRANCH_A), scope)
    assert not geofence_visible(_geofence(COMPANY, BRANCH_B), scope)
    assert not geofence_visible(_geofence(uuid.uuid4()), scope)


def test_geofence_links_vehicles_of_its_branch_or_whole_company() -> None:
    assert geofence_applies(_geofence(COMPANY), COMPANY, BRANCH_B)
    assert geofence_applies(_geofence(COMPANY, BRANCH_A), COMPANY, BRANCH_A)
    assert not geofence_applies(_geofence(COMPANY, BRANCH_A), COMPANY, BRANCH_B)


def test_device_body_labels_device_and_keeps_foreign_attributes() -> None:
    vehicle_id = uuid.uuid4()
    body = device_body(
        existing={"id": 7, "attributes": {"speedLimit": 40}},
        unique_id="358240051111110",
        code="FL-001",
        plate="C 123",
        company_id=COMPANY,
        branch_id=BRANCH_A,
        vehicle_id=vehicle_id,
    )
    assert body["id"] == 7
    assert body["name"] == "FL-001"
    assert body["attributes"]["speedLimit"] == 40
    assert body["attributes"]["erpVehicleId"] == str(vehicle_id)
    assert device_owner(body) == COMPANY
    assert device_owner({"attributes": {}}) is None
