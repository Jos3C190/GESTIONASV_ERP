"""RBAC response-contract tests."""

from __future__ import annotations

import uuid

from app.api.v1.schemas.rbac import PermissionOut


def test_permission_out_marks_standard_catalogue_permissions_as_protected() -> None:
    permission = PermissionOut(
        id=uuid.uuid4(),
        code="users:read",
        description="Consultar usuarios",
        module="users",
    )

    assert permission.is_protected is True
    assert permission.model_dump()["is_protected"] is True


def test_permission_out_keeps_custom_permissions_editable() -> None:
    permission = PermissionOut(
        id=uuid.uuid4(),
        code="custom_reports:approve",
        description="Aprobar reportes personalizados",
        module="custom_reports",
    )

    assert permission.is_protected is False
    assert permission.model_dump()["is_protected"] is False
