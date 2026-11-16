"""Reglas puras de clientes con identidad fiscal."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.customer import (
    CustomerAddress,
    CustomerDraft,
    CustomerType,
    DeliveryAddressDraft,
    Geography,
    IdentityDocument,
    normalize_document,
    receivable_documents,
    tax_credit_missing,
    validate_delivery_address,
    validate_draft,
)
from app.domain.entities.fiscal import PersonType, TaxpayerCategory

GEOGRAPHY = Geography(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
CODED = CustomerAddress("San Miguel", "12", "San Miguel Centro", "22", "San Miguel", "17")


def taxpayer(**changes: object) -> CustomerDraft:
    values: dict[str, object] = {
        "customer_type": CustomerType.TAXPAYER,
        "name": "Cafetería El Trigal, S.A. de C.V.",
        "person_type": PersonType.LEGAL,
        "taxpayer_category": TaxpayerCategory.OTHER,
        "document_type": IdentityDocument.NIT,
        "document_number": "0614-010101-101-1",
        "nrc": "123456-7",
        "activity_code": "56101",
        "geography": GEOGRAPHY,
        "address_line": "Avenida Roosevelt 12",
    }
    values.update(changes)
    return CustomerDraft(**values)  # type: ignore[arg-type]


def test_documents_are_normalized_to_digits() -> None:
    assert normalize_document(IdentityDocument.NIT, "0614-010101-101-1") == "06140101011011"
    assert normalize_document(IdentityDocument.DUI, "01234567-8") == "012345678"
    assert normalize_document(IdentityDocument.PASSPORT, " ab 12345 ") == "AB12345"
    for kind, bad in (
        (IdentityDocument.NIT, "0614-1"),
        (IdentityDocument.DUI, "1234"),
        (IdentityDocument.OTHER, "x"),
    ):
        with pytest.raises(BusinessRuleError):
            normalize_document(kind, bad)


def test_complete_taxpayer_receives_invoice_and_tax_credit() -> None:
    draft = validate_draft(taxpayer())
    assert draft.document_number == "06140101011011"
    assert draft.nrc == "1234567"
    assert tax_credit_missing(draft, CODED) == []
    assert receivable_documents(draft, CODED) == ["01", "03"]


def test_incomplete_taxpayer_explains_what_is_missing() -> None:
    draft = validate_draft(
        taxpayer(nrc=None, activity_code=None, geography=None, address_line=None)
    )
    missing = tax_credit_missing(draft, CustomerAddress())
    assert missing == [
        "NRC.",
        "Actividad económica.",
        "Dirección completa: departamento, municipio, distrito y dirección.",
    ]
    assert receivable_documents(draft, CustomerAddress()) == ["01"]


def test_address_without_hacienda_codes_blocks_tax_credit() -> None:
    draft = validate_draft(taxpayer())
    assert tax_credit_missing(draft, CustomerAddress("X", None, "Y", None, "Z", None))


def test_final_consumer_and_foreign_documents() -> None:
    consumer = validate_draft(CustomerDraft(CustomerType.FINAL_CONSUMER, "Ana López"))
    assert receivable_documents(consumer, CustomerAddress()) == ["01"]
    assert tax_credit_missing(consumer, CustomerAddress())[0].startswith("Solo un contribuyente")
    foreign = validate_draft(
        CustomerDraft(CustomerType.FOREIGN, "Panadería Centroamericana", country_code="gt")
    )
    assert foreign.country_code == "GT"
    assert receivable_documents(foreign, CustomerAddress()) == ["11"]


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"taxpayer_category": None}, "customer_taxpayer_category_required"),
        ({"document_type": IdentityDocument.PASSPORT}, "customer_taxpayer_document_invalid"),
        ({"document_number": None}, "customer_document_incomplete"),
        ({"nrc": "12-AB"}, "customer_nrc_invalid"),
        ({"activity_code": "123"}, "customer_activity_invalid"),
        ({"country_code": "GT"}, "customer_country_not_foreign"),
        ({"credit_days": 400}, "customer_credit_days_invalid"),
        ({"credit_limit": Decimal("-1")}, "customer_credit_limit_invalid"),
        ({"name": " "}, "customer_name_required"),
    ],
)
def test_invalid_taxpayer_values(changes: dict[str, object], code: str) -> None:
    with pytest.raises(BusinessRuleError) as exc:
        validate_draft(taxpayer(**changes))
    assert exc.value.code == code


def test_foreign_customer_rules() -> None:
    with pytest.raises(BusinessRuleError) as no_country:
        validate_draft(CustomerDraft(CustomerType.FOREIGN, "Cliente"))
    assert no_country.value.code == "customer_country_required"
    with pytest.raises(BusinessRuleError) as with_geography:
        validate_draft(
            CustomerDraft(CustomerType.FOREIGN, "Cliente", country_code="GT", geography=GEOGRAPHY)
        )
    assert with_geography.value.code == "customer_foreign_geography"


def test_category_is_dropped_for_non_taxpayers() -> None:
    draft = validate_draft(
        CustomerDraft(CustomerType.FINAL_CONSUMER, "Ana", taxpayer_category=TaxpayerCategory.LARGE)
    )
    assert draft.taxpayer_category is None


def test_delivery_address_rules() -> None:
    ok = validate_delivery_address(
        DeliveryAddressDraft(
            " Bodega ", "Km 5 carretera", latitude=Decimal("13.48"), longitude=Decimal("-88.17")
        )
    )
    assert ok.label == "Bodega"
    for draft, code in (
        (DeliveryAddressDraft("B", "Calle 1"), "customer_delivery_label_required"),
        (
            DeliveryAddressDraft("Bodega", "Calle 1", latitude=Decimal("13")),
            "customer_delivery_coordinates_invalid",
        ),
        (
            DeliveryAddressDraft("Bodega", "Calle 1", is_default=True, is_active=False),
            "customer_delivery_default_inactive",
        ),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            validate_delivery_address(draft)
        assert exc.value.code == code
