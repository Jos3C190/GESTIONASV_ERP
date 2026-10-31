"""Read-only report snapshots shared by PDF and spreadsheet renderers."""

from dataclasses import dataclass, field
from decimal import Decimal

ReportValue = str | Decimal


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[ReportValue, ...], ...]
    widths: tuple[float, ...]
    numeric_formats: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TabularReport:
    title: str
    code: str
    company_name: str
    metadata: tuple[tuple[str, str], ...]
    sections: tuple[ReportSection, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcurementReportContext:
    company_name: str
    nit: str = ""
    nrc: str = ""
    purchase_code: str = ""
    order_code: str = ""
    supplier_name: str = ""
    product_labels: dict[int, tuple[str, str]] = field(default_factory=dict)
    unit_labels: dict[int, str] = field(default_factory=dict)
