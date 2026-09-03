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
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_derivative import DocumentDerivativeModel
from app.infrastructure.models.document_record import DocumentCategoryModel, DocumentRecordModel
from app.infrastructure.models.employee import (
    Department,
    DepartmentBranchAssignment,
    Employee,
    EmployeeBranchAssignment,
)
from app.infrastructure.models.inventory import (
    CapacityOperationalOverrideModel,
    CapacityReservationModel,
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
    InventoryPackagingModel,
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
    WarehouseCapacityGroup,
    WarehouseCategory,
)
from app.infrastructure.models.product_image import ProductImageModel
from app.infrastructure.models.product_master import (
    ProductBrandModel,
    ProductIdentifierModel,
    ProductManufacturerModel,
    ProductSupplierModel,
)
from app.infrastructure.models.product_variant import (
    ProductFamilyAttributeModel,
    ProductFamilyAttributeValueModel,
    ProductSkuRegistryModel,
    ProductVariantAttributeValueModel,
    ProductVariantImageModel,
    ProductVariantModel,
)
from app.infrastructure.models.rbac import (
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel
from app.infrastructure.models.supplier_image import SupplierContactImageModel, SupplierImageModel
from app.infrastructure.models.supplier_master_data import (
    CurrencyModel,
    PaymentTermsModel,
    SupplierAddressModel,
    SupplierBankAccountModel,
    SupplierGroupModel,
    SupplierTaxIdentifierModel,
)
from app.infrastructure.models.system import AppMeta
from app.infrastructure.models.user import User

__all__: list[str] = [
    "AppMeta",
    "AuditLog",
    "Branch",
    "CapacityOperationalOverrideModel",
    "CapacityReservationModel",
    "CategoryModel",
    "Company",
    "CompanyUnitModel",
    "CountryModel",
    "CurrencyModel",
    "Department",
    "DepartmentBranchAssignment",
    "District",
    "DocumentAssetModel",
    "DocumentCategoryModel",
    "DocumentDerivativeModel",
    "DocumentRecordModel",
    "Employee",
    "EmployeeBranchAssignment",
    "GeographicDepartment",
    "InventoryBalanceModel",
    "InventoryHandlingUnitModel",
    "InventoryItemModel",
    "InventoryMovementLineModel",
    "InventoryMovementModel",
    "InventoryPackagingModel",
    "Location",
    "LocationBatchJob",
    "LocationBatchRow",
    "LocationCodeAlias",
    "LocationCodeScheme",
    "MediaAsset",
    "Municipality",
    "PasswordResetToken",
    "PaymentTermsModel",
    "Permission",
    "ProductBrandModel",
    "ProductFamilyAttributeModel",
    "ProductFamilyAttributeValueModel",
    "ProductIdentifierModel",
    "ProductImageModel",
    "ProductManufacturerModel",
    "ProductModel",
    "ProductSkuRegistryModel",
    "ProductSupplierModel",
    "ProductVariantAttributeValueModel",
    "ProductVariantImageModel",
    "ProductVariantModel",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SubCategoryModel",
    "SupplierAddressModel",
    "SupplierBankAccountModel",
    "SupplierContactImageModel",
    "SupplierContactModel",
    "SupplierGroupModel",
    "SupplierImageModel",
    "SupplierModel",
    "SupplierTaxIdentifierModel",
    "UnitModel",
    "User",
    "UserBranch",
    "UserCompany",
    "UserRole",
    "Warehouse",
    "WarehouseCapacityGroup",
    "WarehouseCategory",
]
