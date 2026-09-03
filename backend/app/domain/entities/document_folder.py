"""Read-only virtual folders for the document library.

Folders are a presentation projection, not persisted storage objects.  The
domain type deliberately contains only information that can be shown safely
after the caller's company, branch and RBAC scope has been applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DocumentFolder:
    """A virtual module, employee or category folder."""

    id: str
    kind: str
    name: str
    module: str
    parent_id: str | None
    employee_id: str | None = None
    category_id: str | None = None
    employee_code: str | None = None
    employee_status: str | None = None
    document_count: int = 0
    active_count: int = 0
    expiring_count: int = 0
    expired_count: int = 0
    latest_document_at: datetime | None = None
    can_upload: bool = False


__all__ = ["DocumentFolder"]
