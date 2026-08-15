"""API v1 router aggregation.

Phase 0: health. Phase 1: auth. Phase 1b: users. Phase 2: RBAC.
Phase 3: employees + departments. Phase 4: audit log (read-only).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    audit_logs,
    auth,
    catalog,
    dashboard,
    departments,
    employees,
    health,
    lifecycle,
    locations,
    media,
    operational_context,
    organization,
    roles,
    supplier_master,
    suppliers,
    users,
    workforce,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(users.router, prefix="/api/v1")
api_router.include_router(roles.router, prefix="/api/v1")
api_router.include_router(roles.me_router, prefix="/api/v1")
api_router.include_router(departments.router, prefix="/api/v1")
api_router.include_router(employees.router, prefix="/api/v1")
api_router.include_router(workforce.router, prefix="/api/v1")
api_router.include_router(audit_logs.router, prefix="/api/v1")
api_router.include_router(organization.router, prefix="/api/v1")
api_router.include_router(locations.router, prefix="/api/v1")
api_router.include_router(operational_context.router, prefix="/api/v1")
api_router.include_router(dashboard.router, prefix="/api/v1")
api_router.include_router(media.router, prefix="/api/v1")
api_router.include_router(catalog.router, prefix="/api/v1")
api_router.include_router(supplier_master.router, prefix="/api/v1")
api_router.include_router(suppliers.router, prefix="/api/v1")
api_router.include_router(lifecycle.router, prefix="/api/v1")
