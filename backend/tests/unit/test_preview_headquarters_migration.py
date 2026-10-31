from __future__ import annotations

from scripts.preview_headquarters_migration import (
    _company_address_errors,
    _legacy_shape_errors,
)


class _Rows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _Rows:
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _Connection:
    def __init__(
        self,
        *,
        unassigned: list[dict[str, object]] | None = None,
        missing_address: bool = False,
    ) -> None:
        self.unassigned = unassigned or []
        self.missing_address = missing_address
        self.statements: list[str] = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append(sql)
        if "SELECT id, company_id FROM warehouses" in sql:
            return _Rows(self.unassigned)
        if "SELECT EXISTS (SELECT 1 FROM companies" in sql:
            return _Scalar(self.missing_address)
        raise AssertionError(f"Consulta inesperada: {sql}")


class _Scalar:
    def __init__(self, value: object) -> None:
        self.value = value


class _ScalarConnection(_Connection):
    def scalar(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append(sql)
        if "SELECT EXISTS (SELECT 1 FROM companies" not in sql:
            raise AssertionError(f"Consulta inesperada: {sql}")
        return self.missing_address


def test_preview_reports_unassigned_noncentral_warehouses() -> None:
    connection = _Connection(unassigned=[{"id": "warehouse-1", "company_id": "company-1"}])

    errors = _legacy_shape_errors(connection)

    assert errors == ["Almacenes sin sucursal que no son centrales: warehouse-1."]
    assert "branch_id IS NULL AND NOT is_central" in connection.statements[0]


def test_preview_rejects_null_or_blank_company_address_using_migration_rule() -> None:
    connection = _ScalarConnection(missing_address=True)

    errors = _company_address_errors(connection, "company-1")

    assert errors == ["company-1: falta dirección de la empresa (nula o vacía)."]
    assert "address IS NULL OR btrim(address) = ''" in connection.statements[0]


def test_preview_accepts_nonblank_company_address() -> None:
    connection = _ScalarConnection(missing_address=False)

    assert _company_address_errors(connection, "company-1") == []
