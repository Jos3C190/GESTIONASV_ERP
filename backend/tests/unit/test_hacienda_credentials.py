"""V3d: validación del certificado y las contraseñas de Hacienda."""

from __future__ import annotations

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.hacienda_credentials import (
    inspect_certificate,
    require_certificate_matches,
    require_passwords,
)

from tests.hacienda_certificate import hacienda_certificate

NIT = "06142803901121"


def _code(fn) -> str:  # type: ignore[no-untyped-def]
    with pytest.raises(BusinessRuleError) as raised:
        fn()
    return raised.value.code


def test_reads_the_nit_and_checks_the_private_key_password() -> None:
    info = inspect_certificate(hacienda_certificate(NIT, "privada"))
    assert info.nit == NIT
    assert len(info.sha256) == 64
    require_certificate_matches(info, NIT, "privada")
    assert (
        _code(lambda: require_certificate_matches(info, NIT, "otra"))
        == "hacienda_private_key_password_invalid"
    )
    assert (
        _code(lambda: require_certificate_matches(info, "06140101900011", "privada"))
        == "hacienda_certificate_nit_mismatch"
    )
    assert (
        _code(lambda: require_certificate_matches(info, None, "privada"))
        == "hacienda_company_nit_missing"
    )


@pytest.mark.parametrize(
    "data",
    [b"", b"<html></html>", b"<nit>1</nit>", b"\xff\xfe", b"x" * (256 * 1024 + 1)],
)
def test_rejects_files_that_are_not_certificates(data: bytes) -> None:
    assert _code(lambda: inspect_certificate(data)) in {
        "hacienda_certificate_invalid",
        "hacienda_certificate_required",
    }


def test_passwords_are_required() -> None:
    require_passwords("api", "privada")
    assert _code(lambda: require_passwords("", "privada")) == "hacienda_api_password_required"
    assert _code(lambda: require_passwords("api", None)) == "hacienda_private_key_password_required"
