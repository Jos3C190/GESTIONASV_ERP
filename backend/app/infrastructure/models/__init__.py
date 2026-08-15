"""ORM models package. Importing this module registers all tables on
`Base.metadata`.
"""

from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    CountryModel,
    ProductModel,
    SubCategoryModel,
    UnitModel,
)
from app.infrastructure.models.employee import (
    Department,
    DepartmentBranchAssignment,
    Employee,
    EmployeeBranchAssignment,
)
from app.infrastructure.models.location import (
    LocationBatchJob,
    LocationBatchRow,
    LocationCodeAlias,
    LocationCodeScheme,
)
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Location,
    Municipality,
    UserBranch,
    UserCompany,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.product_image import ProductImageModel
from app.infrastructure.models.rbac import (
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel
from app.infrastructure.models.supplier_image import SupplierContactImageModel, SupplierImageModel
from app.infrastructure.models.system import AppMeta
from app.infrastructure.models.user import User

__all__: list[str] = [
    "AppMeta",
    "AuditLog",
    "Branch",
    "CategoryModel",
    "Company",
    "CompanyUnitModel",
    "CountryModel",
    "Department",
    "DepartmentBranchAssignment",
    "District",
    "Employee",
    "EmployeeBranchAssignment",
    "GeographicDepartment",
    "Location",
    "LocationBatchJob",
    "LocationBatchRow",
    "LocationCodeAlias",
    "LocationCodeScheme",
    "MediaAsset",
    "Municipality",
    "PasswordResetToken",
    "Permission",
    "ProductImageModel",
    "ProductModel",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SubCategoryModel",
    "SupplierContactImageModel",
    "SupplierContactModel",
    "SupplierImageModel",
    "SupplierModel",
    "UnitModel",
    "User",
    "UserBranch",
    "UserCompany",
    "UserRole",
    "Warehouse",
    "WarehouseCategory",
]
