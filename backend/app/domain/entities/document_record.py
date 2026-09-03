from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.entities.document import DocumentAsset


@dataclass(slots=True)
class DocumentCategory:
    id: uuid.UUID
    company_id: uuid.UUID
    module: str
    code: str
    name: str
    group_name: str = "General"
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class DocumentRecord:
    document_id: uuid.UUID
    company_id: uuid.UUID
    module: str
    owner_type: str | None
    owner_id: uuid.UUID | None
    category_id: uuid.UUID
    title: str
    description: str | None = None
    reference_code: str | None = None
    issuer: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    confidentiality: str = "restricted"
    tags: list[str] = field(default_factory=list)
    version_group_id: uuid.UUID = field(default_factory=uuid.uuid4)
    version_number: int = 1
    is_current: bool = True
    replaces_document_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    asset: DocumentAsset | None = None
    category_name: str | None = None
    category_group: str | None = None
    owner_label: str | None = None
    owner_deleted: bool = False

    @property
    def is_employee_document(self) -> bool:
        return self.module == "employees" and self.owner_type == "employee"

    @property
    def is_restricted(self) -> bool:
        return self.confidentiality == "restricted"

    @property
    def business_status(self) -> str:  # noqa: PLR0911
        """Return a stable presentation status without persisting derived dates."""
        if self.asset is None:
            return "processing"
        if self.asset.deleted_at is not None:
            return "deleted"
        if self.asset.status in {"pending_upload", "pending_scan", "scanning"}:
            return "processing"
        if self.asset.status in {"quarantined", "rejected"}:
            return self.asset.status
        if self.asset.status != "active":
            return self.asset.status
        if not self.is_current:
            return "replaced"
        if self.expires_on is not None:
            today = datetime.now(ZoneInfo("America/El_Salvador")).date()
            if self.expires_on < today:
                return "expired"
            if (self.expires_on - today).days <= 30:  # noqa: PLR2004
                return "expiring"
        return "current"


__all__ = ["DocumentCategory", "DocumentRecord"]
