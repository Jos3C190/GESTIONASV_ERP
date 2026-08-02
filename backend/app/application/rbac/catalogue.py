"""Permission catalogue — single source of truth for seed and validation.

Format: `recurso:accion`. Adding a new permission = adding a row here +
re-running `seed`. The catalogue is intentionally explicit (not introspected
from decorators) so it survives refactors and can be audited.

Grouped by module for the UI matrix.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionSpec:
    code: str
    description: str
    module: str


PERMISSION_CATALOGUE: Sequence[PermissionSpec] = (
    # --- users ---
    PermissionSpec("users:read", "Ver usuarios", "users"),
    PermissionSpec("users:create", "Crear usuarios", "users"),
    PermissionSpec("users:update", "Editar usuarios", "users"),
    PermissionSpec("users:deactivate", "Desactivar usuarios", "users"),
    PermissionSpec("users:force_password_reset", "Forzar reseteo de contraseña", "users"),
    PermissionSpec("users:unlock", "Desbloquear cuentas", "users"),
    # --- employees ---
    PermissionSpec("employees:read", "Ver empleados", "employees"),
    PermissionSpec("employees:create", "Crear empleados", "employees"),
    PermissionSpec("employees:update", "Editar empleados", "employees"),
    PermissionSpec("employees:delete", "Eliminar empleados", "employees"),
    PermissionSpec("media.upload", "Cargar imágenes", "media"),
    PermissionSpec("media.delete", "Eliminar imágenes", "media"),
    PermissionSpec("departments:manage", "Gestionar departamentos", "employees"),
    # --- roles ---
    PermissionSpec("roles:read", "Ver roles", "roles"),
    PermissionSpec("roles:create", "Crear roles", "roles"),
    PermissionSpec("roles:update", "Editar roles", "roles"),
    PermissionSpec("roles:delete", "Eliminar roles", "roles"),
    PermissionSpec("roles:assign", "Asignar roles a usuarios", "roles"),
    PermissionSpec("roles:revoke", "Revocar roles de usuarios", "roles"),
    PermissionSpec("permissions:read", "Ver catálogo de permisos", "roles"),
    PermissionSpec("permissions:manage", "Modificar matriz permiso-rol", "roles"),
    # --- audit ---
    PermissionSpec("audit_log:read", "Ver bitácora", "audit"),
    PermissionSpec("logs.view", "Consultar la bitácora", "audit"),
    PermissionSpec("logs.detail", "Consultar detalle de auditoría", "audit"),
    PermissionSpec("logs.export", "Exportar registros de auditoría", "audit"),
    # --- auth ---
    PermissionSpec("auth:refresh", "Renovar token (sistema)", "auth"),
    *tuple(
        PermissionSpec(f"{resource}.{action}", f"{action} {resource}", resource)
        for resource in ("companies", "branches", "warehouse_categories", "warehouses", "locations")
        for action in ("view", "create", "update", "activate", "deactivate")
    ),
)


# Convenience set for fast lookup
ALL_PERMISSION_CODES: frozenset[str] = frozenset(p.code for p in PERMISSION_CATALOGUE)


def permissions_by_module() -> dict[str, tuple[PermissionSpec, ...]]:
    out: dict[str, list[PermissionSpec]] = {}
    for p in PERMISSION_CATALOGUE:
        out.setdefault(p.module, []).append(p)
    return {k: tuple(v) for k, v in out.items()}


# Base roles and the permission codes they get by default (seed).
BASE_ROLES: tuple[tuple[str, str, bool, tuple[str, ...]], ...] = (
    (
        "SUPER_ADMIN",
        "Superadministrador con todos los permisos",
        True,
        tuple(ALL_PERMISSION_CODES),
    ),
    (
        "ADMINISTRADOR",
        "Administrador de usuarios y empleados",
        False,
        (
            "users:read",
            "users:create",
            "users:update",
            "users:deactivate",
            "users:force_password_reset",
            "users:unlock",
            "employees:read",
            "employees:create",
            "employees:update",
            "employees:delete",
            "media.upload",
            "media.delete",
            "departments:manage",
            "roles:read",
            "permissions:read",
            "audit_log:read",
            "logs.view",
            "logs.detail",
            "logs.export",
        ),
    ),
    (
        "RECURSOS_HUMANOS",
        "Recursos Humanos",
        False,
        (
            "employees:read",
            "employees:create",
            "employees:update",
            "employees:delete",
            "media.upload",
            "media.delete",
            "departments:manage",
            "users:read",
        ),
    ),
    (
        "EMPLEADO",
        "Empleado — autogestión de perfil",
        False,
        (),
    ),
)
