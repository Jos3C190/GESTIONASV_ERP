"""Reglas puras del emisor de DTE."""

from __future__ import annotations

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import (
    DOCUMENT_TYPES,
    CertificationStatus,
    EstablishmentType,
    IssuerFacts,
    OperatingMode,
    dte_nit,
    dte_nrc,
    establishment_code,
    production_blockers,
    require_can_enable,
    require_document_type,
    require_mode_change,
    validate_activity_code,
    validate_establishment_code,
    validate_point_of_sale_code,
)

READY = IssuerFacts(
    has_nit=True,
    has_nrc=True,
    has_primary_activity=True,
    establishments_with_point_of_sale=1,
    enabled_documents=2,
)


@pytest.mark.parametrize(
    ("kind", "number", "expected"),
    [
        (EstablishmentType.HEADQUARTERS, 1, "M001"),
        (EstablishmentType.BRANCH, 25, "S025"),
        (EstablishmentType.WAREHOUSE, 999, "B999"),
        (EstablishmentType.YARD, 7, "P007"),
    ],
)
def test_establishment_code_uses_the_type_letter(
    kind: EstablishmentType, number: int, expected: str
) -> None:
    assert establishment_code(kind, number) == expected


@pytest.mark.parametrize("number", [0, 1000])
def test_establishment_number_has_three_digits(number: int) -> None:
    with pytest.raises(BusinessRuleError) as exc:
        establishment_code(EstablishmentType.BRANCH, number)
    assert exc.value.code == "fiscal_establishment_number_invalid"


def test_establishment_code_is_normalized_and_validated() -> None:
    assert validate_establishment_code(EstablishmentType.BRANCH, " s002 ") == "S002"
    for bad in ("S02", "X001", "S0001", "S000", ""):
        with pytest.raises(BusinessRuleError) as exc:
            validate_establishment_code(EstablishmentType.BRANCH, bad)
        assert exc.value.code == "fiscal_establishment_code_invalid"


def test_establishment_code_letter_must_match_type() -> None:
    with pytest.raises(BusinessRuleError) as exc:
        validate_establishment_code(EstablishmentType.HEADQUARTERS, "S001")
    assert exc.value.code == "fiscal_establishment_code_type_mismatch"
    assert "M001" in exc.value.message


def test_point_of_sale_code() -> None:
    assert validate_point_of_sale_code("p025") == "P025"
    for bad in ("P25", "A001", "P000", "P0001"):
        with pytest.raises(BusinessRuleError) as exc:
            validate_point_of_sale_code(bad)
        assert exc.value.code == "fiscal_point_of_sale_code_invalid"


def test_activity_code_has_five_or_six_digits() -> None:
    assert validate_activity_code(" 10711 ") == "10711"
    for bad in ("1071", "1071A", "1234567"):
        with pytest.raises(BusinessRuleError):
            validate_activity_code(bad)


def test_nit_and_nrc_follow_the_dte_format() -> None:
    assert dte_nit("1217-060102-101-1") == "12170601021011"
    assert dte_nit("0614-12345") is None  # 10 dígitos
    assert dte_nit("123456789") == "123456789"
    assert dte_nrc("123456-7") == "1234567"
    assert dte_nrc("Pendiente de verificación") is None
    assert dte_nrc("1") is None


def test_document_types_follow_cat_002() -> None:
    assert sorted(DOCUMENT_TYPES) == [
        "01", "03", "04", "05", "06", "07", "08", "09", "11", "14", "15", "17", "18",
    ]  # fmt: skip
    assert require_document_type("03") == "03"
    with pytest.raises(BusinessRuleError) as exc:
        require_document_type("02")
    assert exc.value.code == "fiscal_document_type_invalid"


@pytest.mark.parametrize("mode", [OperatingMode.SIMULATED, OperatingMode.TEST])
def test_any_document_can_be_enabled_outside_production(mode: OperatingMode) -> None:
    require_can_enable(mode, "01", CertificationStatus.PENDING)


def test_production_requires_approved_certification() -> None:
    require_can_enable(OperatingMode.PRODUCTION, "01", CertificationStatus.APPROVED)
    with pytest.raises(BusinessRuleError) as exc:
        require_can_enable(OperatingMode.PRODUCTION, "03", CertificationStatus.IN_PROGRESS)
    assert exc.value.code == "fiscal_document_not_certified"
    assert "Comprobante de crédito fiscal" in exc.value.message


def test_ready_issuer_has_no_blockers() -> None:
    assert production_blockers(READY) == []
    require_mode_change(OperatingMode.PRODUCTION, READY)


def test_blockers_explain_every_missing_piece() -> None:
    facts = IssuerFacts(
        has_nit=False,
        has_nrc=False,
        has_primary_activity=False,
        establishments_with_point_of_sale=0,
        enabled_documents=0,
        enabled_uncertified_documents=("04",),
    )
    reasons = production_blockers(facts)
    assert len(reasons) == 6
    assert any("NIT" in r for r in reasons)
    assert any("Nota de remisión" in r for r in reasons)
    with pytest.raises(BusinessRuleError) as exc:
        require_mode_change(OperatingMode.PRODUCTION, facts)
    assert exc.value.code == "fiscal_production_not_ready"


def test_non_production_modes_never_block() -> None:
    empty = IssuerFacts(False, False, False, 0, 0)
    require_mode_change(OperatingMode.SIMULATED, empty)
    require_mode_change(OperatingMode.TEST, empty)
