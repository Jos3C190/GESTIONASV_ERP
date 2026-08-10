"""Audit durability policy tests."""

from __future__ import annotations

import pytest
from app.application.audit.audit_service import AuditService


class FailingAuditRepository:
    async def add(self, _log):
        raise RuntimeError("audit storage unavailable")


async def test_best_effort_audit_preserves_existing_noncritical_behavior() -> None:
    service = AuditService(FailingAuditRepository())

    await service.record(action="READ")


async def test_required_audit_propagates_failure_to_abort_lifecycle_transaction() -> None:
    service = AuditService(FailingAuditRepository())

    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        await service.record(action="LOGICAL_DELETE", required=True)
