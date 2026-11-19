"""Reglas del emisor de DTE: perfil, establecimientos, puntos de venta y documentos.

Fuentes: Catálogos de Hacienda v1.1 (CAT-002, CAT-009, CAT-029) y esquemas oficiales del
DTE, donde el número de control sigue el patrón ``DTE-TT-(M|B|S|P)NNNPNNN-NNNNNNNNNNNNNNN``.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.core.exceptions import BusinessRuleError


class OperatingMode(StrEnum):
    SIMULATED = "simulated"
    TEST = "test"
    PRODUCTION = "production"


class TaxpayerCategory(StrEnum):
    LARGE = "large"
    MEDIUM = "medium"
    OTHER = "other"


class PersonType(StrEnum):
    """CAT-029."""

    NATURAL = "1"
    LEGAL = "2"


class EstablishmentType(StrEnum):
    """CAT-009."""

    BRANCH = "01"
    HEADQUARTERS = "02"
    WAREHOUSE = "04"
    YARD = "07"


class CertificationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"


#: Letra del establecimiento en el número de control, según su tipo.
ESTABLISHMENT_PREFIX: dict[EstablishmentType, str] = {
    EstablishmentType.HEADQUARTERS: "M",
    EstablishmentType.BRANCH: "S",
    EstablishmentType.WAREHOUSE: "B",
    EstablishmentType.YARD: "P",
}

#: CAT-002: documentos (01 a 15) y eventos (17 y 18).
DOCUMENT_TYPES: dict[str, str] = {
    "01": "Factura",
    "03": "Comprobante de crédito fiscal",
    "04": "Nota de remisión",
    "05": "Nota de crédito",
    "06": "Nota de débito",
    "07": "Comprobante de retención",
    "08": "Comprobante de liquidación",
    "09": "Documento contable de liquidación",
    "11": "Factura de exportación",
    "14": "Factura de sujeto excluido",
    "15": "Comprobante de donación",
    "17": "Evento de operaciones especiales",
    "18": "Evento de retorno",
}

ACTIVITY_CATALOG = "CAT-019"
_ESTABLISHMENT_CODE = re.compile(r"^[MSBP][0-9]{3}$")
_POINT_OF_SALE_CODE = re.compile(r"^P[0-9]{3}$")
_ACTIVITY_CODE = re.compile(r"^[0-9]{5,6}$")


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def establishment_code(establishment_type: EstablishmentType, number: int) -> str:
    """Arma el código de 4 caracteres (``S001``) a partir del tipo y el correlativo."""
    if not 1 <= number <= 999:  # noqa: PLR2004 - tres dígitos del número de control
        raise _rule(
            "El número del establecimiento debe estar entre 1 y 999.",
            "fiscal_establishment_number_invalid",
        )
    return f"{ESTABLISHMENT_PREFIX[establishment_type]}{number:03d}"


def validate_establishment_code(establishment_type: EstablishmentType, code: str) -> str:
    normalized = code.strip().upper()
    if not _ESTABLISHMENT_CODE.match(normalized) or normalized.endswith("000"):
        raise _rule(
            "El código del establecimiento lleva una letra (M, S, B o P) y tres dígitos, "
            "por ejemplo S001.",
            "fiscal_establishment_code_invalid",
        )
    expected = ESTABLISHMENT_PREFIX[establishment_type]
    if normalized[0] != expected:
        raise _rule(
            f"Un establecimiento de este tipo usa la letra {expected}, por ejemplo {expected}001.",
            "fiscal_establishment_code_type_mismatch",
        )
    return normalized


def validate_point_of_sale_code(code: str) -> str:
    normalized = code.strip().upper()
    if not _POINT_OF_SALE_CODE.match(normalized) or normalized == "P000":
        raise _rule(
            "El código del punto de venta lleva la letra P y tres dígitos, por ejemplo P001.",
            "fiscal_point_of_sale_code_invalid",
        )
    return normalized


def validate_activity_code(code: str) -> str:
    normalized = code.strip()
    if not _ACTIVITY_CODE.match(normalized):
        raise _rule(
            "El código de actividad económica tiene 5 o 6 dígitos.",
            "fiscal_activity_code_invalid",
        )
    return normalized


def dte_nit(value: str | None) -> str | None:
    """NIT como lo pide el DTE: 14 o 9 dígitos, sin guiones. ``None`` si no es válido."""
    digits = re.sub(r"[\s-]", "", value or "")
    return digits if re.fullmatch(r"[0-9]{14}|[0-9]{9}", digits) else None


def dte_nrc(value: str | None) -> str | None:
    """NRC como lo pide el DTE: de 2 a 8 dígitos, sin guion. ``None`` si no es válido."""
    digits = re.sub(r"[\s-]", "", value or "")
    return digits if re.fullmatch(r"[0-9]{2,8}", digits) else None


def require_document_type(document_type: str) -> str:
    if document_type not in DOCUMENT_TYPES:
        raise _rule(
            "Ese tipo de documento no existe en el catálogo de Hacienda.",
            "fiscal_document_type_invalid",
        )
    return document_type


def require_can_enable(
    mode: OperatingMode, document_type: str, status: CertificationStatus
) -> None:
    """En producción solo se emite un documento cuyas pruebas aprobó Hacienda."""
    if mode == OperatingMode.PRODUCTION and status != CertificationStatus.APPROVED:
        raise _rule(
            f"En producción solo se habilita «{DOCUMENT_TYPES[document_type]}» después de "
            "aprobar sus pruebas en el ambiente de Hacienda.",
            "fiscal_document_not_certified",
        )


@dataclass(frozen=True, slots=True)
class IssuerFacts:
    """Lo que hace falta saber de una empresa para decidir si puede emitir en producción."""

    has_nit: bool
    has_nrc: bool
    has_primary_activity: bool
    establishments_with_point_of_sale: int
    enabled_documents: int
    enabled_uncertified_documents: tuple[str, ...] = ()
    hacienda_credentials_tested: bool = False
    """Credenciales de Hacienda cargadas y con la última prueba de conexión correcta (V3d)."""


def production_blockers(facts: IssuerFacts) -> list[str]:
    """Motivos, en español, por los que la empresa aún no puede emitir en producción."""
    reasons: list[str] = []
    if not facts.has_nit:
        reasons.append("Registra en la ficha de la empresa un NIT válido (14 o 9 dígitos).")
    if not facts.has_nrc:
        reasons.append("Registra en la ficha de la empresa un NRC válido (de 2 a 8 dígitos).")
    if not facts.has_primary_activity:
        reasons.append("Marca una actividad económica principal.")
    if facts.establishments_with_point_of_sale == 0:
        reasons.append("Crea un establecimiento activo con al menos un punto de venta activo.")
    if facts.enabled_documents == 0:
        reasons.append("Habilita al menos un tipo de documento.")
    if not facts.hacienda_credentials_tested:
        reasons.append(
            "Carga las credenciales de Hacienda y prueba la conexión (pestaña Hacienda)."
        )
    for document_type in facts.enabled_uncertified_documents:
        reasons.append(
            f"«{DOCUMENT_TYPES[document_type]}» está habilitado pero sus pruebas no están "
            "aprobadas."
        )
    return reasons


def require_mode_change(target: OperatingMode, facts: IssuerFacts) -> None:
    if target == OperatingMode.TEST and not facts.hacienda_credentials_tested:
        raise _rule(
            "Para emitir en el ambiente de pruebas de Hacienda carga las credenciales y "
            "prueba la conexión en la pestaña Hacienda.",
            "fiscal_test_not_ready",
        )
    if target != OperatingMode.PRODUCTION:
        return
    reasons = production_blockers(facts)
    if reasons:
        raise _rule(
            "La empresa aún no puede emitir en producción: " + " ".join(reasons),
            "fiscal_production_not_ready",
        )


# --- Read models shared by the repository port, use cases and API ---


@dataclass(frozen=True, slots=True)
class CatalogItem:
    catalog_code: str
    group_code: str
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class FiscalProfile:
    company_id: uuid.UUID
    taxpayer_category: TaxpayerCategory
    person_type: PersonType
    operating_mode: OperatingMode
    dte_email: str | None
    dte_phone: str | None
    configured: bool
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EconomicActivity:
    id: uuid.UUID
    code: str
    description: str
    is_primary: bool
    renta_operation_type: int | None = None
    """Clasificación de renta sugerida para sus ventas (F-07, V4b2)."""
    renta_income_type: int | None = None


@dataclass(frozen=True, slots=True)
class PointOfSale:
    id: uuid.UUID
    establishment_id: uuid.UUID
    code: str
    name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class EstablishmentAddress:
    """La dirección del DTE: la de la sucursal donde ocurre la operación."""

    department: str
    department_code: str | None
    municipality: str
    municipality_code: str | None
    district: str
    district_code: str | None
    complement: str

    @property
    def complete(self) -> bool:
        return bool(self.department_code and self.municipality_code and self.district_code)


@dataclass(frozen=True, slots=True)
class Establishment:
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    establishment_type: EstablishmentType
    code: str
    activity_id: uuid.UUID | None
    activity_code: str | None
    is_active: bool
    address: EstablishmentAddress
    phone: str | None
    email: str | None
    points_of_sale: tuple[PointOfSale, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Datos del emisor que viven en la ficha de la empresa."""

    name: str
    commercial_name: str
    nit: str
    nrc: str


@dataclass(frozen=True, slots=True)
class BranchOption:
    id: uuid.UUID
    name: str
    code: str | None
    is_headquarters: bool
    establishment_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class DocumentTypeSetting:
    document_type: str
    name: str
    is_enabled: bool
    certification_status: CertificationStatus
    certified_at: datetime | None
    notes: str | None
