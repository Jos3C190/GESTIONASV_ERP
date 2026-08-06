"""ORM models package. Importing this module registers all tables on
`Base.metadata`.
"""

from app.infrastructure.models.audit import AuditLog  # noqa: F401
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken  # noqa: F401
from app.infrastructure.models.catalog import (  # noqa: F401
    CategoryModel, CountryModel, ProductModel, SubCategoryModel, UnitModel,
)
from app.infrastructure.models.employee import Department, DepartmentBranchAssignment, Employee, EmployeeBranchAssignment  # noqa: F401
from app.infrastructure.models.media import MediaAsset  # noqa: F401
from app.infrastructure.models.organization import (  # noqa: F401
    Branch, Company, District, GeographicDepartment, Location, Municipality,
    UserBranch, UserCompany, Warehouse, WarehouseCategory,
)
from app.infrastructure.models.rbac import (  # noqa: F401
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel  # noqa: F401
from app.infrastructure.models.user import User  # noqa: F401

__all__: list[str] = [
    "User",
    "RefreshToken",
    "PasswordResetToken",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "Department",
    "Employee",
    "EmployeeBranchAssignment",
    "DepartmentBranchAssignment",
    "AuditLog",
    "GeographicDepartment", "Municipality", "District", "Company", "Branch",
    "WarehouseCategory", "Warehouse", "Location", "UserCompany", "UserBranch",
    "MediaAsset",
    "CountryModel",
    "CategoryModel",
    "SubCategoryModel",
    "UnitModel",
    "ProductModel",
    "SupplierModel",
    "SupplierContactModel",
]
