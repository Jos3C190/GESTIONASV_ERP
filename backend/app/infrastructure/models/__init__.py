"""ORM models package. Importing this module registers all tables on
`Base.metadata`.
"""

from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken
from app.infrastructure.models.branch_product_demand import BranchProductDemandLevelModel
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
from app.infrastructure.models.document_general_entry import (
    DocumentGeneralDeletionBatchModel,
    DocumentGeneralEntryModel,
)
from app.infrastructure.models.document_general_import import (
    DocumentGeneralImportItemModel,
    DocumentGeneralImportModel,
)
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
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDetailModel,
    InventoryAdjustmentDocumentModel,
    InventoryAdjustmentEventModel,
    InventoryAdjustmentModel,
)
from app.infrastructure.models.inventory_label import InventoryLabelPrintModel
from app.infrastructure.models.inventory_label_confirmation import InventoryLabelConfirmationModel
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.inventory_preparation import InventoryPreparationActionModel
from app.infrastructure.models.inventory_trace_capability import (
    InventoryTraceCapabilityModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferCommandModel,
    InventoryTransferDemandAllocationModel,
    InventoryTransferDetailModel,
    InventoryTransferIncidentModel,
    InventoryTransferModel,
    InventoryTransferReceiptModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryRetaceoApplicationModel,
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
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
from app.infrastructure.models.purchase import PurchaseDetailModel, PurchaseModel
from app.infrastructure.models.purchase_consolidation import (
    PurchaseConsolidationAwardModel,
    PurchaseConsolidationEventModel,
    PurchaseConsolidationLineModel,
    PurchaseConsolidationModel,
    PurchaseConsolidationSourceModel,
)
from app.infrastructure.models.purchase_order import (
    PurchaseOrderDetailModel,
    PurchaseOrderExpenseModel,
    PurchaseOrderModel,
)
from app.infrastructure.models.purchase_quotation import (
    ExpenseTypeModel,
    PurchaseQuotationDetailModel,
    PurchaseQuotationDocumentModel,
    PurchaseQuotationExpenseModel,
    PurchaseQuotationLineSnapshotModel,
    PurchaseQuotationModel,
    PurchaseQuotationRequestDetailModel,
    PurchaseQuotationRequestModel,
)
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.models.rbac import (
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from app.infrastructure.models.retaceo import (
    RetaceoCostAllocationModel,
    RetaceoCostDocumentModel,
    RetaceoCostModel,
    RetaceoDetailModel,
    RetaceoModel,
)
from app.infrastructure.models.sales import (
    SaleLineModel,
    SaleModel,
    SalesCustomerModel,
    SalesIdempotencyModel,
    SalesQuotationLineModel,
    SalesQuotationModel,
)
from app.infrastructure.models.sales_delivery import (
    SalesDeliveryAllocationModel,
    SalesDeliveryCommandModel,
    SalesDeliveryLineModel,
    SalesDeliveryModel,
)
from app.infrastructure.models.sales_return import (
    SalesReturnCommandModel,
    SalesReturnDocumentModel,
    SalesReturnEventModel,
    SalesReturnLineModel,
    SalesReturnModel,
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
    "BranchProductDemandLevelModel",
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
    "DocumentGeneralDeletionBatchModel",
    "DocumentGeneralEntryModel",
    "DocumentGeneralImportItemModel",
    "DocumentGeneralImportModel",
    "DocumentRecordModel",
    "Employee",
    "EmployeeBranchAssignment",
    "ExpenseTypeModel",
    "GeographicDepartment",
    "InventoryAdjustmentDetailModel",
    "InventoryAdjustmentDocumentModel",
    "InventoryAdjustmentEventModel",
    "InventoryAdjustmentModel",
    "InventoryBalanceModel",
    "InventoryCostAverageModel",
    "InventoryHandlingUnitModel",
    "InventoryItemModel",
    "InventoryLabelConfirmationModel",
    "InventoryLabelPrintModel",
    "InventoryLotDetailModel",
    "InventoryLotModel",
    "InventoryMovementLineModel",
    "InventoryMovementModel",
    "InventoryPackagingModel",
    "InventoryPreparationActionModel",
    "InventoryRetaceoApplicationModel",
    "InventoryTraceCapabilityModel",
    "InventoryTransferCommandModel",
    "InventoryTransferDemandAllocationModel",
    "InventoryTransferDetailModel",
    "InventoryTransferIncidentModel",
    "InventoryTransferModel",
    "InventoryTransferReceiptModel",
    "InventoryValuationEntryModel",
    "InventoryValuationSettingModel",
    "InventoryVehicleModel",
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
    "PurchaseConsolidationAwardModel",
    "PurchaseConsolidationEventModel",
    "PurchaseConsolidationLineModel",
    "PurchaseConsolidationModel",
    "PurchaseConsolidationSourceModel",
    "PurchaseDetailModel",
    "PurchaseModel",
    "PurchaseOrderDetailModel",
    "PurchaseOrderExpenseModel",
    "PurchaseOrderModel",
    "PurchaseQuotationDetailModel",
    "PurchaseQuotationDocumentModel",
    "PurchaseQuotationExpenseModel",
    "PurchaseQuotationLineSnapshotModel",
    "PurchaseQuotationModel",
    "PurchaseQuotationRequestDetailModel",
    "PurchaseQuotationRequestModel",
    "PurchaseRequestDetailModel",
    "PurchaseRequestModel",
    "RefreshToken",
    "RetaceoCostAllocationModel",
    "RetaceoCostDocumentModel",
    "RetaceoCostModel",
    "RetaceoDetailModel",
    "RetaceoModel",
    "Role",
    "RolePermission",
    "SaleLineModel",
    "SaleModel",
    "SalesCustomerModel",
    "SalesDeliveryAllocationModel",
    "SalesDeliveryCommandModel",
    "SalesDeliveryLineModel",
    "SalesDeliveryModel",
    "SalesIdempotencyModel",
    "SalesQuotationLineModel",
    "SalesQuotationModel",
    "SalesReturnCommandModel",
    "SalesReturnDocumentModel",
    "SalesReturnEventModel",
    "SalesReturnLineModel",
    "SalesReturnModel",
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
