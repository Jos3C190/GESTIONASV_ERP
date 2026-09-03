from __future__ import annotations

import uuid
from collections.abc import MutableSequence, Sequence
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Text, case, exists, func, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_folder import DocumentFolder
from app.domain.entities.document_record import DocumentCategory, DocumentRecord
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_record import DocumentCategoryModel, DocumentRecordModel
from app.infrastructure.models.employee import Employee, EmployeeBranchAssignment


def _asset_to_domain(model: DocumentAssetModel) -> DocumentAsset:
    return DocumentAsset(
        id=model.id,
        company_id=model.company_id,
        original_filename=model.original_filename,
        extension=model.extension,
        declared_content_type=model.declared_content_type,
        detected_content_type=model.detected_content_type,
        size_bytes=model.size_bytes,
        checksum_sha256=model.checksum_sha256,
        bucket=model.bucket,
        object_key=model.object_key,
        etag=model.etag,
        status=model.status,
        failure_code=model.failure_code,
        malware_name=model.malware_name,
        upload_expires_at=model.upload_expires_at,
        scan_started_at=model.scan_started_at,
        scanned_at=model.scanned_at,
        object_deleted_at=model.object_deleted_at,
        uploaded_by=model.uploaded_by,
        deleted_at=model.deleted_at,
        deleted_by=model.deleted_by,
        deletion_reason=model.deletion_reason,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _category_to_domain(model: DocumentCategoryModel) -> DocumentCategory:
    return DocumentCategory(
        id=model.id,
        company_id=model.company_id,
        module=model.module,
        code=model.code,
        name=model.name,
        group_name=model.group_name,
        description=model.description,
        sort_order=model.sort_order,
        is_active=model.is_active,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _record_to_domain(
    model: DocumentRecordModel,
    asset: DocumentAssetModel | None = None,
    category: DocumentCategoryModel | None = None,
    *,
    owner_label: str | None = None,
    owner_deleted: bool = False,
) -> DocumentRecord:
    return DocumentRecord(
        document_id=model.id,
        company_id=model.company_id,
        module=model.module,
        owner_type=model.owner_type,
        owner_id=model.owner_id,
        category_id=model.category_id,
        title=model.title,
        description=model.description,
        reference_code=model.reference_code,
        issuer=model.issuer,
        issued_on=model.issued_on,
        expires_on=model.expires_on,
        confidentiality=model.confidentiality,
        tags=list(model.tags or []),
        version_group_id=model.version_group_id,
        version_number=model.version_number,
        is_current=model.is_current,
        replaces_document_id=model.replaces_document_id,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        asset=_asset_to_domain(asset) if asset is not None else None,
        category_name=category.name if category is not None else None,
        category_group=category.group_name if category is not None else None,
        owner_label=owner_label,
        owner_deleted=owner_deleted,
    )


def _copy_category(category: DocumentCategory, model: DocumentCategoryModel) -> None:
    for name in (
        "module",
        "code",
        "name",
        "group_name",
        "description",
        "sort_order",
        "is_active",
        "created_by",
        "updated_by",
    ):
        setattr(model, name, getattr(category, name))


def _copy_record(record: DocumentRecord, model: DocumentRecordModel) -> None:
    for name in (
        "company_id",
        "module",
        "owner_type",
        "owner_id",
        "category_id",
        "title",
        "description",
        "reference_code",
        "issuer",
        "issued_on",
        "expires_on",
        "confidentiality",
        "tags",
        "version_group_id",
        "version_number",
        "is_current",
        "replaces_document_id",
        "created_by",
        "updated_by",
    ):
        setattr(model, name, getattr(record, name))


class SqlAlchemyDocumentRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_statement(self, *, include_deleted: bool) -> Any:
        statement = (
            select(DocumentRecordModel, DocumentAssetModel, DocumentCategoryModel)
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .join(
                DocumentCategoryModel, DocumentCategoryModel.id == DocumentRecordModel.category_id
            )
            .execution_options(include_deleted=True)
        )
        if not include_deleted:
            statement = statement.where(DocumentAssetModel.deleted_at.is_(None))
        return statement

    async def _hydrate(
        self,
        rows: Sequence[Any],
    ) -> list[DocumentRecord]:
        owner_ids = {
            item.owner_id
            for item, _asset, _category in rows
            if item.owner_type == "employee" and item.owner_id is not None
        }
        employees: dict[uuid.UUID, Employee] = {}
        if owner_ids:
            employees = {
                employee.id: employee
                for employee in (
                    await self._session.scalars(
                        select(Employee)
                        .where(Employee.id.in_(owner_ids))
                        .execution_options(include_deleted=True)
                    )
                ).all()
            }
        return [
            _record_to_domain(
                item,
                asset,
                category,
                owner_label=(
                    f"{employees[item.owner_id].first_name} {employees[item.owner_id].last_name}"
                    if item.owner_id in employees
                    else None
                ),
                owner_deleted=(
                    bool(employees[item.owner_id].deleted_at)
                    if item.owner_id in employees
                    else False
                ),
            )
            for item, asset, category in rows
        ]

    async def add(self, record: DocumentRecord) -> DocumentRecord:
        model = DocumentRecordModel(id=record.document_id)
        _copy_record(record, model)
        self._session.add(model)
        await self._session.flush()
        return _record_to_domain(model)

    async def get(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentRecord | None:
        row = (
            await self._session.execute(
                self._base_statement(include_deleted=include_deleted).where(
                    DocumentRecordModel.id == document_id
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return (await self._hydrate([row]))[0]

    async def save(self, record: DocumentRecord) -> DocumentRecord:
        model = await self._session.get(DocumentRecordModel, record.document_id)
        if model is None:
            raise LookupError("Document record not found")
        _copy_record(record, model)
        await self._session.flush()
        return (await self.get(record.document_id, include_deleted=True)) or record

    @staticmethod
    def _apply_business_status(statement: Any, status: str) -> Any:  # noqa: PLR0911
        today = datetime.now(ZoneInfo("America/El_Salvador")).date()
        if status == "deleted":
            return statement.where(DocumentAssetModel.deleted_at.is_not(None))
        if status == "processing":
            return statement.where(
                DocumentAssetModel.status.in_(("pending_upload", "pending_scan", "scanning"))
            )
        if status in {"quarantined", "rejected"}:
            return statement.where(DocumentAssetModel.status == status)
        if status == "replaced":
            return statement.where(
                DocumentAssetModel.status == "active", DocumentRecordModel.is_current.is_(False)
            )
        if status == "expired":
            return statement.where(
                DocumentAssetModel.status == "active",
                DocumentRecordModel.is_current.is_(True),
                DocumentRecordModel.expires_on < today,
            )
        if status == "expiring":
            return statement.where(
                DocumentAssetModel.status == "active",
                DocumentRecordModel.is_current.is_(True),
                DocumentRecordModel.expires_on >= today,
                DocumentRecordModel.expires_on <= date.fromordinal(today.toordinal() + 30),
            )
        if status == "current":
            return statement.where(
                DocumentAssetModel.status == "active",
                DocumentRecordModel.is_current.is_(True),
                or_(
                    DocumentRecordModel.expires_on.is_(None),
                    DocumentRecordModel.expires_on >= today,
                ),
            )
        return statement.where(DocumentAssetModel.status == status)

    async def list(  # noqa: C901
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        module: str | None = None,
        owner_type: str | None = None,
        owner_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        search: str | None = None,
        include_versions: bool = False,
        include_deleted: bool = False,
        document_status: str | None = None,
        storage_status: str | None = None,
        confidentiality: str | None = None,
        expires_within_days: int | None = None,
        include_restricted: bool = True,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[DocumentRecord], int]:
        statement = self._base_statement(include_deleted=include_deleted).where(
            DocumentRecordModel.company_id == company_id
        )
        if not include_versions:
            statement = statement.where(DocumentRecordModel.is_current.is_(True))
        if module:
            statement = statement.where(DocumentRecordModel.module == module)
        if owner_type:
            statement = statement.where(DocumentRecordModel.owner_type == owner_type)
        if owner_id:
            statement = statement.where(DocumentRecordModel.owner_id == owner_id)
        if branch_id is not None:
            employee_branch_match = exists(
                select(1)
                .select_from(EmployeeBranchAssignment)
                .where(
                    EmployeeBranchAssignment.employee_id == DocumentRecordModel.owner_id,
                    EmployeeBranchAssignment.branch_id == branch_id,
                    EmployeeBranchAssignment.is_active.is_(True),
                    EmployeeBranchAssignment.assigned_until.is_(None),
                )
            )
            statement = statement.where(
                or_(DocumentRecordModel.module != "employees", employee_branch_match)
            )
        if category_id:
            statement = statement.where(DocumentRecordModel.category_id == category_id)
        normalized = search.strip() if search else ""
        if normalized:
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            token = f"%{escaped}%"
            employee_match = exists(
                select(1)
                .select_from(Employee)
                .where(
                    Employee.id == DocumentRecordModel.owner_id,
                    or_(
                        Employee.first_name.ilike(token, escape="\\"),
                        Employee.last_name.ilike(token, escape="\\"),
                        Employee.employee_code.ilike(token, escape="\\"),
                    ),
                )
                .execution_options(include_deleted=True)
            )
            statement = statement.where(
                or_(
                    DocumentRecordModel.title.ilike(token, escape="\\"),
                    DocumentRecordModel.description.ilike(token, escape="\\"),
                    DocumentRecordModel.reference_code.ilike(token, escape="\\"),
                    DocumentRecordModel.issuer.ilike(token, escape="\\"),
                    DocumentAssetModel.original_filename.ilike(token, escape="\\"),
                    sql_cast(DocumentRecordModel.tags, Text).ilike(token, escape="\\"),
                    employee_match,
                )
            )
        if document_status:
            statement = self._apply_business_status(statement, document_status)
        if storage_status:
            statement = statement.where(DocumentAssetModel.status == storage_status)
        if confidentiality:
            statement = statement.where(DocumentRecordModel.confidentiality == confidentiality)
        if not include_restricted:
            statement = statement.where(
                or_(
                    DocumentRecordModel.module != "employees",
                    DocumentRecordModel.confidentiality != "restricted",
                )
            )
        if expires_within_days is not None:
            today = datetime.now(ZoneInfo("America/El_Salvador")).date()
            statement = statement.where(
                DocumentRecordModel.is_current.is_(True),
                DocumentRecordModel.expires_on >= today,
                DocumentRecordModel.expires_on
                <= date.fromordinal(today.toordinal() + expires_within_days),
            )

        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(await self._session.scalar(count_statement) or 0)
        statement = (
            statement.order_by(DocumentRecordModel.created_at.desc(), DocumentRecordModel.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await self._session.execute(statement)).all()
        return await self._hydrate(rows), total

    @staticmethod
    def _folder_count_columns(today: date) -> tuple[Any, ...]:
        """Return low-cardinality aggregates shared by every folder query."""
        active = DocumentAssetModel.status == "active"
        expiring = (
            active
            & DocumentRecordModel.expires_on.is_not(None)
            & (DocumentRecordModel.expires_on >= today)
            & (DocumentRecordModel.expires_on <= date.fromordinal(today.toordinal() + 30))
        )
        expired = (
            active
            & DocumentRecordModel.expires_on.is_not(None)
            & (DocumentRecordModel.expires_on < today)
        )
        return (
            func.count(DocumentRecordModel.id).label("document_count"),
            func.count(case((active, DocumentRecordModel.id))).label("active_count"),
            func.count(case((expiring, DocumentRecordModel.id))).label("expiring_count"),
            func.count(case((expired, DocumentRecordModel.id))).label("expired_count"),
            func.max(DocumentRecordModel.updated_at).label("latest_document_at"),
        )

    def _folder_document_conditions(
        self,
        company_id: uuid.UUID,
        *,
        include_restricted: bool,
        branch_id: uuid.UUID | None,
        current_only: bool = True,
    ) -> MutableSequence[Any]:
        conditions: MutableSequence[Any] = [
            DocumentRecordModel.company_id == company_id,
            DocumentAssetModel.deleted_at.is_(None),
        ]
        if current_only:
            conditions.append(DocumentRecordModel.is_current.is_(True))
        if not include_restricted:
            conditions.append(
                or_(
                    DocumentRecordModel.module != "employees",
                    DocumentRecordModel.confidentiality != "restricted",
                )
            )
        if branch_id is not None:
            employee_branch_match = exists(
                select(1)
                .select_from(EmployeeBranchAssignment)
                .where(
                    EmployeeBranchAssignment.employee_id == DocumentRecordModel.owner_id,
                    EmployeeBranchAssignment.branch_id == branch_id,
                    EmployeeBranchAssignment.is_active.is_(True),
                    EmployeeBranchAssignment.assigned_until.is_(None),
                )
            )
            conditions.append(
                or_(DocumentRecordModel.module != "employees", employee_branch_match)
            )
        return conditions

    @staticmethod
    def _folder_from_row(
        *,
        folder_id: str,
        kind: str,
        name: str,
        module: str,
        parent_id: str | None,
        row: Any | None = None,
        employee_id: str | None = None,
        category_id: str | None = None,
        employee_code: str | None = None,
        employee_status: str | None = None,
        can_upload: bool = False,
    ) -> DocumentFolder:
        return DocumentFolder(
            id=folder_id,
            kind=kind,
            name=name,
            module=module,
            parent_id=parent_id,
            employee_id=employee_id,
            category_id=category_id,
            employee_code=employee_code,
            employee_status=employee_status,
            document_count=int(getattr(row, "document_count", 0) or 0),
            active_count=int(getattr(row, "active_count", 0) or 0),
            expiring_count=int(getattr(row, "expiring_count", 0) or 0),
            expired_count=int(getattr(row, "expired_count", 0) or 0),
            latest_document_at=getattr(row, "latest_document_at", None),
            can_upload=can_upload,
        )

    async def list_folders(  # noqa: C901
        self,
        company_id: uuid.UUID,
        *,
        parent: str,
        employee_id: uuid.UUID | None = None,
        page: int,
        size: int,
        search: str | None = None,
        branch_id: uuid.UUID | None = None,
        include_restricted: bool = True,
        allowed_modules: set[str] | None = None,
        upload_modules: set[str] | None = None,
    ) -> tuple[Sequence[DocumentFolder], int]:
        """Return virtual folders without loading every document into Python.

        The aggregate is intentionally kept in the repository.  The service
        and router only decide which module/employee the caller may see; no
        ORM models or storage details escape this boundary.
        """
        if parent not in {"root", "general", "employees", "employee"}:
            raise ValueError("Unsupported document folder parent")
        allowed = allowed_modules if allowed_modules is not None else {"general", "employees"}
        uploads = upload_modules if upload_modules is not None else set()
        today = datetime.now(ZoneInfo("America/El_Salvador")).date()
        conditions = self._folder_document_conditions(
            company_id,
            include_restricted=include_restricted,
            branch_id=branch_id,
        )

        if parent == "root":
            if not allowed:
                return [], 0
            grouped = (
                select(DocumentRecordModel.module, *self._folder_count_columns(today))
                .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
                .where(*conditions, DocumentRecordModel.module.in_(allowed))
                .group_by(DocumentRecordModel.module)
            )
            rows = {
                row.module: row for row in (await self._session.execute(grouped)).all()
            }
            labels = {
                "general": "General",
                "employees": "Empleados",
            }
            folders = [
                self._folder_from_row(
                    folder_id=module,
                    kind="module",
                    name=labels[module],
                    module=module,
                    parent_id=None,
                    row=rows.get(module),
                    can_upload=module in uploads,
                )
                for module in ("general", "employees")
                if module in allowed
            ]
            return folders[(page - 1) * size : page * size], len(folders)

        if parent == "employees":
            if "employees" not in allowed:
                return [], 0
            aggregate = (
                select(
                    DocumentRecordModel.owner_id.label("employee_id"),
                    *self._folder_count_columns(today),
                )
                .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
                .where(*conditions, DocumentRecordModel.module == "employees")
                .group_by(DocumentRecordModel.owner_id)
                .subquery()
            )
            statement = (
                select(Employee, aggregate)
                .outerjoin(aggregate, aggregate.c.employee_id == Employee.id)
                .where(Employee.company_id == company_id, Employee.deleted_at.is_(None))
            )
            if branch_id is not None:
                branch_match = exists(
                    select(1)
                    .select_from(EmployeeBranchAssignment)
                    .where(
                        EmployeeBranchAssignment.employee_id == Employee.id,
                        EmployeeBranchAssignment.branch_id == branch_id,
                        EmployeeBranchAssignment.is_active.is_(True),
                        EmployeeBranchAssignment.assigned_until.is_(None),
                    )
                )
                statement = statement.where(branch_match)
            normalized = search.strip() if search else ""
            if normalized:
                escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                token = f"%{escaped}%"
                statement = statement.where(
                    or_(
                        Employee.first_name.ilike(token, escape="\\"),
                        Employee.last_name.ilike(token, escape="\\"),
                        Employee.employee_code.ilike(token, escape="\\"),
                    )
                )
            count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
            total = int(await self._session.scalar(count_statement) or 0)
            statement = statement.order_by(
                Employee.last_name,
                Employee.first_name,
                Employee.employee_code,
                Employee.id,
            ).offset((page - 1) * size).limit(size)
            employee_rows = (await self._session.execute(statement)).all()
            folders = []
            for result_row in employee_rows:
                employee = result_row[0]
                folders.append(
                    self._folder_from_row(
                        folder_id=f"employee:{employee.id}",
                        kind="employee",
                        name=f"{employee.first_name} {employee.last_name}",
                        module="employees",
                        parent_id="employees",
                        row=result_row,
                        employee_id=str(employee.id),
                        employee_code=employee.employee_code,
                        employee_status=employee.status,
                        can_upload="employees" in uploads,
                    )
                )
            return folders, total

        module = "general" if parent == "general" else "employees"
        if module not in allowed:
            return [], 0
        if parent == "employee" and employee_id is None:
            raise ValueError("employee_id is required for an employee folder")

        aggregate_conditions = [*conditions, DocumentRecordModel.module == module]
        if employee_id is not None:
            aggregate_conditions.append(DocumentRecordModel.owner_id == employee_id)
        aggregate = (
            select(
                DocumentRecordModel.category_id.label("category_id"),
                *self._folder_count_columns(today),
            )
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(*aggregate_conditions)
            .group_by(DocumentRecordModel.category_id)
            .subquery()
        )
        # Active categories are always part of the stable tree.  A category
        # that was later deactivated must remain discoverable when it still
        # owns a non-deleted historical version, even if that version is no
        # longer the current one.  This existence check stays in the same
        # SQL statement and therefore does not introduce an N+1 query.
        historical_conditions = self._folder_document_conditions(
            company_id,
            include_restricted=include_restricted,
            branch_id=branch_id,
            current_only=False,
        )
        historical_category_exists = (
            exists(
                select(1)
                .select_from(DocumentRecordModel)
                .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
                .where(
                    *historical_conditions,
                    DocumentRecordModel.module == module,
                    DocumentRecordModel.category_id == DocumentCategoryModel.id,
                )
            )
            .correlate(DocumentCategoryModel)
        )
        statement = (
            select(DocumentCategoryModel, aggregate)
            .outerjoin(aggregate, aggregate.c.category_id == DocumentCategoryModel.id)
            .where(
                DocumentCategoryModel.company_id == company_id,
                DocumentCategoryModel.module == module,
                or_(
                    DocumentCategoryModel.is_active.is_(True),
                    historical_category_exists,
                ),
            )
        )
        normalized = search.strip() if search else ""
        if normalized:
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            token = f"%{escaped}%"
            statement = statement.where(
                or_(
                    DocumentCategoryModel.name.ilike(token, escape="\\"),
                    DocumentCategoryModel.group_name.ilike(token, escape="\\"),
                )
            )
        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(await self._session.scalar(count_statement) or 0)
        statement = statement.order_by(
            DocumentCategoryModel.sort_order,
            DocumentCategoryModel.name,
            DocumentCategoryModel.id,
        ).offset((page - 1) * size).limit(size)
        category_rows = (await self._session.execute(statement)).all()
        folders = []
        for result_row in category_rows:
            category = result_row[0]
            folders.append(
                self._folder_from_row(
                    folder_id=f"category:{category.id}",
                    kind="category",
                    name=category.name,
                    module=module,
                    parent_id=(
                        f"employee:{employee_id}" if employee_id is not None else module
                    ),
                    row=result_row,
                    employee_id=str(employee_id) if employee_id is not None else None,
                    category_id=str(category.id),
                    can_upload=module in uploads,
                )
            )
        return folders, total

    async def list_versions(self, document_id: uuid.UUID) -> Sequence[DocumentRecord]:
        record = await self.get(document_id, include_deleted=True)
        if record is None:
            return []
        statement = (
            self._base_statement(include_deleted=True)
            .where(DocumentRecordModel.version_group_id == record.version_group_id)
            .order_by(DocumentRecordModel.version_number.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return await self._hydrate(rows)

    async def next_version_number(self, version_group_id: uuid.UUID) -> int:
        """Reserve the next number while serializing replacements per group.

        PostgreSQL row locks are held until the surrounding request commits.
        Locking every existing version avoids the race where two replacement
        requests both calculate the same number before either insert flushes.
        """
        rows = (
            await self._session.scalars(
                select(DocumentRecordModel)
                .where(DocumentRecordModel.version_group_id == version_group_id)
                .with_for_update()
            )
        ).all()
        return max((item.version_number for item in rows), default=0) + 1

    async def set_current_version(
        self, *, version_group_id: uuid.UUID, document_id: uuid.UUID
    ) -> DocumentRecord | None:
        await self._session.execute(
            update(DocumentRecordModel)
            .where(DocumentRecordModel.version_group_id == version_group_id)
            .values(is_current=False)
        )
        await self._session.execute(
            update(DocumentRecordModel)
            .where(
                DocumentRecordModel.version_group_id == version_group_id,
                DocumentRecordModel.id == document_id,
            )
            .values(is_current=True)
        )
        await self._session.flush()
        return await self.get(document_id, include_deleted=True)

    async def categories(
        self, company_id: uuid.UUID, *, module: str | None = None, include_inactive: bool = False
    ) -> Sequence[DocumentCategory]:
        conditions = [DocumentCategoryModel.company_id == company_id]
        if module:
            conditions.append(DocumentCategoryModel.module == module)
        if not include_inactive:
            conditions.append(DocumentCategoryModel.is_active.is_(True))
        models = (
            await self._session.scalars(
                select(DocumentCategoryModel)
                .where(*conditions)
                .order_by(DocumentCategoryModel.sort_order, DocumentCategoryModel.name)
            )
        ).all()
        return [_category_to_domain(model) for model in models]

    async def get_category(
        self, category_id: uuid.UUID, company_id: uuid.UUID, *, include_inactive: bool = False
    ) -> DocumentCategory | None:
        conditions = [
            DocumentCategoryModel.id == category_id,
            DocumentCategoryModel.company_id == company_id,
        ]
        if not include_inactive:
            conditions.append(DocumentCategoryModel.is_active.is_(True))
        model = await self._session.scalar(select(DocumentCategoryModel).where(*conditions))
        return _category_to_domain(model) if model is not None else None

    async def add_category(self, category: DocumentCategory) -> DocumentCategory:
        model = DocumentCategoryModel(id=category.id)
        _copy_category(category, model)
        self._session.add(model)
        await self._session.flush()
        return _category_to_domain(model)

    async def save_category(self, category: DocumentCategory) -> DocumentCategory:
        model = await self._session.get(DocumentCategoryModel, category.id)
        if model is None:
            raise LookupError("Document category not found")
        _copy_category(category, model)
        await self._session.flush()
        return _category_to_domain(model)

    async def count_category_documents(
        self,
        category_id: uuid.UUID,
        *,
        include_restricted: bool = True,
        branch_id: uuid.UUID | None = None,
    ) -> int:
        conditions = [
            DocumentRecordModel.category_id == category_id,
            DocumentAssetModel.deleted_at.is_(None),
        ]
        if not include_restricted:
            conditions.append(
                or_(
                    DocumentRecordModel.module != "employees",
                    DocumentRecordModel.confidentiality != "restricted",
                )
            )
        if branch_id is not None:
            employee_branch_match = exists(
                select(1)
                .select_from(EmployeeBranchAssignment)
                .where(
                    EmployeeBranchAssignment.employee_id == DocumentRecordModel.owner_id,
                    EmployeeBranchAssignment.branch_id == branch_id,
                    EmployeeBranchAssignment.is_active.is_(True),
                    EmployeeBranchAssignment.assigned_until.is_(None),
                )
            )
            conditions.append(
                or_(DocumentRecordModel.module != "employees", employee_branch_match)
            )
        return int(
            await self._session.scalar(
                select(func.count(DocumentRecordModel.id))
                .select_from(DocumentRecordModel)
                .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
                .where(*conditions)
            )
            or 0
        )


__all__ = ["SqlAlchemyDocumentRecordRepository"]
