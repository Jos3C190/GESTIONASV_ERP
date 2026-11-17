"""V3c: validación del SMTP propio de la empresa."""

from __future__ import annotations

from dataclasses import replace

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.company_email import EmailSettingsInput, validate_settings

VALUES = EmailSettingsInput(
    host=" SMTP.Gmail.com ",
    port=587,
    security="starttls",
    username=" facturacion@lorena.com.sv ",
    password="clave-de-aplicacion",
    from_address=" Facturacion@Lorena.com.sv ",
    from_name="  Panadería   Lorena  ",
    is_enabled=True,
)


def test_normalizes_the_settings() -> None:
    clean = validate_settings(VALUES, has_stored_password=False)
    assert clean.host == "smtp.gmail.com"
    assert clean.username == "facturacion@lorena.com.sv"
    assert clean.from_address == "facturacion@lorena.com.sv"
    assert clean.from_name == "Panadería Lorena"
    assert clean.password == "clave-de-aplicacion"


def test_password_rules() -> None:
    # Editar sin escribir la contraseña conserva la guardada.
    kept = validate_settings(replace(VALUES, password=None), has_stored_password=True)
    assert kept.password is None
    # Un servidor sin autenticación (relé interno) no lleva usuario ni contraseña.
    relay = validate_settings(
        replace(VALUES, username=None, password=None, security="none", port=25),
        has_stored_password=False,
    )
    assert relay.username is None
    with pytest.raises(BusinessRuleError) as missing:
        validate_settings(replace(VALUES, password=""), has_stored_password=False)
    assert missing.value.code == "email_settings_password_required"
    with pytest.raises(BusinessRuleError) as orphan:
        validate_settings(replace(VALUES, username=" "), has_stored_password=False)
    assert orphan.value.code == "email_settings_username_required"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"host": ""}, "email_settings_host_invalid"),
        ({"host": "smtp gmail.com"}, "email_settings_host_invalid"),
        ({"port": 0}, "email_settings_port_invalid"),
        ({"port": 65536}, "email_settings_port_invalid"),
        ({"security": "tls"}, "email_settings_security_invalid"),
        ({"from_address": "facturacion"}, "email_settings_from_invalid"),
        ({"from_name": "x" * 151}, "email_settings_from_name_too_long"),
    ],
)
def test_rejects_invalid_values(changes: dict[str, object], code: str) -> None:
    with pytest.raises(BusinessRuleError) as raised:
        validate_settings(replace(VALUES, **changes), has_stored_password=False)  # type: ignore[arg-type]
    assert raised.value.code == code
