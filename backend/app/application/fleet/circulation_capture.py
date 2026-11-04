"""Guided capture of a circulation card: two photos, proposed values, human confirmation.

Confirming is the only way proposed values become the vehicle's card, and the server
repeats every check on what it receives. The card completes vehicle data that is
missing but never overwrites it: a difference is for a person to resolve.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.application.document_capture.sessions import CaptureConfig, CaptureSessions
from app.application.documents import DocumentMetadataInput, DocumentRecordService
from app.application.documents.service import DocumentService, UploadTicket
from app.application.fleet.circulation_rules import (
    CirculationCheck,
    CirculationFields,
    RegisteredVehicle,
    check_circulation_card,
    sides_look_swapped,
    tidy_extracted,
)
from app.application.fleet.license_capture import business_today
from app.application.fleet.license_rules import LicenseIssue
from app.application.fleet.vehicle_identifiers import normalize_serial, normalize_vin
from app.core.exceptions import ConflictError, ValidationError
from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.observability import record_counter
from app.infrastructure.repositories.fleet_repository import FleetRepository

_CONFIG = CaptureConfig(
    kind="circulation_card",
    owner_type="vehicle",
    file_prefix="tarjeta-circulacion",
    code_prefix="circulation_capture",
    cancel_action="CIRCULATION_CARD_CAPTURE_CANCELLED",
    resource_type="fleet_vehicles",
)


def fields_from_extracted(extracted: dict[str, Any] | None) -> CirculationFields:
    """Map what the model read on each side to the fields the rules understand."""
    data = extracted or {}
    front = (data.get("front") or {}).get("values") or {}
    back = (data.get("back") or {}).get("values") or {}
    return CirculationFields(
        plate=tidy_extracted(front.get("placa")),
        expires=tidy_extracted(front.get("vto")),
        issued=tidy_extracted(front.get("emision")),
        year=tidy_extracted(back.get("anio")),
        brand=tidy_extracted(back.get("marca")),
        model=tidy_extracted(back.get("modelo")),
        color=tidy_extracted(back.get("color")),
        chassis=tidy_extracted(back.get("chasis")),
        engine=tidy_extracted(back.get("motor")),
        vin=tidy_extracted(back.get("vin")),
    )


def _corrected_fields(proposed: CirculationFields, confirmed: CirculationFields) -> list[str]:
    return [
        item.name
        for item in fields(CirculationFields)
        if getattr(proposed, item.name) is not None
        and getattr(proposed, item.name) != getattr(confirmed, item.name)
    ]


def _registered(vehicle: FleetVehicleModel) -> RegisteredVehicle:
    return RegisteredVehicle(
        plate=vehicle.plate,
        year=vehicle.year,
        brand=vehicle.brand,
        model=vehicle.model,
        color=vehicle.color,
        vin=vehicle.vin,
    )


def _usable_vin(value: str | None) -> str | None:
    """A VIN the vehicle form would reject is not stored: the warning already flagged it."""
    try:
        return normalize_vin(value)
    except ValueError:
        return None


def _missing_data(vehicle: FleetVehicleModel, values: CirculationFields) -> dict[str, str]:
    """What the card can add to the vehicle: only columns still empty."""
    candidates = {
        "vin": _usable_vin(values.vin),
        "color": (values.color or "").strip() or None,
        "chassis_number": normalize_serial(values.chassis),
        "engine_number": normalize_serial(values.engine),
    }
    return {
        column: value
        for column, value in candidates.items()
        if value is not None and getattr(vehicle, column) is None
    }


@dataclass(frozen=True, slots=True)
class CirculationCaptureView:
    capture: DocumentCaptureModel
    front: DocumentAsset | None
    back: DocumentAsset | None
    values: CirculationFields
    issues: tuple[LicenseIssue, ...]
    #: Vehicle columns a confirmation would complete, so the review can say so.
    fills: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConfirmedCard:
    filled: tuple[str, ...]
    #: Data left out because the user may not edit the vehicle.
    skipped: tuple[str, ...]


class CirculationCaptureService:
    def __init__(
        self,
        session: AsyncSession,
        documents: DocumentService,
        records: DocumentRecordService,
        audit: AuditService,
    ) -> None:
        self._session = session
        self._records = records
        self._audit = audit
        self._sessions = CaptureSessions(session, documents, audit, _CONFIG)

    @staticmethod
    def _require_plate(vehicle: FleetVehicleModel) -> None:
        if not vehicle.plate:
            raise ConflictError(
                "Este vehículo no tiene placa; registra la placa antes de capturar su tarjeta.",
                code="circulation_capture_no_plate",
            )

    async def open(self, vehicle: FleetVehicleModel, actor_id: uuid.UUID) -> DocumentCaptureModel:
        self._require_plate(vehicle)
        return await self._sessions.open(vehicle.company_id, vehicle.id, actor_id)

    async def get_capture(
        self, vehicle: FleetVehicleModel, capture_id: uuid.UUID, *, lock: bool = False
    ) -> DocumentCaptureModel:
        return await self._sessions.get(vehicle.company_id, vehicle.id, capture_id, lock=lock)

    async def initiate_side(
        self,
        capture: DocumentCaptureModel,
        side: str,
        *,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str,
        actor_id: uuid.UUID,
    ) -> UploadTicket:
        return await self._sessions.initiate_side(
            capture,
            side,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            actor_id=actor_id,
        )

    async def complete_side(
        self, capture: DocumentCaptureModel, side: str, actor_id: uuid.UUID
    ) -> bool:
        return await self._sessions.complete_side(capture, side, actor_id)

    async def cancel(self, capture: DocumentCaptureModel, actor_id: uuid.UUID) -> None:
        await self._sessions.cancel(capture, actor_id)

    def check_values(
        self, vehicle: FleetVehicleModel, values: CirculationFields
    ) -> CirculationCheck:
        return check_circulation_card(values, _registered(vehicle), today=business_today())

    def fills(self, vehicle: FleetVehicleModel, values: CirculationFields) -> tuple[str, ...]:
        return tuple(_missing_data(vehicle, values))

    async def view(
        self, vehicle: FleetVehicleModel, capture: DocumentCaptureModel
    ) -> CirculationCaptureView:
        values = fields_from_extracted(capture.extracted)
        issues: tuple[LicenseIssue, ...] = ()
        if capture.extracted:
            issues = self.check_values(vehicle, values).issues
            if sides_look_swapped(values):
                issues = (
                    LicenseIssue(
                        "sides_swapped",
                        "warning",
                        "plate",
                        "Parece que el frente y el reverso están intercambiados.",
                    ),
                    *issues,
                )
        return CirculationCaptureView(
            capture,
            await self._sessions.asset(capture, "front"),
            await self._sessions.asset(capture, "back"),
            values,
            issues,
            self.fills(vehicle, values),
        )

    def _validate_confirmation(
        self, vehicle: FleetVehicleModel, values: CirculationFields, acknowledged: set[str]
    ) -> CirculationCheck:
        check = self.check_values(vehicle, values)
        if check.has_errors:
            raise ValidationError(
                " ".join(item.message for item in check.issues if item.severity == "error"),
                code=(
                    "circulation_capture_plate_mismatch"
                    if check.plate_differs
                    else "circulation_capture_invalid"
                ),
            )
        if not check.warning_codes <= acknowledged:
            raise ConflictError(
                "Revisa los avisos antes de confirmar.",
                code="circulation_capture_unacknowledged",
            )
        return check

    async def _complete_vehicle(
        self,
        vehicle: FleetVehicleModel,
        values: CirculationFields,
        *,
        actor_id: uuid.UUID,
        can_update_vehicle: bool,
    ) -> ConfirmedCard:
        missing = _missing_data(vehicle, values)
        if not missing:
            return ConfirmedCard((), ())
        # Un vehículo dado de baja no se edita, igual que en su formulario.
        if not can_update_vehicle or vehicle.status == "retired":
            return ConfirmedCard((), tuple(missing))
        if "vin" in missing:
            taken = await FleetRepository(self._session).conflicting_vehicle(
                vehicle.company_id, vin=missing["vin"], exclude_id=vehicle.id
            )
            if taken is not None:
                raise ConflictError(
                    "Ya existe otro vehículo con ese VIN en la empresa.",
                    code="vehicle_vin_taken",
                )
        for column, value in missing.items():
            setattr(vehicle, column, value)
        vehicle.updated_by = actor_id
        return ConfirmedCard(tuple(missing), ())

    async def confirm(
        self,
        vehicle: FleetVehicleModel,
        capture: DocumentCaptureModel,
        values: CirculationFields,
        *,
        actor_id: uuid.UUID,
        acknowledged: set[str],
        can_update_vehicle: bool,
    ) -> ConfirmedCard:
        self._sessions.require_open(capture)
        self._require_plate(vehicle)
        check = self._validate_confirmation(vehicle, values, acknowledged)
        assert check.expires_on is not None  # has_errors lo descartó
        if capture.front_document_id is None or capture.back_document_id is None:
            raise ConflictError(
                "Carga el frente y el reverso de la tarjeta.",
                code="circulation_capture_side_missing",
            )
        corrected = _corrected_fields(fields_from_extracted(capture.extracted), values)
        for field_name in corrected:
            record_counter(
                "erp.circulation_capture.field_corrections", attributes={"field": field_name}
            )
        async with self._session.begin_nested():
            result = await self._complete_vehicle(
                vehicle, values, actor_id=actor_id, can_update_vehicle=can_update_vehicle
            )
            await self._records.adopt_asset(
                capture.company_id,
                capture.front_document_id,
                actor_id,
                module="fleet",
                owner_type="vehicle",
                owner_id=vehicle.id,
                category_code="circulation_card",
                metadata=DocumentMetadataInput(
                    title="Tarjeta de circulación",
                    reference_code=vehicle.plate,
                    issued_on=check.issued_on,
                    expires_on=check.expires_on,
                    confidentiality="internal",
                ),
            )
            await self._records.adopt_asset(
                capture.company_id,
                capture.back_document_id,
                actor_id,
                module="fleet",
                owner_type="vehicle",
                owner_id=vehicle.id,
                category_code="circulation_card_back",
                metadata=DocumentMetadataInput(
                    title="Reverso de tarjeta de circulación",
                    reference_code=vehicle.plate,
                    confidentiality="internal",
                ),
            )
            capture.status = "confirmed"
            capture.extracted = None
            capture.confirmed_by = actor_id
            capture.confirmed_at = datetime.now(UTC)
            await self._session.flush()
            # Solo nombres de campos: los valores salen de un documento con datos del titular.
            await self._audit.record(
                action="CIRCULATION_CARD_CAPTURE_CONFIRMED",
                user_id=actor_id,
                company_id=capture.company_id,
                branch_id=vehicle.branch_id,
                resource_type="fleet_vehicles",
                resource_id=str(vehicle.id),
                after_state={
                    "capture_id": str(capture.id),
                    "document_id": str(capture.front_document_id),
                    "corrected_fields": corrected,
                    "filled_fields": list(result.filled),
                    "skipped_fields": list(result.skipped),
                    "acknowledged_warnings": sorted(check.warning_codes),
                },
                required=True,
            )
        return result
