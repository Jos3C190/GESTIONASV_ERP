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
from app.infrastructure.repositories.employee_repository import (
    SqlAlchemyEmployeeRepository,
)
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
    "SqlAlchemyUserRepository",
    "SqlAlchemyRefreshTokenRepository",
    "SqlAlchemyRoleRepository",
    "SqlAlchemyPermissionRepository",
    "SqlAlchemyDepartmentRepository",
    "SqlAlchemyEmployeeRepository",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyOperationalContextRepository",
    "SqlAlchemyCatalogRepository",
    "SqlAlchemySupplierRepository",
    "JwtTokenService",
]
