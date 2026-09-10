from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any

from app.application.audit.audit_service import AuditService
from app.application.documents.general_service import DocumentGeneralService
from app.application.documents.record_service import DocumentMetadataInput, DocumentRecordService
from app.application.documents.service import (
    InitiateDocumentInput,
    UploadTicket,
    validate_declaration,
)
from app.core.config import Settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.document_general_entry import (
    clean_general_entry_name,
    normalize_general_entry_name,
)
from app.domain.entities.document_general_import import (
    DocumentGeneralImport,
    DocumentGeneralImportItem,
)
from app.domain.ports.document_general_import_repository import DocumentGeneralImportRepository
from app.domain.ports.document_general_repository import DocumentGeneralRepository


class DocumentGeneralImportService:
    def __init__(
        self,
        imports: DocumentGeneralImportRepository,
        entries: DocumentGeneralRepository,
        general: DocumentGeneralService,
        records: DocumentRecordService,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self._imports = imports
        self._entries = entries
        self._general = general
        self._records = records
        self._audit = audit
        self._settings = settings

    @staticmethod
    def _path(value: str) -> tuple[str, ...]:
        if not value or "\\" in value or value.startswith("/") or "\x00" in value:
            raise ValidationError("La ruta de importación no es válida.", code="document_import_path_invalid")
        parts = tuple(value.split("/"))
        if any(not part or part in {".", ".."} for part in parts):
            raise ValidationError("La ruta de importación no es válida.", code="document_import_path_invalid")
        for part in parts:
            clean_general_entry_name(part)
        return parts

    @staticmethod
    def _suffix_name(base: str, index: int) -> str:
        suffix = f" ({index})"
        path = PurePosixPath(base)
        extension = path.suffix
        stem = base[: -len(extension)] if extension else base
        max_stem = 200 - len(suffix) - len(extension)
        return f"{stem[:max(1, max_stem)]}{suffix}{extension}"

    async def _unique_name(
        self,
        company_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        base: str,
        allocated: set[str],
    ) -> str:
        display = clean_general_entry_name(base)
        index = 0
        while True:
            candidate = display if index == 0 else self._suffix_name(display, index)
            normalized = normalize_general_entry_name(candidate)
            if normalized not in allocated and not await self._entries.sibling_exists(company_id, parent_id, normalized):
                allocated.add(normalized)
                return candidate
            index += 1

    async def _create_folder_with_retry(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        base_name: str,
        allocated: set[str],
    ) -> tuple[Any, str]:
        for _ in range(32):
            resolved_name = await self._unique_name(company_id, parent_id, base_name, allocated)
            try:
                folder = await self._general.create_folder(company_id, actor_id, resolved_name, parent_id)
            except ConflictError as error:
                if error.code != "document_general_duplicate_name":
                    raise
            else:
                return folder, resolved_name
        raise ConflictError("No se pudo resolver el nombre de la carpeta.", code="document_general_duplicate_name")

    async def _attach_file_with_retry(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        item: DocumentGeneralImportItem,
    ) -> tuple[Any, str]:
        candidate = item.resolved_name or item.source_name
        for attempt in range(32):
            if attempt:
                candidate = await self._unique_name(company_id, item.parent_folder_id, item.source_name, set())
            try:
                entry = await self._general.attach_file(
                    company_id, actor_id, item.document_id, candidate, item.parent_folder_id
                )
            except ConflictError as error:
                if error.code != "document_general_duplicate_name":
                    raise
            else:
                return entry, candidate
        raise ConflictError("No se pudo resolver el nombre del archivo.", code="document_general_duplicate_name")

    @staticmethod
    def _metadata(values: dict[str, Any]) -> DocumentMetadataInput:
        def parse_date(value: Any) -> date | None:
            return date.fromisoformat(value) if isinstance(value, str) and value else None

        category = values.get("category_id")
        issued_on = parse_date(values.get("issued_on"))
        expires_on = parse_date(values.get("expires_on"))
        if issued_on and expires_on and expires_on < issued_on:
            raise ValidationError(
                "La fecha de vencimiento no puede ser anterior a la fecha de emisión.",
                code="document_import_dates_invalid",
            )
        return DocumentMetadataInput(
            category_id=uuid.UUID(category) if isinstance(category, str) and category else None,
            title=None,
            description=values.get("description"),
            reference_code=values.get("reference_code"),
            issuer=values.get("issuer"),
            issued_on=issued_on,
            expires_on=expires_on,
            confidentiality=values.get("confidentiality") or "restricted",
            tags=tuple(values.get("tags") or ()),
        )

    @staticmethod
    def _safe_message(error: AppError) -> str:
        return str(error.message)[:500]

    @staticmethod
    def _retryable(code: str) -> bool:
        return code in {
            "document_storage_unavailable",
            "document_object_missing",
            "document_upload_failed",
            "document_scan_in_progress",
            "document_scan_unavailable",
        }

    async def prepare(  # noqa: C901
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        metadata: dict[str, Any],
        manifest: Sequence[dict[str, Any]],
    ) -> tuple[DocumentGeneralImport, Sequence[DocumentGeneralImportItem]]:
        await self._general.validate_file_parent(company_id, parent_id)
        if len(manifest) > self._settings.DOCUMENT_GENERAL_IMPORT_MAX_ENTRIES:
            raise ValidationError("La importación supera el máximo de elementos permitido.", code="document_import_limit_exceeded")

        parsed: list[tuple[dict[str, Any], tuple[str, ...]]] = []
        seen_paths: set[tuple[str, ...]] = set()
        for raw in manifest:
            parts = self._path(str(raw.get("relative_path", "")))
            if len(parts) > self._settings.DOCUMENT_GENERAL_MAX_DEPTH:
                raise ValidationError("La ruta supera la profundidad máxima.", code="document_import_depth_exceeded")
            if parts in seen_paths:
                raise ValidationError("La ruta está duplicada en el manifiesto.", code="document_import_duplicate_path")
            seen_paths.add(parts)
            parsed.append((raw, parts))
        if not parsed:
            raise ValidationError("La carpeta seleccionada está vacía.", code="document_import_empty")
        folder_paths: set[tuple[str, ...]] = set()
        for raw, parts in parsed:
            if raw.get("kind") == "folder":
                folder_paths.add(parts)
            elif raw.get("kind") == "file":
                folder_paths.update(tuple(parts[:index]) for index in range(1, len(parts)))
            else:
                raise ValidationError("El tipo de elemento no es válido.", code="document_import_manifest_invalid")
        if len(folder_paths) > self._settings.DOCUMENT_GENERAL_IMPORT_MAX_ENTRIES:
            raise ValidationError("La importación supera el máximo de carpetas permitido.", code="document_import_limit_exceeded")

        file_count = sum(1 for raw, _ in parsed if raw.get("kind") == "file")
        folder_count = len(folder_paths)
        total_bytes = sum(int(raw.get("size_bytes") or 0) for raw, _ in parsed if raw.get("kind") == "file")
        if file_count > self._settings.DOCUMENT_GENERAL_IMPORT_MAX_FILES:
            raise ValidationError("La importación supera el máximo de archivos permitido.", code="document_import_limit_exceeded")
        if total_bytes > self._settings.DOCUMENT_GENERAL_IMPORT_MAX_TOTAL_BYTES:
            raise ValidationError("La importación supera el tamaño total permitido.", code="document_import_limit_exceeded")

        import_id = uuid.uuid4()
        folder_map: dict[tuple[str, ...], tuple[uuid.UUID, tuple[str, ...]]] = {}
        allocated: dict[uuid.UUID | None, set[str]] = {}
        for path in sorted(folder_paths, key=lambda item: (len(item), item)):
            parent_source = path[:-1]
            parent_entry = folder_map.get(parent_source)
            actual_parent = parent_entry[0] if parent_entry else parent_id
            names = allocated.setdefault(actual_parent, set())
            folder, resolved_name = await self._create_folder_with_retry(company_id, actor_id, actual_parent, path[-1], names)
            resolved_path = (parent_entry[1] if parent_entry else ()) + (resolved_name,)
            folder_map[path] = (folder.id, resolved_path)

        root_entry_id = next((entry_id for path, (entry_id, _) in folder_map.items() if len(path) == 1), None)

        import_row = DocumentGeneralImport(
            id=import_id, company_id=company_id, actor_id=actor_id, parent_id=parent_id,
            root_entry_id=root_entry_id, status="ready", metadata=dict(metadata),
            total_files=file_count, total_folders=folder_count, total_entries=len(parsed),
            total_bytes=total_bytes, expires_at=datetime.now(UTC) + timedelta(hours=self._settings.DOCUMENT_GENERAL_IMPORT_TTL_HOURS),
        )
        await self._imports.add_import(import_row)
        items: list[DocumentGeneralImportItem] = []
        for raw, parts in parsed:
            if raw.get("kind") != "file":
                folder = folder_map.get(parts)
                if folder:
                    item = DocumentGeneralImportItem(
                        id=uuid.uuid4(), import_id=import_id, kind="folder",
                        source_path="/".join(parts), source_name=parts[-1],
                        resolved_path="/".join(folder[1]), resolved_name=folder[1][-1],
                        parent_folder_id=folder[0], entry_id=folder[0], status="completed",
                    )
                    await self._imports.add_item(item)
                    items.append(item)
                continue
            source_name = parts[-1]
            parent = folder_map.get(parts[:-1])
            item = DocumentGeneralImportItem(
                id=uuid.uuid4(), import_id=import_id, kind="file",
                source_path="/".join(parts), source_name=source_name,
                resolved_path="/".join(parent[1] if parent else ()) + "/" + source_name if parent else source_name,
                resolved_name=source_name,
                parent_folder_id=parent[0] if parent else parent_id,
                size_bytes=int(raw.get("size_bytes") or 0),
                content_type=str(raw.get("content_type") or ""),
                extension=PurePosixPath(source_name).suffix.lower().lstrip("."),
            )
            try:
                safe_name, extension, _ = validate_declaration(
                    filename=source_name,
                    content_type=item.content_type or "application/octet-stream",
                    size_bytes=item.size_bytes or 0,
                    checksum_sha256="0" * 64,
                    max_bytes=self._settings.DOCUMENT_MAX_BYTES,
                )
                if parent is None:
                    raise ValidationError("La carpeta padre no existe.", code="document_import_parent_invalid")  # noqa: TRY301
                names = allocated.setdefault(parent[0], set())
                resolved_name = await self._unique_name(company_id, parent[0], safe_name, names)
                item.source_name = safe_name
                item.resolved_name = resolved_name
                item.resolved_path = "/".join(parent[1] + (resolved_name,))
                item.extension = extension.lstrip(".")
            except ValidationError as error:
                item.status = "skipped"
                item.failure_code = error.code
                item.failure_message = str(error.message)
                import_row.skipped_files += 1
            await self._imports.add_item(item)
            items.append(item)
        import_row.total_entries = len(items)
        import_row.status = "ready"
        await self._imports.save_import(import_row)
        await self._audit.record(
            action="GENERAL_FOLDER_IMPORT_STARTED", user_id=actor_id, company_id=company_id,
            resource_type="document_general_imports", resource_id=str(import_id),
            after_state={"total_files": file_count, "total_folders": folder_count, "total_bytes": total_bytes},
            required=True,
        )
        if file_count in {0, import_row.skipped_files}:
            await self._refresh_counts(import_row)
        return import_row, items

    async def get(self, company_id: uuid.UUID, import_id: uuid.UUID, *, page: int = 1, size: int = 200) -> tuple[DocumentGeneralImport, Sequence[DocumentGeneralImportItem], int]:
        import_row = await self._imports.get_import(company_id, import_id)
        if import_row is None:
            raise NotFoundError("Importación no encontrada.", code="document_import_not_found")
        if import_row.expires_at and import_row.expires_at < datetime.now(UTC) and import_row.status not in {"completed", "partial", "cancelled", "expired"}:
            expired_items = await self._imports.list_items(
                company_id, import_id, page=1, size=self._settings.DOCUMENT_GENERAL_IMPORT_MAX_ENTRIES
            )
            cancelled_files = 0
            for item in expired_items:
                if item.status in {"ready", "authorized"}:
                    item.status = "cancelled"
                    item.failure_code = "document_import_expired"
                    item.failure_message = "La sesión de importación expiró antes de completar este archivo."
                    await self._imports.save_item(item)
                    cancelled_files += 1
            import_row.status = "expired"
            import_row.completed_at = datetime.now(UTC)
            await self._imports.save_import(import_row)
            await self._audit.record(
                action="GENERAL_FOLDER_IMPORT_EXPIRED", user_id=import_row.actor_id,
                company_id=company_id, resource_type="document_general_imports",
                resource_id=str(import_id), after_state={"cancelled_files": cancelled_files}, required=True,
            )
        return import_row, await self._imports.list_items(company_id, import_id, page=page, size=size), await self._imports.count_items(company_id, import_id)

    async def ticket(self, company_id: uuid.UUID, actor_id: uuid.UUID, import_id: uuid.UUID, item_id: uuid.UUID, checksum: str) -> tuple[DocumentGeneralImportItem, UploadTicket]:
        import_row, _, _ = await self.get(company_id, import_id)
        if import_row.status in {"expired", "cancelled", "completed"}:
            raise ConflictError("La importación ya no está disponible.", code="document_import_closed")
        item = await self._imports.get_item(company_id, import_id, item_id)
        if item is None or item.kind != "file":
            raise NotFoundError("Elemento de importación no encontrado.", code="document_import_item_not_found")
        if item.status == "completed":
            raise ConflictError("El archivo ya fue completado.", code="document_import_item_completed")
        if item.status in {"skipped", "failed_permanent", "cancelled"}:
            raise ConflictError("El archivo no se puede reintentar.", code="document_import_item_not_retryable")
        if item.parent_folder_id is None:
            raise ConflictError("La carpeta de destino ya no existe.", code="document_import_parent_invalid")
        metadata = self._metadata(import_row.metadata)
        upload = await self._records.initiate_general(
            InitiateDocumentInput(
                company_id=company_id, actor_id=actor_id, filename=item.source_name,
                content_type=item.content_type or "application/octet-stream",
                size_bytes=item.size_bytes or 0, checksum_sha256=checksum,
            ),
            metadata,
        )
        item.document_id = upload.ticket.document.id
        item.status = "authorized"
        item.attempts += 1
        await self._imports.save_item(item)
        import_row.status = "running"
        await self._imports.save_import(import_row)
        return item, upload.ticket

    async def complete(self, company_id: uuid.UUID, actor_id: uuid.UUID, import_id: uuid.UUID, item_id: uuid.UUID) -> DocumentGeneralImportItem:
        import_row, _, _ = await self.get(company_id, import_id)
        item = await self._imports.get_item(company_id, import_id, item_id)
        if item is None or item.kind != "file" or item.document_id is None:
            raise NotFoundError("Elemento de importación no encontrado.", code="document_import_item_not_found")
        if item.status == "completed":
            return item
        try:
            record = await self._records.complete(company_id, item.document_id, actor_id)
            if record.asset is None or record.asset.status != "active":
                raise ConflictError("El documento aún no está activo.", code="document_scan_in_progress")
            entry, resolved_name = await self._attach_file_with_retry(company_id, actor_id, item)
            item.resolved_name = resolved_name
            parent_path = item.resolved_path.rsplit("/", 1)[0] if "/" in item.resolved_path else ""
            item.resolved_path = f"{parent_path}/{resolved_name}" if parent_path else resolved_name
            item.entry_id = entry.id
            item.status = "completed"
            item.failure_code = None
            item.failure_message = None
        except AppError as error:
            item.status = "failed_retryable" if self._retryable(error.code) else "failed_permanent"
            item.failure_code = error.code
            item.failure_message = self._safe_message(error)
            await self._imports.save_item(item)
            await self._refresh_counts(import_row)
            raise
        await self._imports.save_item(item)
        await self._refresh_counts(import_row)
        return item

    async def retryable(self, company_id: uuid.UUID, import_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        item = await self._imports.get_item(company_id, import_id, item_id)
        return item is not None and item.status == "failed_retryable"

    async def cancel(self, company_id: uuid.UUID, actor_id: uuid.UUID, import_id: uuid.UUID) -> DocumentGeneralImport:
        import_row, items, _ = await self.get(company_id, import_id)
        if import_row.status in {"completed", "partial", "cancelled"}:
            return import_row
        for item in items:
            if item.kind == "file" and item.status in {"ready", "authorized"}:
                item.status = "cancelled"
                await self._imports.save_item(item)
        import_row.status = "cancelled"
        import_row.completed_at = datetime.now(UTC)
        await self._imports.save_import(import_row)
        await self._audit.record(
            action="GENERAL_FOLDER_IMPORT_CANCELLED", user_id=actor_id, company_id=company_id,
            resource_type="document_general_imports", resource_id=str(import_id), after_state={}, required=True,
        )
        return import_row

    async def _refresh_counts(self, import_row: DocumentGeneralImport) -> None:
        items = await self._imports.list_items(import_row.company_id, import_row.id, page=1, size=self._settings.DOCUMENT_GENERAL_IMPORT_MAX_ENTRIES)
        files = [item for item in items if item.kind == "file"]
        import_row.completed_files = sum(item.status == "completed" for item in files)
        import_row.skipped_files = sum(item.status == "skipped" for item in files)
        import_row.failed_files = sum(item.status in {"failed_retryable", "failed_permanent"} for item in files)
        pending = any(item.status in {"ready", "authorized"} for item in files)
        if not pending:
            import_row.status = "partial" if import_row.skipped_files or import_row.failed_files else "completed"
            import_row.completed_at = datetime.now(UTC)
            action = "GENERAL_FOLDER_IMPORT_PARTIAL" if import_row.status == "partial" else "GENERAL_FOLDER_IMPORT_COMPLETED"
            await self._audit.record(
                action=action, user_id=import_row.actor_id, company_id=import_row.company_id,
                resource_type="document_general_imports", resource_id=str(import_row.id),
                after_state={"completed_files": import_row.completed_files, "skipped_files": import_row.skipped_files, "failed_files": import_row.failed_files},
                required=True,
            )
        await self._imports.save_import(import_row)

__all__ = ["DocumentGeneralImportService"]
