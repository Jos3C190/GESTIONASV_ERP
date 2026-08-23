"""Shared product and variant identifier rules."""

import pytest
from app.domain.product_identifiers import validate_identifier_value


def test_gtin_formats_share_the_same_check_digit_rule() -> None:
    assert validate_identifier_value("ean", "4006381333931") == "4006381333931"
    assert validate_identifier_value("gtin", "00012345600012") == "00012345600012"


def test_invalid_gtin_and_isbn_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="dígito"):
        validate_identifier_value("upc", "036000291453")
    with pytest.raises(ValueError, match="ISBN"):
        validate_identifier_value("isbn", "0306406154")


def test_text_identifiers_are_normalized_without_barcode_rules() -> None:
    assert validate_identifier_value("internal", "  LORENA-001 ") == "LORENA001"
    assert validate_identifier_value("other", "Ref. A/10") == "REFA10"
