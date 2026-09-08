"""Security helpers tests (Argon2 hashing + masking)."""

from __future__ import annotations

import pytest
from app.core.security import (
    constant_time_eq,
    hash_password,
    mask_token,
    needs_rehash,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("another-very-strong-password")
    assert verify_password("wrong-password", h) is False


def test_hash_rejects_empty() -> None:
    with pytest.raises(ValueError, match="password must not be empty"):
        hash_password("")


def test_verify_rejects_empty_inputs() -> None:
    assert verify_password("", "somehash") is False
    assert verify_password("abc", "") is False


def test_needs_rehash_false_for_fresh_hash() -> None:
    h = hash_password("some-strong-password-123")
    assert needs_rehash(h) is False


def test_constant_time_eq_matches_and_mismatches() -> None:
    assert constant_time_eq("abc", "abc") is True
    assert constant_time_eq("abc", "abd") is False
    assert constant_time_eq("", "") is True


def test_mask_token_behaviour() -> None:
    assert mask_token(None) == "<none>"
    assert mask_token("abc") == "***"
    assert mask_token("abcdefgh", keep=4).startswith("abcd")
    assert mask_token("abcdefgh", keep=4).endswith("gh")
