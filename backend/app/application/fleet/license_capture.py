"""Guided capture of a driver's license: two photos, proposed values, human confirmation.

Photos are assets without a document record until the capture is confirmed, so
compliance cannot see them. Confirming is the only way proposed values become
the employee's license, and the server repeats every check on what it receives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.application.document_capture.sessions import CaptureConfig, CaptureSessions
from app.application.documents import DocumentMetadataInput, DocumentRecordService
from app.application.documents.service import DocumentService, UploadTicket
from app.application.fleet.compliance import license_issue
from app.application.fleet.license_rules import (
    EmployeeIdentity,
    LicenseCheck,
    LicenseFields,
    LicenseIssue,
    check_license,
    sides_look_swapped,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel
from app.infrastructure.observability import record_counter
from app.infrastructure.repositories.fleet_repository import FleetRepository

OVERRIDE_PERMISSION = "drivers:license_override"
MIN_REASON_LENGTH = 3
_BUSINESS_TZ = ZoneInfo("America/El_Salvador")
_CONFIG = CaptureConfig(
    kind="driver_license",
    owner_type="driver",
    file_prefix="licencia",
    code_prefix="license_capture",
    cancel_action="DRIVER_LICENSE_CAPTURE_CANCELLED",
    resource_type="drivers",
)


def business_today() -> Any:
    return datetime.now(_BUSINESS_TZ).date()


def fields_from_extracted(extracted: dict[str, Any] | None) -> LicenseFields:
    """Map what the model read on each side to the fields the rules understand."""
    data = extracted or {}
    front = (data.get("front") or {}).get("values") or {}
    back = (data.get("back") or {}).get("values") or {}
    return LicenseFields(
        license_class=front.get("clase"),
        expires=front.get("vence"),
        number=front.get("numero"),
        surnames=front.get("nombre_linea_1"),
        given_names=front.get("nombre_linea_2"),
        dui=front.get("dui"),
        issued=back.get("expedicion"),
        birth=back.get("nacimiento"),
        control_number=back.get("numero_control"),
    )


def _corrected_fields(proposed: LicenseFields, confirmed: LicenseFields) -> list[str]:
    return [
        item.name
        for item in fields(LicenseFields)
        if getattr(proposed, item.name) is not None
        and getattr(proposed, item.name) != getattr(confirmed, item.name)
    ]


@dataclass(frozen=True, slots=True)
class CaptureView:
    capture: DocumentCaptureModel
    front: DocumentAsset | None
    back: DocumentAsset | None
    values: LicenseFields
    issues: tuple[LicenseIssue, ...]


class LicenseCaptureService:
    def __init__(
        self,
        session: AsyncSession,
        documents: DocumentService,
        records: DocumentRecordService,
        audit: AuditService,
    ) -> None:
        self._session = session
        self._documents = documents
        self._records = records
        self._audit = audit
        self._sessions = CaptureSessions(session, documents, audit, _CONFIG)

    async def open(self, driver: DriverModel, actor_id: uuid.UUID) -> DocumentCaptureModel:
        """Resume the driver's open capture, or start one."""
        return await self._sessions.open(driver.company_id, driver.id, actor_id)

    async def get_capture(
        self, driver: DriverModel, capture_id: uuid.UUID, *, lock: bool = False
    ) -> DocumentCaptureModel:
        return await self._sessions.get(driver.company_id, driver.id, capture_id, lock=lock)

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
        """Scan the uploaded photo. Returns whether the capture now awaits extraction."""
        return await self._sessions.complete_side(capture, side, actor_id)

    async def _identity(self, driver: DriverModel) -> EmployeeIdentity:
        employee = await self._session.get(Employee, driver.employee_id)
        if employee is None:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
        return EmployeeIdentity(
            first_name=employee.first_name,
            last_name=employee.last_name,
            document_id=employee.document_id,
            birth_date=employee.birth_date,
        )

    async def view(self, driver: DriverModel, capture: DocumentCaptureModel) -> CaptureView:
        values = fields_from_extracted(capture.extracted)
        issues: tuple[LicenseIssue, ...] = ()
        if capture.extracted:
            check = check_license(values, await self._identity(driver), today=business_today())
            issues = check.issues
            if sides_look_swapped(values):
                issues = (
                    LicenseIssue(
                        "sides_swapped",
                        "warning",
                        "number",
                        "Parece que el frente y el reverso están intercambiados.",
                    ),
                    *issues,
                )
        return CaptureView(
            capture,
            await self._sessions.asset(capture, "front"),
            await self._sessions.asset(capture, "back"),
            values,
            issues,
        )

    async def check_values(self, driver: DriverModel, values: LicenseFields) -> LicenseCheck:
        return check_license(values, await self._identity(driver), today=business_today())

    async def _validate_confirmation(
        self,
        driver: DriverModel,
        values: LicenseFields,
        *,
        acknowledged: set[str],
        override_reason: str | None,
        can_override: bool,
    ) -> tuple[LicenseCheck, str | None]:
        check = check_license(values, await self._identity(driver), today=business_today())
        if check.has_errors:
            raise ValidationError(
                " ".join(item.message for item in check.issues if item.severity == "error"),
                code="license_capture_invalid",
            )
        reason = (override_reason or "").strip() or None
        if check.has_mismatches:
            if not can_override:
                raise AuthorizationError(
                    "Los datos no coinciden con el empleado; requiere autorización.",
                    code="license_capture_override_required",
                )
            if reason is None or len(reason) < MIN_REASON_LENGTH:
                raise ValidationError(
                    "Indica el motivo de la excepción.", code="license_capture_reason_required"
                )
        if not check.warning_codes <= acknowledged:
            raise ConflictError(
                "Revisa los avisos antes de confirmar.", code="license_capture_unacknowledged"
            )
        return check, reason

    async def _ensure_class_change_allowed(
        self, driver: DriverModel, license_class: str, *, can_update_driver: bool
    ) -> None:
        if license_class == driver.license_class:
            return
        if not can_update_driver:
            raise AuthorizationError(
                "Cambiar la clase de licencia requiere permiso para editar conductores.",
                code="license_class_change_forbidden",
            )
        repo = FleetRepository(self._session)
        vehicle = (await repo.open_vehicles_for_drivers([driver.id])).get(driver.id)
        rules = await repo.license_rules(driver.company_id)
        if vehicle is not None and license_issue(license_class, vehicle["kind"], rules) is not None:
            raise ConflictError(
                f"La nueva clase de licencia no permite conducir {vehicle['code']}; "
                "finalice la asignación primero.",
                code="license_class_incompatible",
            )

    async def confirm(
        self,
        driver: DriverModel,
        capture: DocumentCaptureModel,
        values: LicenseFields,
        *,
        actor_id: uuid.UUID,
        acknowledged: set[str],
        override_reason: str | None,
        can_override: bool,
        can_update_driver: bool,
    ) -> None:
        self._sessions.require_open(capture)
        check, reason = await self._validate_confirmation(
            driver,
            values,
            acknowledged=acknowledged,
            override_reason=override_reason,
            can_override=can_override,
        )
        assert check.license_class is not None  # has_errors lo descartó
        if capture.front_document_id is None or capture.back_document_id is None:
            raise ConflictError(
                "Carga el frente y el reverso de la licencia.", code="license_capture_side_missing"
            )
        await self._ensure_class_change_allowed(
            driver, check.license_class, can_update_driver=can_update_driver
        )
        corrected = _corrected_fields(fields_from_extracted(capture.extracted), values)
        for field_name in corrected:
            record_counter(
                "erp.license_capture.field_corrections", attributes={"field": field_name}
            )
        async with self._session.begin_nested():
            await self._records.adopt_asset(
                capture.company_id,
                capture.front_document_id,
                actor_id,
                module="employees",
                owner_type="employee",
                owner_id=driver.employee_id,
                category_code="driver_license",
                metadata=DocumentMetadataInput(
                    title="Licencia de conducir",
                    reference_code=values.number,
                    issued_on=check.issued_on,
                    expires_on=check.expires_on,
                    confidentiality="internal",
                ),
            )
            await self._records.adopt_asset(
                capture.company_id,
                capture.back_document_id,
                actor_id,
                module="employees",
                owner_type="employee",
                owner_id=driver.employee_id,
                category_code="driver_license_back",
                # Lleva datos de salud: en Conductores solo lo ve quien gestiona licencias.
                metadata=DocumentMetadataInput(
                    title="Reverso de licencia de conducir",
                    reference_code=values.control_number,
                    confidentiality="restricted",
                ),
            )
            driver.license_class = check.license_class
            driver.updated_by = actor_id
            capture.status = "confirmed"
            capture.extracted = None
            capture.confirmed_by = actor_id
            capture.confirmed_at = datetime.now(UTC)
            await self._session.flush()
            await self._audit.record(
                action="DRIVER_LICENSE_CAPTURE_CONFIRMED",
                user_id=actor_id,
                company_id=capture.company_id,
                branch_id=driver.branch_id,
                resource_type="drivers",
                resource_id=str(driver.id),
                after_state={
                    "capture_id": str(capture.id),
                    "document_id": str(capture.front_document_id),
                    "corrected_fields": corrected,
                    "acknowledged_warnings": sorted(check.warning_codes),
                    "mismatches": sorted(
                        item.code for item in check.issues if item.severity == "mismatch"
                    ),
                    "override_reason": reason,
                },
                required=True,
            )

    async def cancel(self, capture: DocumentCaptureModel, actor_id: uuid.UUID) -> None:
        await self._sessions.cancel(capture, actor_id)
