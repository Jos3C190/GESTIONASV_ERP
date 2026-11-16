"""Clientes de demostración de Grupo Lorena."""

from __future__ import annotations

import uuid

from app.domain.entities.customer import (
    CustomerAddress,
    CustomerType,
    Geography,
    receivable_documents,
    tax_credit_missing,
    validate_draft,
)
from app.infrastructure.catalogs.hacienda_dte import CATALOGS
from seed.seed_grupo_lorena_customers import CUSTOMERS

CODED = CustomerAddress("San Miguel", "12", "San Miguel Centro", "22", "San Miguel", "17")
GEOGRAPHY = Geography(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


def _codes(catalog: str) -> set[str]:
    return {code for _, code, _ in CATALOGS[catalog][1]}


def test_one_customer_per_case_with_unique_codes() -> None:
    assert [c.code for c in CUSTOMERS] == ["CLI-00001", "CLI-00002", "CLI-00003", "CLI-00004"]
    assert {c.draft.customer_type for c in CUSTOMERS} == set(CustomerType)


def test_seed_data_passes_the_domain_rules() -> None:
    documents: list[list[str]] = []
    for item in CUSTOMERS:
        draft = validate_draft(item.draft)
        if item.with_san_miguel_address:
            draft = validate_draft(draft.__class__(**{**_fields(draft), "geography": GEOGRAPHY}))
        if draft.activity_code:
            assert draft.activity_code in _codes("CAT-019")
        if draft.country_code:
            assert draft.country_code in _codes("CAT-020")
        documents.append(receivable_documents(draft, CODED))
    assert documents == [["01", "03"], ["01"], ["01"], ["11"]]


def test_incomplete_taxpayer_only_lacks_the_nrc() -> None:
    draft = validate_draft(CUSTOMERS[1].draft)
    draft = draft.__class__(**{**_fields(draft), "geography": GEOGRAPHY})
    assert tax_credit_missing(draft, CODED) == ["NRC."]


def test_identity_numbers_are_fictitious() -> None:
    for item in CUSTOMERS:
        number = item.draft.document_number or ""
        assert "0000" in number


def _fields(draft: object) -> dict[str, object]:
    return {name: getattr(draft, name) for name in draft.__dataclass_fields__}  # type: ignore[attr-defined]
