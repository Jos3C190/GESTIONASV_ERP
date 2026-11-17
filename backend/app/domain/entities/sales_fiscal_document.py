"""Documento fiscal del pedido: del pedido confirmado a la solicitud del servicio DTE.

El ERP es dueño de la venta y del cálculo fiscal (plan de Ventas, sección 6.4). Este módulo arma,
sin tocar la base, lo que se le pide al servicio en el contrato v2:

- el snapshot del emisor (empresa, establecimiento de la sucursal y punto de venta) con el hash
  SHA-256 de su JSON canónico, el mismo que el servicio recalcula para aceptarlo;
- el receptor según el documento (factura o crédito fiscal);
- las líneas, el descuento global en el resumen, la condición, la retención y la percepción;
- la conciliación de totales: antes de enviar (la solicitud cuadra con el pedido) y después
  (el JSON que devolvió el servicio cuadra con el pedido).

Fuentes: esquemas oficiales ``fe-f-v2`` y ``fe-ccf-v3``, Catálogos de Hacienda v1.1 (CAT-009,
CAT-011, CAT-014, CAT-016, CAT-017 y CAT-022).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import OperatingMode
from app.domain.entities.product_fiscal import DteItemType
from app.domain.entities.sales_tax import cent_round

INVOICE = "01"
TAX_CREDIT = "03"
INVOICEABLE_DOCUMENTS = (INVOICE, TAX_CREDIT)

#: CAT-014: 59 = Unidad; 99 = Otra, la que pide Hacienda para los servicios.
DEFAULT_UNIT = 59
SERVICE_UNIT = 99
#: CAT-017: 01 = Billetes y monedas; 99 = Otros (venta a crédito, aún sin cobro).
CASH_PAYMENT = "01"
CREDIT_PAYMENT = "99"
#: CAT-016: 1 = contado, 2 = crédito.
CASH = 1
CREDIT = 2

ZERO = Decimal("0")
HUNDRED = Decimal("100")
_CODE_LENGTH = 25
_DESCRIPTION_LENGTH = 1000
_MIN_CONTACT = 8
_MIN_EMAIL = 6


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class FiscalDocumentStatus(StrEnum):
    PENDING = "pending"
    CONTINGENCY = "contingency"
    """Generado sin comunicación con Hacienda: tiene número y versión legible, espera el sello."""
    ISSUED = "issued"
    """Sellado por Hacienda."""
    SIMULATED = "simulated"
    REJECTED = "rejected"
    FAILED = "failed"
    """No llegó a emitirse; el pedido se puede volver a facturar."""


#: Estados que ya tienen identidad fiscal y bloquean una nueva emisión del pedido.
ACTIVE_STATUSES = (
    FiscalDocumentStatus.PENDING,
    FiscalDocumentStatus.CONTINGENCY,
    FiscalDocumentStatus.ISSUED,
    FiscalDocumentStatus.SIMULATED,
    FiscalDocumentStatus.REJECTED,
)
#: Estados que se pueden reintentar con la misma clave de idempotencia.
RETRYABLE_STATUSES = (FiscalDocumentStatus.PENDING, FiscalDocumentStatus.FAILED)


class FiscalMode(StrEnum):
    """Modo del servicio DTE (``DTE_MODE``)."""

    SIMULATED = "simulated"
    TEST = "hacienda-test"
    PRODUCTION = "production"


def fiscal_mode(mode: OperatingMode) -> FiscalMode:
    return {
        OperatingMode.SIMULATED: FiscalMode.SIMULATED,
        OperatingMode.TEST: FiscalMode.TEST,
        OperatingMode.PRODUCTION: FiscalMode.PRODUCTION,
    }[mode]


def service_status(estado: str | None) -> FiscalDocumentStatus | None:
    """Estado del ERP para la respuesta del servicio; ``None`` si aún no hay resultado."""

    return {
        "SIMULADO": FiscalDocumentStatus.SIMULATED,
        "TRANSMITIDO": FiscalDocumentStatus.ISSUED,
        "PROCESADO": FiscalDocumentStatus.ISSUED,
        "RECHAZADO": FiscalDocumentStatus.REJECTED,
        # Generado en contingencia: espera el evento y su transmisión (V4a).
        "CONTINGENCIA": FiscalDocumentStatus.CONTINGENCY,
        "CONTINGENCIA_REPORTADA": FiscalDocumentStatus.CONTINGENCY,
    }.get(estado or "")


#: CAT-005, tipo de contingencia.
CONTINGENCY_TYPES = {
    1: "No disponibilidad de sistema del MH",
    2: "No disponibilidad de sistema del emisor",
    3: "Falla en el suministro de servicio de Internet del Emisor",
    4: "Falla en el suministro de servicio de energía eléctrica del emisor",
    5: "Otro",
}


def contingency_details(dte_json: dict[str, Any] | None) -> tuple[int, str | None] | None:
    """Tipo (CAT-005) y motivo de la contingencia del JSON del documento; ``None`` si no la tiene."""

    identification = (dte_json or {}).get("identificacion") or {}
    kind = identification.get("tipoContingencia")
    if kind not in CONTINGENCY_TYPES:
        return None
    reason = identification.get("motivoContin")
    return int(kind), str(reason) if reason else None


# --- emisor ---


@dataclass(frozen=True, slots=True)
class IssuerAddress:
    department_code: str
    department_name: str
    municipality_code: str
    municipality_name: str
    district_code: str
    district_name: str
    complement: str
    geo_catalog_version: str


@dataclass(frozen=True, slots=True)
class IssuerSnapshot:
    """Emisor en tres niveles: empresa, establecimiento de la sucursal y punto de venta."""

    legal_name: str
    trade_name: str | None
    nit: str
    nrc: str
    activity_code: str
    activity_description: str
    activity_catalog_version: str
    address: IssuerAddress
    phone: str
    email: str
    establishment_type: str
    establishment_code: str
    """Código de cuatro caracteres del ERP, por ejemplo ``M001``."""
    point_of_sale_code: str
    """Código de cuatro caracteres del ERP, por ejemplo ``P001``."""

    def canonical(self) -> dict[str, Any]:
        """El JSON que el servicio rehace para validar el hash (``issuerContractV2.js``)."""

        a = self.address
        return {
            "legalName": self.legal_name,
            "tradeName": self.trade_name,
            "nit": self.nit,
            "nrc": self.nrc,
            "economicActivityCode": self.activity_code,
            "economicActivityDescription": self.activity_description,
            "activityCatalogVersion": self.activity_catalog_version,
            "address": {
                "departmentCode": a.department_code,
                "departmentName": a.department_name,
                "municipalityCode": a.municipality_code,
                "municipalityName": a.municipality_name,
                "districtCode": a.district_code,
                "districtName": a.district_name,
                "complement": a.complement,
                "geoCatalogVersion": a.geo_catalog_version,
            },
            "phone": self.phone,
            "email": self.email,
            "establishmentType": self.establishment_type,
            "mhEstablishmentCode": self.establishment_code[1:],
            "mhPointOfSaleCode": self.point_of_sale_code[1:],
            "internalEstablishmentCode": self.establishment_code,
            "internalPointOfSaleCode": self.point_of_sale_code,
        }

    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.canonical()).encode("utf-8")).hexdigest()

    def record(self) -> dict[str, Any]:
        """Lo que guarda el documento fiscal: el snapshot canónico y su hash."""

        return {**self.canonical(), "snapshotSha256": self.sha256()}

    def to_service(self) -> dict[str, Any]:
        """El emisor del contrato v2."""

        digest = self.sha256()
        a = self.address
        return {
            "revisionId": f"erp-{digest[:20]}",
            "snapshotSha256": digest,
            "nit": self.nit,
            "nrc": self.nrc,
            "nombre": self.legal_name,
            "nombreComercial": self.trade_name,
            "codActividad": self.activity_code,
            "descActividad": self.activity_description,
            "activityCatalogVersion": self.activity_catalog_version,
            "direccion": {
                "departamento": a.department_code,
                "departmentName": a.department_name,
                "municipio": a.municipality_code,
                "municipalityName": a.municipality_name,
                "distrito": a.district_code,
                "districtName": a.district_name,
                "complemento": a.complement,
                "geoCatalogVersion": a.geo_catalog_version,
            },
            "telefono": self.phone,
            "correo": self.email,
            "tipoEstablecimiento": self.establishment_type,
            "codEstablecimientoMH": self.establishment_code[1:],
            "codPuntoVentaMH": self.point_of_sale_code[1:],
            "codEstable": self.establishment_code,
            "codPuntoVenta": self.point_of_sale_code,
        }


def canonical_json(value: Any) -> str:
    """``JSON.stringify`` de un objeto con las llaves ordenadas, como lo hace el servicio."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class IssuerFacts:
    """Lo que el repositorio encontró del emisor, antes de validarlo."""

    legal_name: str | None
    trade_name: str | None
    nit: str | None
    nrc: str | None
    activity_code: str | None
    activity_description: str | None
    activity_catalog_version: str
    address: IssuerAddress | None
    phone: str | None
    email: str | None
    establishment_type: str
    establishment_code: str
    point_of_sale_code: str


def issuer_snapshot(facts: IssuerFacts) -> IssuerSnapshot:
    """Valida los datos del emisor y arma su snapshot; dice todo lo que falta de una vez."""

    missing: list[str] = []
    if not facts.legal_name:
        missing.append("el nombre o razón social de la empresa")
    if not facts.nit:
        missing.append("un NIT válido de la empresa")
    if not facts.nrc:
        missing.append("un NRC válido de la empresa")
    if not (facts.activity_code and facts.activity_description):
        missing.append("la actividad económica del establecimiento o la principal de la empresa")
    if facts.address is None or not facts.address.complement:
        missing.append("la dirección con departamento, municipio y distrito de la sucursal")
    if not facts.phone or len(facts.phone) < _MIN_CONTACT:
        missing.append("el teléfono para DTE (8 caracteres o más)")
    if not facts.email or len(facts.email) < _MIN_EMAIL:
        missing.append("el correo para DTE")
    if missing:
        raise _rule(
            "Falta configurar el emisor antes de facturar: " + "; ".join(missing) + ".",
            "sales_invoice_issuer_incomplete",
        )
    return IssuerSnapshot(
        legal_name=facts.legal_name or "",
        trade_name=facts.trade_name or None,
        nit=facts.nit or "",
        nrc=facts.nrc or "",
        activity_code=facts.activity_code or "",
        activity_description=facts.activity_description or "",
        activity_catalog_version=facts.activity_catalog_version,
        address=facts.address,  # type: ignore[arg-type]
        phone=facts.phone or "",
        email=facts.email or "",
        establishment_type=facts.establishment_type,
        establishment_code=facts.establishment_code,
        point_of_sale_code=facts.point_of_sale_code,
    )


# --- receptor ---


@dataclass(frozen=True, slots=True)
class ReceiverAddress:
    department_code: str
    municipality_code: str
    district_code: str
    complement: str


@dataclass(frozen=True, slots=True)
class ReceiverFacts:
    """El cliente del pedido, con sus datos fiscales del momento de facturar."""

    name: str
    commercial_name: str | None
    is_generic: bool
    is_taxpayer: bool
    document_type: str | None
    """CAT-022: 36 NIT, 13 DUI, 02 carné de residente, 03 pasaporte, 37 otro."""
    document_number: str | None
    nrc: str | None
    activity_code: str | None
    activity_description: str | None
    address: ReceiverAddress | None
    phone: str | None
    email: str | None


_NIT = "36"
_DUI = "13"


def _document_number(document_type: str, number: str) -> str:
    """Hacienda pide el DUI con guion antes del dígito verificador (``01234567-8``)."""

    if document_type == _DUI and "-" not in number:
        return f"{number[:-1]}-{number[-1]}"
    return number


def _contact(value: str | None, minimum: int) -> str | None:
    return value if value and len(value) >= minimum else None


def _address(address: ReceiverAddress | None) -> dict[str, str] | None:
    if address is None:
        return None
    return {
        "departamento": address.department_code,
        "municipio": address.municipality_code,
        "distrito": address.district_code,
        "complemento": address.complement[:200],
    }


def build_receiver(document_type: str, receiver: ReceiverFacts) -> dict[str, Any] | None:
    """Receptor del DTE. La factura a consumidor final genérico no lleva receptor."""

    if document_type == TAX_CREDIT:
        missing: list[str] = []
        if not receiver.is_taxpayer:
            missing.append("el cliente no es contribuyente de IVA")
        if receiver.document_type not in (_NIT, _DUI) or not receiver.document_number:
            missing.append("NIT o DUI homologado")
        if not receiver.nrc:
            missing.append("NRC")
        if not (receiver.activity_code and receiver.activity_description):
            missing.append("actividad económica")
        if receiver.address is None:
            missing.append("dirección con departamento, municipio y distrito")
        if missing:
            raise _rule(
                "El cliente no puede recibir crédito fiscal: " + "; ".join(missing) + ".",
                "sales_invoice_receiver_incomplete",
            )
        return {
            "nit": receiver.document_number,
            "nrc": receiver.nrc,
            "nombre": receiver.name[:250],
            "codActividad": receiver.activity_code,
            "descActividad": (receiver.activity_description or "")[:150],
            "nombreComercial": (receiver.commercial_name or "")[:150] or None,
            "direccion": _address(receiver.address),
            "telefono": _contact(receiver.phone, _MIN_CONTACT),
            "correo": _contact(receiver.email, _MIN_EMAIL),
        }
    if receiver.is_generic:
        return None
    identified = bool(receiver.document_type and receiver.document_number)
    return {
        "tipoDocumento": receiver.document_type if identified else None,
        "numDocumento": (
            _document_number(receiver.document_type or "", receiver.document_number or "")
            if identified
            else None
        ),
        "nrc": receiver.nrc if receiver.document_type == _NIT else None,
        "nombre": receiver.name[:250],
        "codActividad": receiver.activity_code if receiver.activity_description else None,
        "descActividad": (receiver.activity_description or "")[:150] or None,
        "direccion": _address(receiver.address),
        "telefono": _contact(receiver.phone, _MIN_CONTACT),
        "correo": _contact(receiver.email, _MIN_EMAIL),
    }


# --- líneas y resumen ---


@dataclass(frozen=True, slots=True)
class FiscalLine:
    """Una línea del pedido, ya calculada por el motor fiscal en la forma del documento."""

    sku: str
    description: str
    item_type: str
    unit_code: str | None
    """CAT-014 de la unidad en la empresa; sin él se informa 59 (Unidad)."""
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal


@dataclass(frozen=True, slots=True)
class OrderFiscalTotals:
    document_type: str
    global_discount_percent: Decimal
    total_not_subject: Decimal
    total_exempt: Decimal
    total_taxed: Decimal
    subtotal_sales: Decimal
    total_discount: Decimal
    subtotal: Decimal
    vat: Decimal
    vat_perceived: Decimal
    vat_withheld: Decimal
    total: Decimal
    on_credit: bool
    credit_days: int


def _number(value: Decimal) -> float | int:
    """Importe para el JSON: el servicio y los esquemas trabajan con números."""

    return int(value) if value == value.to_integral_value() else float(value)


def build_items(lines: list[FiscalLine] | tuple[FiscalLine, ...]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in lines:
        is_service = line.item_type == DteItemType.SERVICES.value
        unit = SERVICE_UNIT if is_service else int(line.unit_code or DEFAULT_UNIT)
        items.append(
            {
                "tipoItem": int(line.item_type),
                "codigo": line.sku[:_CODE_LENGTH] or None,
                "uniMedida": unit,
                "descripcion": line.description[:_DESCRIPTION_LENGTH],
                "cantidad": _number(line.quantity),
                "precioUni": _number(line.unit_price),
                "montoDescu": _number(line.discount),
                "ventaNoSuj": _number(line.not_subject),
                "ventaExenta": _number(line.exempt),
                "ventaGravada": _number(line.taxed),
            }
        )
    return items


@dataclass(frozen=True, slots=True)
class GlobalDiscount:
    taxed: Decimal
    exempt: Decimal
    not_subject: Decimal

    @property
    def total(self) -> Decimal:
        return self.taxed + self.exempt + self.not_subject


def global_discount(totals: OrderFiscalTotals) -> GlobalDiscount:
    """El descuento global por naturaleza, con la misma regla del motor de cotización."""

    share = totals.global_discount_percent / HUNDRED
    return GlobalDiscount(
        taxed=cent_round(totals.total_taxed * share),
        exempt=cent_round(totals.total_exempt * share),
        not_subject=cent_round(totals.total_not_subject * share),
    )


def build_request(
    issuer: IssuerSnapshot,
    receiver: dict[str, Any] | None,
    lines: list[FiscalLine] | tuple[FiscalLine, ...],
    totals: OrderFiscalTotals,
) -> dict[str, Any]:
    """Cuerpo de ``POST /api/dte/v2/factura`` o ``/v2/ccf``. Concilia antes de devolverlo."""

    if totals.document_type not in INVOICEABLE_DOCUMENTS:
        raise _rule(
            "Por ahora se factura con factura o comprobante de crédito fiscal.",
            "sales_invoice_document_unsupported",
        )
    discount = global_discount(totals)
    require_request_reconciled(lines, totals, discount)
    is_ccf = totals.document_type == TAX_CREDIT
    adjustments: dict[str, Any] = {
        "condicionOperacion": CREDIT if totals.on_credit else CASH,
        "descuentoGlobalEnResumen": True,
        "ivaRete": _number(totals.vat_withheld),
    }
    if totals.on_credit:
        adjustments["plazoDias"] = totals.credit_days
    if is_ccf:
        adjustments["ivaPerci"] = _number(totals.vat_perceived)
    request: dict[str, Any] = {
        "emisor": issuer.to_service(),
        "receptor": receiver,
        "items": build_items(lines),
        "ajustes": adjustments,
        "pago": {
            "codigo": CREDIT_PAYMENT if totals.on_credit else CASH_PAYMENT,
            "montoPago": _number(totals.total),
            "referencia": None,
            "numPagoElectronico": None,
        },
    }
    if discount.total > ZERO:
        request["descuentoGlobal"] = {
            "gravada": _number(discount.taxed),
            "exenta": _number(discount.exempt),
            "noSuj": _number(discount.not_subject),
        }
    return request


def require_request_reconciled(
    lines: list[FiscalLine] | tuple[FiscalLine, ...],
    totals: OrderFiscalTotals,
    discount: GlobalDiscount,
) -> None:
    """La solicitud debe cuadrar al centavo con lo que guardó el pedido; si no, no se envía."""

    differences: list[str] = []

    def check(label: str, sent: Decimal, stored: Decimal) -> None:
        if cent_round(sent) != stored:
            differences.append(f"{label}: {cent_round(sent)} frente a {stored}")

    check("no sujetas", sum((ln.not_subject for ln in lines), ZERO), totals.total_not_subject)
    check("exentas", sum((ln.exempt for ln in lines), ZERO), totals.total_exempt)
    check("gravadas", sum((ln.taxed for ln in lines), ZERO), totals.total_taxed)
    line_discounts = cent_round(sum((ln.discount for ln in lines), ZERO))
    check("descuentos", line_discounts + discount.total, totals.total_discount)
    check("subtotal", totals.subtotal_sales - discount.total, totals.subtotal)
    added = totals.vat + totals.vat_perceived if totals.document_type == TAX_CREDIT else ZERO
    check("total", totals.subtotal + added - totals.vat_withheld, totals.total)
    if totals.on_credit and not 1 <= totals.credit_days <= 365:  # noqa: PLR2004
        differences.append("plazo de crédito fuera de 1 a 365 días")
    if differences:
        raise _rule(
            "Los totales del pedido no cuadran con sus líneas (" + "; ".join(differences) + "). "
            "Edita y vuelve a confirmar el pedido antes de facturar.",
            "sales_invoice_totals_mismatch",
        )


def _cents(value: Any) -> Decimal:
    return cent_round(Decimal(str(value if value is not None else 0)))


def dte_differences(dte: dict[str, Any], totals: OrderFiscalTotals) -> list[str]:
    """Diferencias entre el resumen del JSON del servicio y los totales del pedido."""

    summary = dte.get("resumen") or {}
    is_ccf = totals.document_type == TAX_CREDIT
    if is_ccf:
        tributes = summary.get("tributos") or []
        vat = sum((_cents(t.get("valor")) for t in tributes if t.get("codigo") == "20"), ZERO)
    else:
        vat = _cents(summary.get("totalIva"))
    pairs = [
        ("totalNoSuj", _cents(summary.get("totalNoSuj")), totals.total_not_subject),
        ("totalExenta", _cents(summary.get("totalExenta")), totals.total_exempt),
        ("totalGravada", _cents(summary.get("totalGravada")), totals.total_taxed),
        ("totalDescu", _cents(summary.get("totalDescu")), totals.total_discount),
        ("subTotal", _cents(summary.get("subTotal")), totals.subtotal),
        ("IVA", vat, totals.vat),
        ("ivaRete", _cents(summary.get("ivaRete")), totals.vat_withheld),
        ("totalPagar", _cents(summary.get("totalPagar")), totals.total),
    ]
    if is_ccf:
        pairs.append(("ivaPerci", _cents(summary.get("ivaPerci")), totals.vat_perceived))
    return [f"{name}: {sent} frente a {stored}" for name, sent, stored in pairs if sent != stored]


# --- reglas del pedido ---


def require_invoiceable(
    order_status: str,
    document_type: str,
    document_enabled: bool,
    has_active_document: bool,
) -> None:
    if order_status != "confirmed":
        raise _rule("Solo se factura un pedido confirmado.", "sales_invoice_order_not_confirmed")
    if has_active_document:
        raise _rule(
            "El pedido ya tiene su documento fiscal. Si falló, reintenta su emisión.",
            "sales_invoice_already_issued",
        )
    if document_type not in INVOICEABLE_DOCUMENTS:
        raise _rule(
            "Por ahora se factura con factura o comprobante de crédito fiscal.",
            "sales_invoice_document_unsupported",
        )
    if not document_enabled:
        raise _rule(
            "La empresa no tiene habilitado este tipo de documento para emitir.",
            "sales_invoice_document_disabled",
        )


def require_retryable(status: FiscalDocumentStatus) -> None:
    if status not in RETRYABLE_STATUSES:
        raise _rule(
            "Solo se reintenta un documento pendiente o fallido.",
            "sales_invoice_not_retryable",
        )
