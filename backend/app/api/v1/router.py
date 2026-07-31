"""API v1 router aggregation.

Phase 0: health. Phase 1: auth. Phase 1b: users. Phase 2: RBAC.
Phase 3: employees + departments. Phase 4: audit log (read-only).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import audit_logs, auth, departments, employees, health, organization, roles, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(users.router, prefix="/api/v1")
api_router.include_router(roles.router, prefix="/api/v1")
api_router.include_router(roles.me_router, prefix="/api/v1")
api_router.include_router(departments.router, prefix="/api/v1")
api_router.include_router(employees.router, prefix="/api/v1")
api_router.include_router(audit_logs.router, prefix="/api/v1")
api_router.include_router(organization.router, prefix="/api/v1")
