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
    PermissionSpec("users:delete", "Eliminar usuarios lógicamente", "users"),
    PermissionSpec("users:restore", "Restaurar usuarios eliminados", "users"),
    PermissionSpec("users:force_password_reset", "Forzar reseteo de contraseña", "users"),
    PermissionSpec("users:unlock", "Desbloquear cuentas", "users"),
    # --- employees ---
    PermissionSpec("employees:read", "Ver empleados", "employees"),
    PermissionSpec("employees:create", "Crear empleados", "employees"),
    PermissionSpec("employees:update", "Editar empleados", "employees"),
    PermissionSpec("employees:delete", "Eliminar empleados", "employees"),
    PermissionSpec("employees:restore", "Restaurar empleados eliminados", "employees"),
    PermissionSpec("media.upload", "Cargar imágenes", "media"),
    PermissionSpec("media.delete", "Eliminar imágenes", "media"),
    PermissionSpec("departments:manage", "Gestionar departamentos", "employees"),
    PermissionSpec("departments:delete", "Eliminar departamentos lógicamente", "employees"),
    PermissionSpec("departments:restore", "Restaurar departamentos eliminados", "employees"),
    # --- commercial masters ---
    PermissionSpec("reference_data:read", "Consultar catálogos de referencia", "catalog"),
    PermissionSpec("products:read", "Ver productos y sus categorías", "products"),
    PermissionSpec("products:manage", "Gestionar productos y sus categorías", "products"),
    PermissionSpec("products:images", "Gestionar la galería de imágenes de productos", "products"),
    PermissionSpec("products:delete", "Eliminar productos lógicamente", "products"),
    PermissionSpec("products:restore", "Restaurar productos eliminados", "products"),
    PermissionSpec("product_categories:delete", "Eliminar categorías de productos", "products"),
    PermissionSpec("product_categories:restore", "Restaurar categorías de productos", "products"),
    PermissionSpec("units:read", "Consultar unidades de medida", "units"),
    PermissionSpec("units:create", "Crear unidades personalizadas", "units"),
    PermissionSpec("units:update", "Editar unidades personalizadas", "units"),
    PermissionSpec("units:activate", "Activar unidades para una empresa", "units"),
    PermissionSpec("units:deactivate", "Desactivar unidades para una empresa", "units"),
    PermissionSpec("units:delete", "Eliminar unidades personalizadas", "units"),
    PermissionSpec("units:restore", "Restaurar unidades personalizadas", "units"),
    PermissionSpec("units:manage_global", "Administrar el catálogo global de unidades", "units"),
    PermissionSpec("suppliers:read", "Ver proveedores", "suppliers"),
    PermissionSpec("suppliers:manage", "Gestionar proveedores y contactos", "suppliers"),
    PermissionSpec("suppliers:images", "Gestionar imágenes de proveedores y contactos", "suppliers"),
    PermissionSpec("suppliers:delete", "Eliminar proveedores y contactos", "suppliers"),
    PermissionSpec("suppliers:restore", "Restaurar proveedores y contactos", "suppliers"),
    # --- roles ---
    PermissionSpec("roles:read", "Ver roles", "roles"),
    PermissionSpec("roles:create", "Crear roles", "roles"),
    PermissionSpec("roles:update", "Editar roles", "roles"),
    PermissionSpec("roles:delete", "Eliminar roles", "roles"),
    PermissionSpec("roles:restore", "Restaurar roles eliminados", "roles"),
    PermissionSpec("roles:assign", "Asignar roles a usuarios", "roles"),
    PermissionSpec("roles:revoke", "Revocar roles de usuarios", "roles"),
    PermissionSpec("permissions:read", "Ver catálogo de permisos", "roles"),
    PermissionSpec("permissions:manage", "Modificar matriz permiso-rol", "roles"),
    PermissionSpec("permissions:delete", "Eliminar permisos personalizados", "roles"),
    PermissionSpec("permissions:restore", "Restaurar permisos personalizados", "roles"),
    PermissionSpec("lifecycle:read", "Consultar la papelera administrativa", "administration"),
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
        for action in ("view", "create", "update", "activate", "deactivate", "delete", "restore")
    ),
    PermissionSpec("locations.scheme", "Versionar esquemas de códigos de ubicación", "locations"),
    PermissionSpec("locations.bulk", "Generar y publicar ubicaciones por lotes", "locations"),
    PermissionSpec("locations.import", "Importar ubicaciones desde CSV o XLSX", "locations"),
    PermissionSpec("locations.export", "Exportar ubicaciones", "locations"),
    PermissionSpec("locations.recode", "Renumerar ubicaciones conservando alias", "locations"),
    PermissionSpec("locations.labels", "Generar etiquetas de ubicación", "locations"),
    PermissionSpec("locations.commission", "Comisionar y retirar ubicaciones", "locations"),
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
            "users:delete",
            "users:restore",
            "users:force_password_reset",
            "users:unlock",
            "employees:read",
            "employees:create",
            "employees:update",
            "employees:delete",
            "employees:restore",
            "media.upload",
            "media.delete",
            "departments:manage",
            "departments:delete",
            "departments:restore",
            "reference_data:read",
            "products:read",
            "products:manage",
            "products:images",
            "products:delete",
            "products:restore",
            "product_categories:delete",
            "product_categories:restore",
            "units:read",
            "units:create",
            "units:update",
            "units:activate",
            "units:deactivate",
            "units:delete",
            "units:restore",
            "suppliers:read",
            "suppliers:manage",
            "suppliers:images",
            "suppliers:delete",
            "suppliers:restore",
            "roles:read",
            "roles:restore",
            "permissions:read",
            "lifecycle:read",
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
            "departments:delete",
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
