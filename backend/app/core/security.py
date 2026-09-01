"""Security primitives.

Phase 0 keeps only the Argon2 hasher facade and a constant-time compare helper.
JWT issuance/verification, password policy, and token rotation arrive in Phase 1.
The Argon2 parameters are read from settings so they can be tuned per env.
"""
from __future__ import annotations

import hmac
from typing import cast

from argon2 import PasswordHasher, Type
from argon2.exceptions import Argon2Error, InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


_hasher = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    type=Type.ID,
)


def hash_password(plain: str) -> str:
    """Hash a password using Argon2id. Raises ValueError on empty input."""
    if not plain:
        raise ValueError("password must not be empty")
    return cast(str, _hasher.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time-ish verification via argon2. Never re-raises mismatch."""
    if not plain or not hashed:
        return False
    try:
        return cast(bool, _hasher.verify(hashed, plain))
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHash, Argon2Error) as exc:
        log.warning("password_verify_error", error=str(exc))
        return False


def needs_rehash(hashed: str) -> bool:
    """True if `hashed` was produced with weaker params than current."""
    return cast(bool, _hasher.check_needs_rehash(hashed))


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def mask_token(token: str | None, keep: int = 4) -> str:
    if not token:
        return "<none>"
    if len(token) <= keep:
        return "***"
    return token[:keep] + "..." + token[-2:]


__all__ = [
    "constant_time_eq",
    "hash_password",
    "mask_token",
    "needs_rehash",
    "verify_password",
]
