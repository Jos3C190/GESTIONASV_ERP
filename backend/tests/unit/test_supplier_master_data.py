"""Pure tests for international supplier master invariants."""

from __future__ import annotations

import base64

import pytest
from app.api.v1.schemas.supplier import SupplierCreate, SupplierTaxIdentifierCreate
from app.core.config import settings
from app.core.secret_encryption import decrypt_secret, encrypt_secret, last_four
from app.infrastructure.repositories.supplier_master_repository import SupplierMasterRepository

pytestmark = pytest.mark.unit


def test_tax_identifier_is_generic_and_optional() -> None:
    payload = SupplierTaxIdentifierCreate(
        country_id=222,
        identifier_type=" EIN ",
        value=" 12-3456789 ",
    )
    assert payload.identifier_type == "EIN"
    assert payload.value == "12-3456789"
    supplier = SupplierCreate(code="INT-001", name="International Supplier", country=222)
    assert supplier.supplier_status == "approved"


def test_tax_identifier_normalization_is_country_agnostic() -> None:
    assert SupplierMasterRepository.normalize_tax_value(" VAT  DE-123 ") == "vatde-123"
    assert (
        SupplierMasterRepository.normalize_tax_value("NIT-0614-123456-101-0")
        == "nit-0614-123456-101-0"
    )


def test_bank_encryption_round_trip_and_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    monkeypatch.setattr(settings, "SUPPLIER_DATA_ENCRYPTION_KEY", key)
    plaintext = "001234567890"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext.encode()
    assert decrypt_secret(ciphertext) == plaintext
    assert last_four(plaintext) == "7890"


def test_bank_encryption_decrypts_cryptography_45_ciphertext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing AES-GCM rows remain readable after the cryptography upgrade."""
    key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    monkeypatch.setattr(settings, "SUPPLIER_DATA_ENCRYPTION_KEY", key)
    ciphertext = base64.b64decode("AAECAwQFBgcICQoLGuupcf+WRmTkJtiLkabhAKKujHfZlOlVB+I4Rg==")

    assert decrypt_secret(ciphertext) == "001234567890"


def test_bank_encryption_fails_closed_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SUPPLIER_DATA_ENCRYPTION_KEY", None)
    with pytest.raises(RuntimeError):
        encrypt_secret("123456")
