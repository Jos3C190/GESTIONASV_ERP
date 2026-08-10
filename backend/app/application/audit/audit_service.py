"""AuditService — helper to record audit log entries.

Use cases call `AuditService.record(...)` after a successful (or failed) action.
The service creates an AuditLog and persists it via the AuditRepository.
Telemetry is best-effort by default; regulated lifecycle mutations opt into a
strict transactional append with ``required=True``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.domain.entities.audit import AuditLog
from app.domain.ports.audit_repository import AuditRepository

log = get_logger(__name__)


class AuditService:
    def __init__(self, repo: AuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
        required: bool = False,
    ) -> None:
        """Append an audit entry, optionally as a transactional requirement.

        Most telemetry remains best-effort. Regulated lifecycle mutations pass
        ``required=True`` so a failed append aborts their database transaction.
        """
        try:
            entry = AuditLog(
                id=uuid.uuid4(),
                user_id=user_id,
                company_id=company_id,
                branch_id=branch_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                before_state=before_state,
                after_state=after_state,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                metadata=metadata,
                created_at=datetime.now(UTC),
            )
            await self._repo.add(entry)
        except Exception as exc:
            log.warning("audit_record_failed", action=action, error=str(exc))
            if required:
                raise


def user_to_audit_state(user: object) -> dict[str, Any]:
    """Serialize a User domain entity to a JSON-safe dict for audit before/after."""
    return {
        "id": str(getattr(user, "id", "")),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "is_active": getattr(user, "is_active", None),
        "is_superuser": getattr(user, "is_superuser", None),
    }


def employee_to_audit_state(emp: object) -> dict[str, Any]:
    return {
        "id": str(getattr(emp, "id", "")),
        "company_id": str(getattr(emp, "company_id", "")),
        "user_id": str(getattr(emp, "user_id", "") or "") or None,
        "employee_code": getattr(emp, "employee_code", None),
        "first_name": getattr(emp, "first_name", None),
        "last_name": getattr(emp, "last_name", None),
        "document_id": getattr(emp, "document_id", None),
        "birth_date": (
            getattr(emp, "birth_date", None).isoformat()
            if getattr(emp, "birth_date", None)
            else None
        ),
        "phone": getattr(emp, "phone", None),
        "address": getattr(emp, "address", None),
        "department_id": str(getattr(emp, "department_id", "")) or None,
        "position": getattr(emp, "position", None),
        "hire_date": (
            getattr(emp, "hire_date", None).isoformat() if getattr(emp, "hire_date", None) else None
        ),
        "termination_date": (
            getattr(emp, "termination_date", None).isoformat()
            if getattr(emp, "termination_date", None)
            else None
        ),
        "status": str(getattr(emp, "status", "")),
        "photo_url": getattr(emp, "photo_url", None),
    }


def department_to_audit_state(department: object) -> dict[str, Any]:
    return {
        "id": str(getattr(department, "id", "")),
        "company_id": str(getattr(department, "company_id", "")),
        "name": getattr(department, "name", None),
        "description": getattr(department, "description", None),
        "parent_department_id": (
            str(getattr(department, "parent_department_id", "") or "") or None
        ),
    }


def role_to_audit_state(role: object) -> dict[str, Any]:
    return {
        "id": str(getattr(role, "id", "")),
        "name": getattr(role, "name", None),
        "is_system": getattr(role, "is_system", None),
    }
