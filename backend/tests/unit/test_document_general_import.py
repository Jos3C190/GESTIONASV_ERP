import uuid
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from types import SimpleNamespace

import pytest

from app.application.documents.general_import_service import DocumentGeneralImportService
from app.core.exceptions import ValidationError


def test_import_paths_reject_traversal_and_windows_separators() -> None:
    assert DocumentGeneralImportService._path('Contratos/2026/contrato.pdf') == (
        'Contratos',
        '2026',
        'contrato.pdf',
    )
    for value in ('', '/root/file.pdf', r'root\\file.pdf', 'root/../file.pdf', 'root//file.pdf'):
        with pytest.raises(ValidationError):
            DocumentGeneralImportService._path(value)


def test_import_suffix_preserves_file_extension() -> None:
    assert DocumentGeneralImportService._suffix_name('manual.pdf', 1) == 'manual (1).pdf'
    assert DocumentGeneralImportService._suffix_name('Contratos', 2) == 'Contratos (2)'
    assert PurePosixPath(DocumentGeneralImportService._suffix_name('a.tar.gz', 1)).suffix == '.gz'


def test_import_metadata_rejects_inverted_dates() -> None:
    with pytest.raises(ValidationError, match="fecha de vencimiento"):
        DocumentGeneralImportService._metadata(
            {"issued_on": date(2026, 9, 10).isoformat(), "expires_on": date(2026, 9, 9).isoformat()}
        )


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[object]:
        return self.rows


class _MaintenanceSession:
    def __init__(self, import_row: object, items: list[object]) -> None:
        self.import_row = import_row
        self.items = items
        self.calls = 0
        self.audit_rows: list[object] = []

    async def execute(self, _statement: object) -> _Result:
        self.calls += 1
        return _Result([self.import_row] if self.calls == 1 else [item for item in self.items if getattr(item, "status", None) in {"ready", "authorized"}])

    def add(self, item: object) -> None:
        self.audit_rows.append(item)


async def test_expired_import_cancels_pending_items() -> None:
    from app.infrastructure.document_maintenance import _expire_imports

    import_row = SimpleNamespace(
        id=uuid.uuid4(), company_id=uuid.uuid4(), actor_id=uuid.uuid4(), root_entry_id=None,
        status="running", completed_at=None,
    )
    pending = SimpleNamespace(status="ready", failure_code=None, failure_message=None)
    completed = SimpleNamespace(status="completed", failure_code=None, failure_message=None)
    session = _MaintenanceSession(import_row, [pending, completed])

    assert await _expire_imports(session, datetime.now(UTC)) == 1
    assert import_row.status == "expired"
    assert pending.status == "cancelled"
    assert pending.failure_code == "document_import_expired"
    assert completed.status == "completed"
    assert getattr(session.audit_rows[0], "action") == "GENERAL_FOLDER_IMPORT_EXPIRED"
