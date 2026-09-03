"""SQLAlchemy implementation of the enterprise record lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.ports.lifecycle_repository import DeletedRecord
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    ProductModel,
    SubCategoryModel,
    UnitModel,
)
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_record import DocumentRecordModel
from app.infrastructure.models.employee import (
    Department,
    DepartmentBranchAssignment,
    Employee,
    EmployeeBranchAssignment,
)
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.organization import (
    Branch,
    Company,
    Location,
    UserBranch,
    UserCompany,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel
from app.infrastructure.models.supplier_image import SupplierContactImageModel, SupplierImageModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.capacity_hierarchy_repository import (
    SqlAlchemyCapacityHierarchyRepository,
)


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    model: type[Any]
    id_attribute: str
    label_attributes: tuple[str, ...]
    scope: str


RESOURCE_POLICIES: dict[str, ResourcePolicy] = {
    "companies": ResourcePolicy(Company, "id", ("commercial_name",), "self"),
    "branches": ResourcePolicy(Branch, "id", ("name",), "company"),
    "warehouse_categories": ResourcePolicy(WarehouseCategory, "id", ("name",), "company"),
    "warehouses": ResourcePolicy(Warehouse, "id", ("name",), "warehouse"),
    "locations": ResourcePolicy(Location, "id", ("code",), "location"),
    "departments": ResourcePolicy(Department, "id", ("name",), "company"),
    "employees": ResourcePolicy(Employee, "id", ("first_name", "last_name"), "company"),
    "users": ResourcePolicy(User, "id", ("username",), "user"),
    "roles": ResourcePolicy(Role, "id", ("name",), "company"),
    "permissions": ResourcePolicy(Permission, "id", ("code",), "global"),
    "product_categories": ResourcePolicy(CategoryModel, "id_category", ("name",), "company"),
    "product_subcategories": ResourcePolicy(
        SubCategoryModel, "id_sub_category", ("name",), "company"
    ),
    "units": ResourcePolicy(UnitModel, "id_unit", ("name",), "unit"),
    "products": ResourcePolicy(ProductModel, "id_product", ("name",), "company"),
    "suppliers": ResourcePolicy(SupplierModel, "id_supplier", ("name",), "company"),
    "supplier_contacts": ResourcePolicy(
        SupplierContactModel, "id_supplier_contact", ("full_name",), "supplier_contact"
    ),
    "documents": ResourcePolicy(DocumentAssetModel, "id", ("original_filename",), "company"),
}


class SqlAlchemyLifecycleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _policy(resource: str) -> ResourcePolicy:
        policy = RESOURCE_POLICIES.get(resource)
        if policy is None:
            raise NotFoundError(
                "El tipo de registro no admite eliminación lógica.",
                code="lifecycle_resource_not_found",
            )
        return policy

    @staticmethod
    def _label(policy: ResourcePolicy, record: Any) -> str:
        return " ".join(
            str(value).strip()
            for attribute in policy.label_attributes
            if (value := getattr(record, attribute, None))
        ) or str(getattr(record, policy.id_attribute))

    @staticmethod
    def _parse_id(policy: ResourcePolicy, raw_id: str) -> uuid.UUID | int:
        column = getattr(policy.model, policy.id_attribute).property.columns[0]
        try:
            return uuid.UUID(raw_id) if column.type.python_type is uuid.UUID else int(raw_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise NotFoundError(
                "Registro no encontrado.", code="lifecycle_record_not_found"
            ) from exc

    async def _get(self, resource: str, record_id: str) -> tuple[ResourcePolicy, Any]:
        policy = self._policy(resource)
        parsed_id = self._parse_id(policy, record_id)
        stmt = (
            select(policy.model)
            .where(getattr(policy.model, policy.id_attribute) == parsed_id)
            .with_for_update()
            .execution_options(include_deleted=True)
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise NotFoundError("Registro no encontrado.", code="lifecycle_record_not_found")
        return policy, record

    async def _record_company_id(  # noqa: PLR0911
        self, policy: ResourcePolicy, record: Any
    ) -> uuid.UUID | None:
        if policy.scope == "self":
            return record.id
        if policy.scope == "company":
            return record.company_id
        if policy.scope == "warehouse":
            return await self._session.scalar(
                select(Branch.company_id)
                .join(Warehouse, Warehouse.branch_id == Branch.id)
                .where(Warehouse.id == record.id)
                .execution_options(include_deleted=True)
            )
        if policy.scope == "location":
            return await self._session.scalar(
                select(Branch.company_id)
                .join(Warehouse, Warehouse.branch_id == Branch.id)
                .join(Location, Location.warehouse_id == Warehouse.id)
                .where(Location.id == record.id)
                .execution_options(include_deleted=True)
            )
        if policy.scope == "supplier_contact":
            return await self._session.scalar(
                select(SupplierModel.company_id)
                .join(
                    SupplierContactModel,
                    SupplierContactModel.id_supplier == SupplierModel.id_supplier,
                )
                .where(SupplierContactModel.id_supplier_contact == record.id_supplier_contact)
                .execution_options(include_deleted=True)
            )
        if policy.scope == "unit":
            return record.owner_company_id
        if policy.scope == "global":
            return None
        return None

    async def _assert_scope(
        self,
        policy: ResourcePolicy,
        record: Any,
        company_id: uuid.UUID,
        *,
        allow_global: bool,
    ) -> uuid.UUID | None:
        if policy.scope == "global":
            if not allow_global:
                raise NotFoundError("Registro no encontrado.", code="lifecycle_record_not_found")
            return None
        if policy.scope == "user":
            membership = await self._session.scalar(
                select(UserCompany.user_id).where(
                    UserCompany.user_id == record.id,
                    UserCompany.company_id == company_id,
                )
            )
            if membership is None:
                raise NotFoundError("Registro no encontrado.", code="lifecycle_record_not_found")
            return company_id
        # Los roles del sistema son globales y visibles en el catálogo de cada
        # empresa. Dejarlos llegar a la política de dependencias permite devolver
        # un conflicto de negocio legible, sin tratarlos como roles editables del
        # tenant ni hacer posible su eliminación.
        if policy.model is Role and record.company_id is None and record.is_system:
            return company_id
        actual_company_id = await self._record_company_id(policy, record)
        if actual_company_id != company_id:
            raise NotFoundError("Registro no encontrado.", code="lifecycle_record_not_found")
        return actual_company_id

    async def _exists(self, model: type[Any], *conditions: Any) -> bool:
        stmt = select(1).select_from(model).where(*conditions).limit(1)
        return (await self._session.scalar(stmt)) is not None

    async def _detach_supplier_image(self, resource: str, record: Any) -> None:
        """Detach supplier media when a supplier/contact enters the trash.

        Lifecycle deletion is intentionally the single place that handles soft
        deletion across modules.  Removing the relation here prevents an asset
        from remaining active and owned by a record that normal application
        queries no longer expose.  The Cloudinary object itself is left for the
        existing detached-asset cleaner.
        """
        if resource == "suppliers":
            image = await self._session.scalar(
                select(SupplierImageModel).where(
                    SupplierImageModel.supplier_id == record.id_supplier
                )
            )
        elif resource == "supplier_contacts":
            image = await self._session.scalar(
                select(SupplierContactImageModel).where(
                    SupplierContactImageModel.supplier_contact_id == record.id_supplier_contact
                )
            )
        else:
            return
        if image is None:
            return
        if image.media_asset_id is not None:
            asset = await self._session.get(MediaAsset, image.media_asset_id)
            if asset is not None and asset.status != "deleted":
                asset.status = "detached"
                asset.owner_type = None
                asset.owner_id = None
        await self._session.delete(image)

    async def _deletion_blockers(  # noqa: C901
        self,
        resource: str,
        record: Any,
        actor_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        allow_global: bool,
    ) -> list[str]:
        blockers: list[str] = []
        checks: tuple[tuple[type[Any], Any, str], ...]
        if resource == "companies":
            checks = (
                (Branch, Branch.company_id == record.id, "sucursales"),
                (Department, Department.company_id == record.id, "departamentos"),
                (Employee, Employee.company_id == record.id, "empleados"),
                (Role, Role.company_id == record.id, "roles personalizados"),
                (
                    WarehouseCategory,
                    WarehouseCategory.company_id == record.id,
                    "categorías de almacén",
                ),
                (CategoryModel, CategoryModel.company_id == record.id, "categorías de productos"),
                (ProductModel, ProductModel.company_id == record.id, "productos"),
                (SupplierModel, SupplierModel.company_id == record.id, "proveedores"),
                (UnitModel, UnitModel.owner_company_id == record.id, "unidades personalizadas"),
            )
            for model, condition, label in checks:
                if await self._exists(model, condition):
                    blockers.append(label)
        elif resource == "branches":
            checks = (
                (Warehouse, Warehouse.branch_id == record.id, "almacenes"),
                (
                    EmployeeBranchAssignment,
                    (
                        (EmployeeBranchAssignment.branch_id == record.id)
                        & EmployeeBranchAssignment.is_active.is_(True)
                        & EmployeeBranchAssignment.assigned_until.is_(None)
                    ),
                    "asignaciones de empleados",
                ),
                (
                    DepartmentBranchAssignment,
                    (
                        (DepartmentBranchAssignment.branch_id == record.id)
                        & DepartmentBranchAssignment.is_active.is_(True)
                        & DepartmentBranchAssignment.closed_at.is_(None)
                    ),
                    "asignaciones de departamentos",
                ),
                (
                    UserBranch,
                    (
                        (UserBranch.branch_id == record.id)
                        & UserBranch.is_active.is_(True)
                        & UserBranch.revoked_at.is_(None)
                    ),
                    "accesos administrativos",
                ),
            )
            for model, condition, label in checks:
                if await self._exists(model, condition):
                    blockers.append(label)
        elif resource == "warehouse_categories" and await self._exists(
            Warehouse, Warehouse.warehouse_category_id == record.id
        ):
            blockers.append("almacenes")
        elif resource == "warehouses" and await self._exists(
            Location, Location.warehouse_id == record.id
        ):
            blockers.append("ubicaciones físicas")
        elif resource == "departments":
            if await self._exists(Employee, Employee.department_id == record.id):
                blockers.append("empleados")
            if await self._exists(Department, Department.parent_department_id == record.id):
                blockers.append("subdepartamentos")
            if await self._exists(
                DepartmentBranchAssignment,
                DepartmentBranchAssignment.department_id == record.id,
                DepartmentBranchAssignment.is_active.is_(True),
                DepartmentBranchAssignment.closed_at.is_(None),
            ):
                blockers.append("asignaciones a sucursales")
        elif resource == "employees":
            if record.user_id and await self._exists(User, User.id == record.user_id):
                blockers.append("una cuenta de usuario activa")
            if await self._exists(
                EmployeeBranchAssignment,
                EmployeeBranchAssignment.employee_id == record.id,
                EmployeeBranchAssignment.is_active.is_(True),
                EmployeeBranchAssignment.assigned_until.is_(None),
            ):
                blockers.append("asignaciones a sucursales")
            if await self._exists(Branch, Branch.manager_employee_id == record.id):
                blockers.append("sucursales bajo su responsabilidad")
            if await self._exists(Warehouse, Warehouse.manager_employee_id == record.id):
                blockers.append("almacenes bajo su responsabilidad")
        elif resource == "users":
            if record.id == actor_id:
                blockers.append("su propia sesión")
            if record.is_superuser:
                another = await self._exists(
                    User,
                    User.is_superuser.is_(True),
                    User.is_active.is_(True),
                    User.id != record.id,
                )
                if not another:
                    blockers.append("la última cuenta de superadministración")
            if not allow_global and await self._exists(
                UserCompany,
                UserCompany.user_id == record.id,
                UserCompany.company_id != company_id,
            ):
                blockers.append("accesos vigentes a otras empresas")
        elif resource == "roles":
            if record.is_system or record.company_id is None:
                blockers.append("un rol protegido del sistema")
            elif await self._exists(UserRole, UserRole.role_id == record.id):
                blockers.append("usuarios con el rol asignado")
        elif resource == "permissions":
            if record.code in ALL_PERMISSION_CODES:
                blockers.append("un permiso estándar del sistema")
            elif await self._exists(RolePermission, RolePermission.permission_id == record.id):
                blockers.append("roles que utilizan el permiso")
        elif resource == "product_categories":
            if await self._exists(
                SubCategoryModel, SubCategoryModel.id_category == record.id_category
            ):
                blockers.append("subcategorías")
            if await self._exists(ProductModel, ProductModel.id_category == record.id_category):
                blockers.append("productos")
        elif resource == "product_subcategories" and await self._exists(
            ProductModel, ProductModel.id_sub_category == record.id_sub_category
        ):
            blockers.append("productos")
        elif resource == "units":
            if record.is_standard or record.owner_company_id is None:
                blockers.append("una unidad estándar global")
            elif await self._exists(
                ProductModel,
                or_(
                    ProductModel.purchase_unit == record.id_unit,
                    ProductModel.sale_unit == record.id_unit,
                ),
            ):
                blockers.append("productos")
        elif resource == "suppliers" and await self._exists(
            SupplierContactModel, SupplierContactModel.id_supplier == record.id_supplier
        ):
            blockers.append("contactos")
        return blockers

    async def _restore_blockers(  # noqa: C901
        self,
        resource: str,
        record: Any,
        company_id: uuid.UUID,
        *,
        allow_global: bool,
    ) -> list[str]:
        blockers: list[str] = []

        async def missing(model: type[Any], *conditions: Any) -> bool:
            return not await self._exists(model, *conditions)

        if resource == "branches" and await missing(Company, Company.id == record.company_id):
            blockers.append("la empresa está eliminada")
        elif resource == "warehouses":
            branch_company_id = await self._session.scalar(
                select(Branch.company_id)
                .where(Branch.id == record.branch_id)
                .execution_options(include_deleted=True)
            )
            if await missing(Branch, Branch.id == record.branch_id):
                blockers.append("la sucursal está eliminada")
            if await missing(
                WarehouseCategory,
                WarehouseCategory.id == record.warehouse_category_id,
                WarehouseCategory.company_id == branch_company_id,
            ):
                blockers.append("la categoría está eliminada o pertenece a otra empresa")
        elif resource == "locations" and await missing(
            Warehouse, Warehouse.id == record.warehouse_id
        ):
            blockers.append("el almacén está eliminado")
        elif resource == "departments":
            if await missing(Company, Company.id == record.company_id):
                blockers.append("la empresa está eliminada")
            if record.parent_department_id and await missing(
                Department, Department.id == record.parent_department_id
            ):
                blockers.append("el departamento padre está eliminado")
        elif resource == "employees":
            if await missing(Company, Company.id == record.company_id):
                blockers.append("la empresa está eliminada")
            if record.department_id and await missing(
                Department, Department.id == record.department_id
            ):
                blockers.append("el departamento está eliminado")
        elif resource == "users":
            if await missing(Employee, Employee.user_id == record.id):
                blockers.append("no existe un empleado activo vinculado")
            if not allow_global and await self._exists(
                UserCompany,
                UserCompany.user_id == record.id,
                UserCompany.company_id != company_id,
            ):
                blockers.append(
                    "la cuenta mantiene accesos a otras empresas y requiere superadministración"
                )
        elif resource in {"roles", "product_categories", "suppliers"}:
            if await missing(Company, Company.id == record.company_id):
                blockers.append("la empresa está eliminada")
        elif resource == "product_subcategories":
            if await missing(
                CategoryModel,
                CategoryModel.id_category == record.id_category,
                CategoryModel.company_id == record.company_id,
            ):
                blockers.append("la categoría está eliminada o pertenece a otra empresa")
        elif resource == "supplier_contacts" and await missing(
            SupplierModel, SupplierModel.id_supplier == record.id_supplier
        ):
            blockers.append("el proveedor está eliminado")
        elif (
            resource == "units"
            and record.owner_company_id
            and await missing(Company, Company.id == record.owner_company_id)
        ):
            blockers.append("la empresa está eliminada")
        elif resource == "products":
            if await missing(Company, Company.id == record.company_id):
                blockers.append("la empresa está eliminada")
            if await missing(
                CategoryModel,
                CategoryModel.id_category == record.id_category,
                CategoryModel.company_id == record.company_id,
            ):
                blockers.append("la categoría está eliminada o pertenece a otra empresa")
            if record.id_sub_category and await missing(
                SubCategoryModel,
                SubCategoryModel.id_sub_category == record.id_sub_category,
                SubCategoryModel.id_category == record.id_category,
                SubCategoryModel.company_id == record.company_id,
            ):
                blockers.append("la subcategoría está eliminada o no corresponde a la categoría")
            for unit_id, label in (
                (record.purchase_unit, "la unidad de compra"),
                (record.sale_unit, "la unidad de venta"),
            ):
                if await missing(UnitModel, UnitModel.id_unit == unit_id) or await missing(
                    CompanyUnitModel,
                    CompanyUnitModel.company_id == record.company_id,
                    CompanyUnitModel.unit_id == unit_id,
                    CompanyUnitModel.is_enabled.is_(True),
                ):
                    blockers.append(f"{label} no está disponible para la empresa")
        return blockers

    def _deleted_record(
        self,
        resource: str,
        policy: ResourcePolicy,
        record: Any,
        company_id: uuid.UUID | None,
        *,
        deleted_at: datetime | None = None,
        deleted_by: uuid.UUID | None = None,
        deletion_reason: str | None = None,
        operation_applied: bool = True,
    ) -> DeletedRecord:
        return DeletedRecord(
            resource=resource,
            record_id=str(getattr(record, policy.id_attribute)),
            label=self._label(policy, record),
            company_id=company_id,
            deleted_at=deleted_at or record.deleted_at,
            deleted_by=deleted_by if deleted_by is not None else record.deleted_by,
            deletion_reason=(
                deletion_reason if deletion_reason is not None else record.deletion_reason
            ),
            operation_applied=operation_applied,
        )

    @staticmethod
    def _deleted_scope_statement(  # noqa: C901
        policy: ResourcePolicy,
        company_id: uuid.UUID,
        *,
        include_all_companies: bool,
        document_module: str | None = None,
        include_restricted: bool = True,
    ) -> Any:
        """Build the tenant-safe base SELECT used by trash queries."""

        stmt = select(policy.model).where(policy.model.deleted_at.is_not(None))
        if policy.scope == "self":
            if not include_all_companies:
                stmt = stmt.where(policy.model.id == company_id)
        elif policy.scope == "company":
            stmt = stmt.where(policy.model.company_id == company_id)
        elif policy.scope == "warehouse":
            stmt = stmt.join(Branch, policy.model.branch_id == Branch.id).where(
                Branch.company_id == company_id
            )
        elif policy.scope == "location":
            stmt = (
                stmt.join(Warehouse, policy.model.warehouse_id == Warehouse.id)
                .join(Branch, Warehouse.branch_id == Branch.id)
                .where(Branch.company_id == company_id)
            )
        elif policy.scope == "supplier_contact":
            stmt = stmt.join(
                SupplierModel,
                policy.model.id_supplier == SupplierModel.id_supplier,
            ).where(SupplierModel.company_id == company_id)
        elif policy.scope == "unit":
            stmt = stmt.where(policy.model.owner_company_id == company_id)
        elif policy.scope == "user":
            stmt = stmt.join(UserCompany, UserCompany.user_id == policy.model.id).where(
                UserCompany.company_id == company_id
            )
        if policy.model is DocumentAssetModel and (
            document_module is not None or not include_restricted
        ):
            stmt = stmt.join(DocumentRecordModel, DocumentRecordModel.id == DocumentAssetModel.id)
            if document_module is not None:
                stmt = stmt.where(DocumentRecordModel.module == document_module)
        if not include_restricted and policy.model is DocumentAssetModel:
            stmt = stmt.where(
                or_(
                    DocumentRecordModel.module != "employees",
                    DocumentRecordModel.confidentiality != "restricted",
                )
            )
        return stmt.execution_options(include_deleted=True)

    @staticmethod
    def _with_deleted_search(stmt: Any, policy: ResourcePolicy, search: str | None) -> Any:
        normalized = search.strip() if search else ""
        if not normalized:
            return stmt
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        return stmt.where(
            or_(
                *(
                    getattr(policy.model, attribute).ilike(pattern, escape="\\")
                    for attribute in policy.label_attributes
                )
            )
        )

    @staticmethod
    def _listed_company_id(
        policy: ResourcePolicy,
        record: Any,
        requested_company_id: uuid.UUID,
    ) -> uuid.UUID | None:
        if policy.scope == "global":
            return None
        if policy.scope == "self":
            return record.id
        if policy.scope == "unit":
            return record.owner_company_id
        return requested_company_id

    async def list_deleted(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        resource: str | None = None,
        search: str | None = None,
        include_global: bool = False,
        include_all_companies: bool = False,
        document_module: str | None = None,
        include_restricted: bool = True,
    ) -> tuple[list[DeletedRecord], int]:
        resources = [resource] if resource else list(RESOURCE_POLICIES)
        items: list[DeletedRecord] = []

        # A filtered trash view is the common path used by module-specific
        # screens.  Count and pagination stay entirely in PostgreSQL so its
        # cost does not grow with the total historical volume.
        if resource is not None:
            policy = self._policy(resource)
            if policy.scope == "global" and not include_global:
                return [], 0
            stmt = self._deleted_scope_statement(
                policy,
                company_id,
                include_all_companies=include_all_companies,
                document_module=document_module,
                include_restricted=include_restricted,
            )
            stmt = self._with_deleted_search(stmt, policy, search)
            count_stmt = (
                select(func.count())
                .select_from(stmt.subquery())
                .execution_options(include_deleted=True)
            )
            total = int(await self._session.scalar(count_stmt) or 0)
            id_column = getattr(policy.model, policy.id_attribute)
            stmt = (
                stmt.order_by(policy.model.deleted_at.desc(), id_column.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
            records = (await self._session.execute(stmt)).scalars().unique().all()
            return [
                self._deleted_record(
                    resource,
                    policy,
                    record,
                    self._listed_company_id(policy, record, company_id),
                )
                for record in records
            ], total

        total = 0
        per_resource_limit = page * size
        for resource_name in resources:
            policy = self._policy(resource_name)
            if policy.scope == "global" and not include_global:
                continue
            stmt = self._deleted_scope_statement(
                policy,
                company_id,
                include_all_companies=include_all_companies,
                document_module=document_module,
                include_restricted=include_restricted,
            )
            stmt = self._with_deleted_search(stmt, policy, search)
            count_stmt = (
                select(func.count())
                .select_from(stmt.subquery())
                .execution_options(include_deleted=True)
            )
            resource_total = int(await self._session.scalar(count_stmt) or 0)
            total += resource_total
            if resource_total == 0:
                continue
            id_column = getattr(policy.model, policy.id_attribute)
            label_columns = (
                getattr(policy.model, attribute) for attribute in policy.label_attributes
            )
            stmt = stmt.order_by(
                policy.model.deleted_at.desc(),
                *(column.desc() for column in label_columns),
                id_column.desc(),
            ).limit(per_resource_limit)
            records = (await self._session.execute(stmt)).scalars().unique().all()
            for record in records:
                items.append(
                    self._deleted_record(
                        resource_name,
                        policy,
                        record,
                        self._listed_company_id(policy, record, company_id),
                    )
                )
        items.sort(key=lambda item: (item.deleted_at, item.resource, item.label), reverse=True)
        offset = (page - 1) * size
        return items[offset : offset + size], total

    async def soft_delete(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        allow_global: bool = False,
    ) -> DeletedRecord:
        policy, record = await self._get(resource, record_id)
        actual_company_id = await self._assert_scope(
            policy, record, company_id, allow_global=allow_global
        )
        if record.deleted_at is not None:
            return self._deleted_record(
                resource,
                policy,
                record,
                actual_company_id,
                operation_applied=False,
            )
        blockers = await self._deletion_blockers(
            resource,
            record,
            actor_id,
            company_id,
            allow_global=allow_global,
        )
        if blockers:
            detail = ", ".join(blockers)
            raise ConflictError(
                f"No se puede eliminar porque mantiene relación con: {detail}.",
                code="record_has_dependencies",
            )
        await self._detach_supplier_image(resource, record)
        record.deleted_at = datetime.now(UTC)
        record.deleted_by = actor_id
        record.deletion_reason = reason
        if resource == "users":
            record.is_active = False
            await self._session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == record.id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=record.deleted_at)
            )
            await self._session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == record.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=record.deleted_at)
            )
        await self._session.flush()
        return self._deleted_record(resource, policy, record, actual_company_id)

    async def restore(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_global: bool = False,
    ) -> DeletedRecord:
        del actor_id  # actor is recorded by the audit service at the API boundary
        locked_location_warehouse: Warehouse | None = None
        if resource == "locations":
            policy = self._policy(resource)
            parsed_id = self._parse_id(policy, record_id)
            warehouse_id = await self._session.scalar(
                select(Location.warehouse_id)
                .where(Location.id == parsed_id)
                .execution_options(include_deleted=True)
            )
            if warehouse_id is not None:
                # Match create/update/publish lock order: warehouse first, then
                # location. This serializes commissioning and restore decisions.
                locked_location_warehouse = await self._session.scalar(
                    select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
                )
        policy, record = await self._get(resource, record_id)
        actual_company_id = await self._assert_scope(
            policy, record, company_id, allow_global=allow_global
        )
        if record.deleted_at is None:
            return self._deleted_record(
                resource,
                policy,
                record,
                actual_company_id,
                operation_applied=False,
            )
        blockers = await self._restore_blockers(
            resource,
            record,
            company_id,
            allow_global=allow_global,
        )
        if blockers:
            raise ConflictError(
                f"No se puede restaurar porque {', '.join(blockers)}.",
                code="restore_parent_deleted",
            )
        if resource == "locations" and record.is_active:
            warehouse = locked_location_warehouse
            if (
                warehouse is None
                or not warehouse.is_active
                or warehouse.operational_status == "inactive"
            ):
                raise ConflictError(
                    "No se puede restaurar una ubicación activa en el estado actual del almacén.",
                    code="warehouse_not_commissionable",
                )
        if resource == "locations":
            await SqlAlchemyCapacityHierarchyRepository(self._session).validate_location_write(
                record.warehouse_id,
                {
                    "capacity_group_id": record.capacity_group_id,
                    "certified_max_weight_kg": record.certified_max_weight_kg,
                    "operational_max_weight_kg": record.operational_max_weight_kg,
                    "certified_usable_volume_m3": record.certified_usable_volume_m3,
                    "operational_usable_volume_m3": record.operational_usable_volume_m3,
                    "capacity_enforcement_mode": record.capacity_enforcement_mode,
                },
            )
        deleted_at = record.deleted_at
        deleted_by = record.deleted_by
        deletion_reason = record.deletion_reason
        try:
            async with self._session.begin_nested():
                record.deleted_at = None
                record.deleted_by = None
                record.deletion_reason = None
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "No se puede restaurar porque ya existe otro registro con el mismo identificador.",
                code="restore_unique_conflict",
            ) from exc
        return self._deleted_record(
            resource,
            policy,
            record,
            actual_company_id,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
            deletion_reason=deletion_reason,
        )
