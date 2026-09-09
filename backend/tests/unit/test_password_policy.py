"""Unit tests for PasswordPolicy."""

from app.application.password_policy import PasswordPolicy


def test_valid_password() -> None:
    p = PasswordPolicy()
    r = p.validate("Strong!Passw0rd2026")
    assert r.valid
    assert r.reasons == ()


def test_too_short() -> None:
    r = PasswordPolicy().validate("Aa1!short")
    assert not r.valid
    assert any("12" in reason for reason in r.reasons)


def test_missing_uppercase() -> None:
    r = PasswordPolicy().validate("lowercase!12345")
    assert not r.valid
    assert any("mayúscula" in reason for reason in r.reasons)


def test_missing_digit() -> None:
    r = PasswordPolicy().validate("NoDigitsHere!!")
    assert not r.valid
    assert any("dígito" in reason for reason in r.reasons)


def test_missing_symbol() -> None:
    r = PasswordPolicy().validate("OnlyLetters2026")
    assert not r.valid
    assert any("símbolo" in reason for reason in r.reasons)


def test_denied_list() -> None:
    r = PasswordPolicy().validate("password123!!!")
    assert not r.valid
