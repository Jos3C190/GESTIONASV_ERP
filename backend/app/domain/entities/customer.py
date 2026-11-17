"""Clientes con identidad fiscal: normalización, reglas por tipo y documentos que reciben.

Fuentes: esquemas oficiales del DTE (receptor de factura 01, crédito fiscal 03 y
exportación 11) y Catálogos de Hacienda v1.1 (CAT-019, CAT-020, CAT-022 y CAT-029).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import PersonType, TaxpayerCategory, dte_nit, dte_nrc


class CustomerType(StrEnum):
    FINAL_CONSUMER = "final_consumer"
    TAXPAYER = "taxpayer"
    FOREIGN = "foreign"


class IdentityDocument(StrEnum):
    """CAT-022."""

    NIT = "36"
    DUI = "13"
    RESIDENT_CARD = "02"
    PASSPORT = "03"
    OTHER = "37"


INVOICE = "01"
TAX_CREDIT = "03"
EXPORT_INVOICE = "11"
MAX_CREDIT_DAYS = 365
GENERIC_NAME = "Consumidor final"
_DUI = re.compile(r"^[0-9]{9}$")


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def _clean(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text or None


def normalize_document(document_type: IdentityDocument, number: str) -> str:
    """Número de documento como lo lleva el DTE: NIT y DUI solo con dígitos."""
    if document_type == IdentityDocument.NIT:
        nit = dte_nit(number)
        if nit is None:
            raise _rule(
                "El NIT lleva 14 dígitos, o 9 si es un DUI homologado.",
                "customer_nit_invalid",
            )
        return nit
    if document_type == IdentityDocument.DUI:
        digits = re.sub(r"[\s-]", "", number)
        if not _DUI.match(digits):
            raise _rule("El DUI lleva 9 dígitos, por ejemplo 01234567-8.", "customer_dui_invalid")
        return digits
    text = re.sub(r"\s", "", number).upper()
    if not 3 <= len(text) <= 20:  # noqa: PLR2004 - límites del esquema del DTE
        raise _rule(
            "El número de documento debe tener entre 3 y 20 caracteres.",
            "customer_document_invalid",
        )
    return text


@dataclass(frozen=True, slots=True)
class Geography:
    department_id: uuid.UUID
    municipality_id: uuid.UUID
    district_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CustomerDraft:
    """Valores que se guardan; ``validate_draft`` los normaliza y comprueba."""

    customer_type: CustomerType
    name: str
    person_type: PersonType = PersonType.NATURAL
    taxpayer_category: TaxpayerCategory | None = None
    is_withholding_agent: bool = False
    commercial_name: str | None = None
    document_type: IdentityDocument | None = None
    document_number: str | None = None
    nrc: str | None = None
    activity_code: str | None = None
    geography: Geography | None = None
    address_line: str | None = None
    country_code: str | None = None
    phone: str | None = None
    email: str | None = None
    credit_days: int = 0
    credit_limit: Decimal | None = None
    seller_employee_id: uuid.UUID | None = None
    price_list_id: uuid.UUID | None = None
    discount_percent: Decimal = Decimal("0")


def validate_draft(draft: CustomerDraft) -> CustomerDraft:  # noqa: C901 - una regla por campo
    name = _clean(draft.name)
    if name is None or len(name) < 2:  # noqa: PLR2004
        raise _rule("Escribe el nombre o la razón social del cliente.", "customer_name_required")
    is_taxpayer = draft.customer_type == CustomerType.TAXPAYER
    is_foreign = draft.customer_type == CustomerType.FOREIGN
    if is_taxpayer and draft.taxpayer_category is None:
        raise _rule(
            "Indica si el contribuyente es grande, mediano u otro.",
            "customer_taxpayer_category_required",
        )
    if (draft.document_type is None) != (_clean(draft.document_number) is None):
        raise _rule(
            "Indica el tipo y el número del documento de identidad, o ninguno.",
            "customer_document_incomplete",
        )
    number = None
    if draft.document_type is not None and draft.document_number:
        if is_taxpayer and draft.document_type not in (IdentityDocument.NIT, IdentityDocument.DUI):
            raise _rule(
                "Un contribuyente se identifica con su NIT o su DUI homologado.",
                "customer_taxpayer_document_invalid",
            )
        number = normalize_document(draft.document_type, draft.document_number)
    nrc = None
    if _clean(draft.nrc):
        nrc = dte_nrc(draft.nrc)
        if nrc is None:
            raise _rule("El NRC lleva de 2 a 8 dígitos.", "customer_nrc_invalid")
    activity = _clean(draft.activity_code)
    if activity is not None and not re.fullmatch(r"[0-9]{5,6}", activity):
        raise _rule(
            "El código de actividad económica tiene 5 o 6 dígitos.", "customer_activity_invalid"
        )
    if is_foreign:
        if not _clean(draft.country_code):
            raise _rule("Indica el país del cliente del extranjero.", "customer_country_required")
        if draft.geography is not None:
            raise _rule(
                "Un cliente del extranjero no lleva departamento ni municipio de El Salvador.",
                "customer_foreign_geography",
            )
    elif draft.country_code:
        raise _rule("Solo los clientes del extranjero llevan país.", "customer_country_not_foreign")
    if not 0 <= draft.credit_days <= MAX_CREDIT_DAYS:
        raise _rule("El plazo de crédito va de 0 a 365 días.", "customer_credit_days_invalid")
    if draft.credit_limit is not None and draft.credit_limit < 0:
        raise _rule("El límite de crédito no puede ser negativo.", "customer_credit_limit_invalid")
    return replace(
        draft,
        name=name,
        taxpayer_category=draft.taxpayer_category if is_taxpayer else None,
        commercial_name=_clean(draft.commercial_name),
        document_number=number,
        document_type=draft.document_type if number else None,
        nrc=nrc,
        activity_code=activity,
        address_line=_clean(draft.address_line),
        country_code=_clean(draft.country_code.upper() if draft.country_code else None),
        phone=_clean(draft.phone),
        email=_clean(draft.email.lower() if draft.email else None),
    )


@dataclass(frozen=True, slots=True)
class CustomerAddress:
    department: str | None = None
    department_code: str | None = None
    municipality: str | None = None
    municipality_code: str | None = None
    district: str | None = None
    district_code: str | None = None

    @property
    def coded(self) -> bool:
        return bool(self.department_code and self.municipality_code and self.district_code)


@dataclass(frozen=True, slots=True)
class DeliveryAddress:
    id: uuid.UUID
    label: str
    address_line: str
    geography: Geography | None
    address: CustomerAddress
    latitude: Decimal | None
    longitude: Decimal | None
    contact_name: str | None
    phone: str | None
    is_default: bool
    is_active: bool


@dataclass(frozen=True, slots=True)
class SellerOption:
    """Empleado activo de la empresa que puede quedar como vendedor del cliente."""

    id: uuid.UUID
    code: str
    name: str
    position: str | None


@dataclass(frozen=True, slots=True)
class Customer:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    draft: CustomerDraft
    address: CustomerAddress
    activity_name: str | None
    country_name: str | None
    is_active: bool
    is_generic: bool
    branch_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    delivery_addresses: tuple[DeliveryAddress, ...] = field(default=())
    seller_name: str | None = None
    price_list_name: str | None = None
    anonymized_at: datetime | None = None

    @property
    def tax_credit_missing(self) -> list[str]:
        return tax_credit_missing(self.draft, self.address)

    @property
    def receivable_documents(self) -> list[str]:
        return receivable_documents(self.draft, self.address)


def tax_credit_missing(draft: CustomerDraft, address: CustomerAddress) -> list[str]:
    """Lo que le falta a un cliente para recibir comprobante de crédito fiscal."""
    if draft.customer_type != CustomerType.TAXPAYER:
        return ["Solo un contribuyente de IVA recibe comprobante de crédito fiscal."]
    missing: list[str] = []
    if draft.document_type not in (IdentityDocument.NIT, IdentityDocument.DUI) or not (
        draft.document_number
    ):
        missing.append("NIT o DUI homologado.")
    if not draft.nrc:
        missing.append("NRC.")
    if not draft.activity_code:
        missing.append("Actividad económica.")
    if draft.geography is None or not draft.address_line or not address.coded:
        missing.append("Dirección completa: departamento, municipio, distrito y dirección.")
    return missing


def receivable_documents(draft: CustomerDraft, address: CustomerAddress) -> list[str]:
    """Documentos (CAT-002) que se le pueden emitir al cliente con sus datos actuales."""
    if draft.customer_type == CustomerType.FOREIGN:
        return [EXPORT_INVOICE]
    documents = [INVOICE]
    if not tax_credit_missing(draft, address):
        documents.append(TAX_CREDIT)
    return documents


def require_editable(customer: Customer) -> None:
    if customer.anonymized_at is not None:
        raise _rule(
            "El cliente fue anonimizado por una solicitud de cancelación u olvido; sus datos "
            "ya no se editan ni se reactiva.",
            "customer_anonymized_locked",
        )
    if customer.is_generic:
        raise _rule(
            "El cliente «Consumidor final» de la sucursal no se edita ni se desactiva.",
            "customer_generic_locked",
        )


@dataclass(frozen=True, slots=True)
class DeliveryAddressDraft:
    label: str
    address_line: str
    geography: Geography | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    contact_name: str | None = None
    phone: str | None = None
    is_default: bool = False
    is_active: bool = True


def validate_delivery_address(draft: DeliveryAddressDraft) -> DeliveryAddressDraft:
    label = _clean(draft.label)
    line = _clean(draft.address_line)
    if label is None or len(label) < 2:  # noqa: PLR2004
        raise _rule(
            "Ponle un nombre a la dirección de entrega.", "customer_delivery_label_required"
        )
    if line is None or len(line) < 3:  # noqa: PLR2004
        raise _rule("Escribe la dirección de entrega.", "customer_delivery_line_required")
    if (draft.latitude is None) != (draft.longitude is None):
        raise _rule(
            "Las coordenadas llevan latitud y longitud.", "customer_delivery_coordinates_invalid"
        )
    if (
        draft.latitude is not None
        and draft.longitude is not None
        and not (
            -90 <= draft.latitude <= 90 and -180 <= draft.longitude <= 180  # noqa: PLR2004
        )
    ):
        raise _rule(
            "Las coordenadas están fuera de rango.", "customer_delivery_coordinates_invalid"
        )
    if draft.is_default and not draft.is_active:
        raise _rule(
            "La dirección principal debe estar activa.", "customer_delivery_default_inactive"
        )
    return replace(
        draft,
        label=label,
        address_line=line,
        contact_name=_clean(draft.contact_name),
        phone=_clean(draft.phone),
    )
