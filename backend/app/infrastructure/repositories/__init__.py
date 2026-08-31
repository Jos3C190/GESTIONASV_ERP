"""Concrete repositories. Importing this package wires the implementations."""
from app.infrastructure.repositories.audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.infrastructure.repositories.catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from app.infrastructure.repositories.department_repository import (
    SqlAlchemyDepartmentRepository,
)
from app.infrastructure.repositories.document_repository import SqlAlchemyDocumentRepository
from app.infrastructure.repositories.employee_repository import (
    SqlAlchemyEmployeeRepository,
)
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.lifecycle_repository import SqlAlchemyLifecycleRepository
from app.infrastructure.repositories.location_repository import SqlAlchemyLocationRepository
from app.infrastructure.repositories.operational_context_repository import (
    SqlAlchemyOperationalContextRepository,
)
from app.infrastructure.repositories.permission_repository import (
    SqlAlchemyPermissionRepository,
)
from app.infrastructure.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.repositories.role_repository import (
    SqlAlchemyRoleRepository,
)
from app.infrastructure.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from app.infrastructure.repositories.token_service import JwtTokenService
from app.infrastructure.repositories.user_repository import (
    SqlAlchemyUserRepository,
)

__all__ = [
    "JwtTokenService",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyCatalogRepository",
    "SqlAlchemyDepartmentRepository",
    "SqlAlchemyDocumentRepository",
    "SqlAlchemyEmployeeRepository",
    "SqlAlchemyInventoryRepository",
    "SqlAlchemyLifecycleRepository",
    "SqlAlchemyLocationRepository",
    "SqlAlchemyOperationalContextRepository",
    "SqlAlchemyPermissionRepository",
    "SqlAlchemyRefreshTokenRepository",
    "SqlAlchemyRoleRepository",
    "SqlAlchemySupplierRepository",
    "SqlAlchemyUserRepository",
]
