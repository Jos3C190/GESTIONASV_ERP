from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.audit.audit_service import AuditService
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.document_general_entry import (
    DocumentGeneralEntry,
    GeneralDeletionBatch,
    clean_general_entry_name,
    normalize_general_entry_name,
)
from app.domain.ports.document_general_repository import DocumentGeneralRepository


@dataclass(frozen=True, slots=True)
class GeneralContents:
    items: Sequence[DocumentGeneralEntry]
    total: int


class DocumentGeneralService:
    """Use cases for the mutable, company-scoped general workspace."""

    def __init__(
        self,
        repository: DocumentGeneralRepository,
        audit: AuditService,
        *,
        max_depth: int = 20,
    ) -> None:
        self._repository = repository
        self._audit = audit
        self._max_depth = max_depth

    @staticmethod
    def _name(value: str) -> tuple[str, str]:
        try:
            display = clean_general_entry_name(value)
        except ValueError as exc:
            raise ValidationError(str(exc), code="document_general_name_invalid") from exc
        return display, normalize_general_entry_name(display)

    async def _active_parent(
        self, company_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> DocumentGeneralEntry | None:
        if parent_id is None:
            return None
        parent = await self._repository.get(company_id, parent_id)
        if parent is None or parent.kind != "folder":
            deleted = await self._repository.get(company_id, parent_id, include_deleted=True)
            if deleted is not None and deleted.deleted_at is not None:
                raise ConflictError(
                    "La carpeta de destino está eliminada.",
                    code="document_general_parent_deleted",
                )
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        return parent

    @staticmethod
    def _depths(entries: Sequence[DocumentGeneralEntry]) -> dict[uuid.UUID, int]:
        by_id = {entry.id: entry for entry in entries}
        depths: dict[uuid.UUID, int] = {}
        for entry in entries:
            current = entry
            depth = 0
            seen: set[uuid.UUID] = set()
            while current.parent_id is not None:
                if current.id in seen or current.parent_id not in by_id:
                    break
                seen.add(current.id)
                depth += 1
                current = by_id[current.parent_id]
            depths[entry.id] = depth
        return depths

    async def _ensure_depth(
        self, company_id: uuid.UUID, parent_id: uuid.UUID | None, moving_id: uuid.UUID | None = None
    ) -> None:
        entries = list(await self._repository.list_tree(company_id))
        depths = self._depths(entries)
        parent_depth = -1 if parent_id is None else depths.get(parent_id, -1)
        if moving_id is None:
            if parent_depth + 2 > self._max_depth:
                raise ValidationError(
                    "La profundidad máxima de carpetas es 20 niveles.",
                    code="document_general_depth_exceeded",
                )
            return
        moving_depth = depths.get(moving_id, 0)
        subtree = await self._repository.descendants(company_id, moving_id)
        max_relative = max((depths.get(item.id, moving_depth) - moving_depth for item in subtree), default=0)
        if parent_depth + 2 + max_relative > self._max_depth:
            raise ValidationError(
                "La profundidad máxima de carpetas es 20 niveles.",
                code="document_general_depth_exceeded",
            )

    async def _ensure_sibling(
        self,
        company_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        normalized_name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if await self._repository.sibling_exists(
            company_id, parent_id, normalized_name, exclude_id=exclude_id
        ):
            raise ConflictError(
                "Ya existe una entrada con ese nombre en la carpeta.",
                code="document_general_duplicate_name",
            )

    @staticmethod
    def _state(entry: DocumentGeneralEntry) -> dict[str, object]:
        return {
            "id": str(entry.id),
            "kind": entry.kind,
            "name": entry.name,
            "parent_id": str(entry.parent_id) if entry.parent_id else None,
            "document_id": str(entry.document_id) if entry.document_id else None,
        }

    async def contents(
        self,
        company_id: uuid.UUID,
        *,
        folder_id: uuid.UUID | None = None,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        status: str | None = None,
        sort: str = "name",
        descending: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> GeneralContents:
        if folder_id is not None:
            await self._active_parent(company_id, folder_id)
        items, total = await self._repository.list_contents(
            company_id,
            parent_id=folder_id,
            search=search,
            category_id=category_id,
            status=status,
            sort=sort,
            descending=descending,
            page=page,
            size=size,
        )
        return GeneralContents(items, total)

    async def tree(self, company_id: uuid.UUID) -> Sequence[DocumentGeneralEntry]:
        return await self._repository.list_tree(company_id)

    async def breadcrumbs(
        self, company_id: uuid.UUID, folder_id: uuid.UUID | None
    ) -> list[dict[str, object]]:
        breadcrumbs: list[dict[str, object]] = [
            {"id": None, "label": "General", "href": "/documents/general"}
        ]
        if folder_id is None:
            return breadcrumbs
        folder = await self._repository.get(company_id, folder_id)
        if folder is None or folder.kind != "folder":
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        entries = {entry.id: entry for entry in await self._repository.list_tree(company_id)}
        chain: list[DocumentGeneralEntry] = []
        current: DocumentGeneralEntry | None = folder
        while current is not None:
            chain.append(current)
            current = entries.get(current.parent_id) if current.parent_id is not None else None
        for item in reversed(chain):
            breadcrumbs.append(
                {
                    "id": item.id,
                    "label": item.name,
                    "href": f"/documents/general?folder={item.id}",
                }
            )
        return breadcrumbs

    async def create_folder(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, name: str, parent_id: uuid.UUID | None
    ) -> DocumentGeneralEntry:
        display, normalized = self._name(name)
        await self._active_parent(company_id, parent_id)
        await self._ensure_depth(company_id, parent_id)
        await self._ensure_sibling(company_id, parent_id, normalized)
        entry = DocumentGeneralEntry(
            id=uuid.uuid4(),
            company_id=company_id,
            parent_id=parent_id,
            kind="folder",
            document_id=None,
            name=display,
            normalized_name=normalized,
            created_by=actor_id,
            updated_by=actor_id,
        )
        saved = await self._repository.add(entry)
        await self._audit.record(
            action="GENERAL_FOLDER_CREATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(saved.id),
            after_state=self._state(saved),
            required=True,
        )
        return saved

    async def rename_folder(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID, name: str
    ) -> DocumentGeneralEntry:
        entry = await self._repository.get(company_id, folder_id)
        if entry is None or entry.kind != "folder":
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        display, normalized = self._name(name)
        await self._ensure_sibling(
            company_id, entry.parent_id, normalized, exclude_id=entry.id
        )
        before = self._state(entry)
        entry.name = display
        entry.normalized_name = normalized
        entry.updated_by = actor_id
        saved = await self._repository.save(entry)
        await self._audit.record(
            action="GENERAL_FOLDER_RENAMED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(saved.id),
            before_state=before,
            after_state=self._state(saved),
            required=True,
        )
        return saved

    async def move_folder(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        folder_id: uuid.UUID,
        new_parent_id: uuid.UUID | None,
    ) -> DocumentGeneralEntry:
        entry = await self._repository.get(company_id, folder_id)
        if entry is None or entry.kind != "folder":
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        target = await self._active_parent(company_id, new_parent_id)
        if target is not None and target.id == entry.id:
            raise ValidationError("Una carpeta no puede ser su propia madre.", code="document_general_cycle")
        descendants = await self._repository.descendants(company_id, entry.id)
        if target is not None and target.id in {item.id for item in descendants}:
            raise ValidationError("El movimiento crea un ciclo.", code="document_general_cycle")
        await self._ensure_depth(company_id, new_parent_id, moving_id=entry.id)
        await self._ensure_sibling(
            company_id, new_parent_id, entry.normalized_name, exclude_id=entry.id
        )
        old_parent_id = entry.parent_id
        entry.parent_id = new_parent_id
        entry.updated_by = actor_id
        saved = await self._repository.save(entry)
        await self._audit.record(
            action="GENERAL_FOLDER_MOVED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(saved.id),
            before_state={"old_parent_id": str(old_parent_id) if old_parent_id else None},
            after_state={"new_parent_id": str(new_parent_id) if new_parent_id else None},
            required=True,
        )
        return saved

    async def attach_file(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        document_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
    ) -> DocumentGeneralEntry:
        display, normalized = self._name(name)
        await self._active_parent(company_id, parent_id)
        existing = await self._repository.get_by_document(
            company_id, document_id, include_deleted=True
        )
        if existing is not None:
            existing.parent_id = parent_id
            existing.name = display
            existing.normalized_name = normalized
            existing.deleted_at = None
            existing.deletion_batch_id = None
            existing.updated_by = actor_id
            return await self._repository.save(existing)
        await self._ensure_sibling(company_id, parent_id, normalized)
        return await self._repository.add(
            DocumentGeneralEntry(
                id=uuid.uuid4(),
                company_id=company_id,
                parent_id=parent_id,
                kind="file",
                document_id=document_id,
                name=display,
                normalized_name=normalized,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

    async def validate_file_parent(
        self, company_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> None:
        await self._active_parent(company_id, parent_id)

    async def rename_file(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, document_id: uuid.UUID, name: str
    ) -> DocumentGeneralEntry:
        entry = await self._repository.get_by_document(company_id, document_id)
        if entry is None or entry.kind != "file":
            raise NotFoundError("Archivo no encontrado.", code="document_general_file_not_found")
        display, normalized = self._name(name)
        await self._ensure_sibling(
            company_id, entry.parent_id, normalized, exclude_id=entry.id
        )
        before = self._state(entry)
        entry.name = display
        entry.normalized_name = normalized
        entry.updated_by = actor_id
        saved = await self._repository.save(entry)
        await self._audit.record(
            action="GENERAL_FILE_RENAMED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(saved.id),
            before_state=before,
            after_state=self._state(saved),
            required=True,
        )
        return saved

    async def move_file(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        document_id: uuid.UUID,
        new_parent_id: uuid.UUID | None,
    ) -> DocumentGeneralEntry:
        entry = await self._repository.get_by_document(company_id, document_id)
        if entry is None or entry.kind != "file":
            raise NotFoundError("Archivo no encontrado.", code="document_general_file_not_found")
        await self._active_parent(company_id, new_parent_id)
        await self._ensure_sibling(
            company_id, new_parent_id, entry.normalized_name, exclude_id=entry.id
        )
        old_parent_id = entry.parent_id
        entry.parent_id = new_parent_id
        entry.updated_by = actor_id
        saved = await self._repository.save(entry)
        await self._audit.record(
            action="GENERAL_FILE_MOVED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(saved.id),
            before_state={"old_parent_id": str(old_parent_id) if old_parent_id else None},
            after_state={"new_parent_id": str(new_parent_id) if new_parent_id else None},
            required=True,
        )
        return saved

    async def delete_folder(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID
    ) -> uuid.UUID:
        entry = await self._repository.get(company_id, folder_id)
        if entry is None or entry.kind != "folder":
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        batch_id = await self._repository.create_deletion_batch(company_id, actor_id)
        entries = await self._repository.descendants(company_id, folder_id)
        await self._repository.soft_delete_batch(
            company_id,
            [item.id for item in entries],
            batch_id,
            actor_id,
            datetime.now(UTC),
        )
        await self._audit.record(
            action="GENERAL_FOLDER_DELETED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_deletion_batches",
            resource_id=str(batch_id),
            after_state={"folder_id": str(folder_id), "entry_count": len(entries)},
            required=True,
        )
        return batch_id

    async def deletion_batches(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[Sequence[GeneralDeletionBatch], int]:
        return await self._repository.list_deletion_batches(
            company_id, search=search, page=page, size=size
        )

    async def restore_deletion_batch(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, batch_id: uuid.UUID
    ) -> DocumentGeneralEntry:
        entries = [
            item
            for item in await self._repository.list_tree(company_id, include_deleted=True)
            if item.deletion_batch_id == batch_id and item.deleted_at is not None
        ]
        batch_ids = {item.id for item in entries}
        roots = [
            item
            for item in entries
            if item.kind == "folder" and item.parent_id not in batch_ids
        ]
        if not roots:
            raise NotFoundError(
                "Lote de carpetas no encontrado.", code="document_general_deletion_batch_not_found"
            )
        return await self.restore_folder(company_id, actor_id, roots[0].id)
    async def restore_folder(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID
    ) -> DocumentGeneralEntry:
        entry = await self._repository.get(company_id, folder_id, include_deleted=True)
        if entry is None or entry.kind != "folder":
            raise NotFoundError("Carpeta no encontrada.", code="document_general_folder_not_found")
        if entry.deleted_at is None or entry.deletion_batch_id is None:
            raise ConflictError(
                "La carpeta no está eliminada.", code="document_general_not_deleted"
            )
        batch_entries = [
            item
            for item in await self._repository.list_tree(company_id, include_deleted=True)
            if item.deletion_batch_id == entry.deletion_batch_id
        ]
        batch_ids = {item.id for item in batch_entries}
        if entry.parent_id is not None and entry.parent_id not in batch_ids:
            parent = await self._repository.get(company_id, entry.parent_id, include_deleted=True)
            if parent is None or parent.deleted_at is not None:
                raise ConflictError(
                    "La carpeta padre sigue eliminada; no se puede restaurar el lote.",
                    code="document_general_restore_conflict",
                )
        for item in batch_entries:
            if await self._repository.sibling_exists(
                company_id, item.parent_id, item.normalized_name
            ):
                raise ConflictError(
                    "La restauración tiene conflicto de nombres con una entrada existente.",
                    code="document_general_restore_conflict",
                )
        await self._repository.restore_batch(company_id, entry.deletion_batch_id, actor_id)
        restored = await self._repository.get(company_id, folder_id)
        if restored is None:
            raise ConflictError("No se pudo restaurar la carpeta.", code="document_general_restore_failed")
        await self._audit.record(
            action="GENERAL_FOLDER_RESTORED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="document_general_entries",
            resource_id=str(folder_id),
            after_state={"deletion_batch_id": str(entry.deletion_batch_id)},
            required=True,
        )
        return restored


__all__ = ["DocumentGeneralService", "GeneralContents"]
