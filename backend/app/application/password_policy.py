"""Password policy — validation against strength rules and a deny-list of
known-leaked passwords. Phase 1 uses a small embedded deny-list; phase 6+
can swap in a real HIBP integration without changing the interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Small embedded deny-list of the most common leaked passwords. This is NOT
# a substitute for HIBP, but blocks the absolute worst cases. Extend as needed.
_DENY_LIST = frozenset(
    {
        "password",
        "password123",
        "123456789",
        "qwerty123",
        "admin123",
        "letmein123",
        "welcome123",
        "changeme123",
        "superadmin",
        "erpadmin",
        "changeme",
    }
)

_MIN_LENGTH = 12
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"[0-9]")
_SYMBOL = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True, slots=True)
class PasswordPolicyResult:
    valid: bool
    reasons: tuple[str, ...]


class PasswordPolicy:
    """Validates a candidate password against the configured policy."""

    def __init__(self, *, min_length: int = _MIN_LENGTH) -> None:
        self._min_length = min_length

    def validate(self, candidate: str) -> PasswordPolicyResult:
        reasons: list[str] = []
        if len(candidate) < self._min_length:
            reasons.append(f"Debe tener al menos {self._min_length} caracteres.")
        if not _UPPER.search(candidate):
            reasons.append("Debe incluir al menos una mayúscula.")
        if not _LOWER.search(candidate):
            reasons.append("Debe incluir al menos una minúscula.")
        if not _DIGIT.search(candidate):
            reasons.append("Debe incluir al menos un dígito.")
        if not _SYMBOL.search(candidate):
            reasons.append("Debe incluir al menos un símbolo.")
        if candidate.lower() in _DENY_LIST:
            reasons.append("La contraseña está en la lista de contraseñas filtradas conocidas.")
        return PasswordPolicyResult(valid=not reasons, reasons=tuple(reasons))
