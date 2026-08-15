"""Authenticated encryption for supplier bank details.

The key is supplied by the deployment secret manager as URL-safe/base64 text
(``SUPPLIER_DATA_ENCRYPTION_KEY``).  Plaintext is intentionally never logged
or returned by an API serializer.
"""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

NONCE_BYTES = 12
LAST_FOUR_CHARS = 4


class EncryptionConfigurationError(RuntimeError):
    """The application cannot safely encrypt protected data."""


def _key() -> bytes:
    raw = settings.SUPPLIER_DATA_ENCRYPTION_KEY or os.getenv("SUPPLIER_DATA_ENCRYPTION_KEY")
    if not raw:
        raise EncryptionConfigurationError("SUPPLIER_DATA_ENCRYPTION_KEY no está configurada")
    try:
        key = base64.urlsafe_b64decode(raw.encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise EncryptionConfigurationError("La clave de datos de proveedores no es base64 válida") from exc
    if len(key) not in (16, 24, 32):
        raise EncryptionConfigurationError("La clave de datos de proveedores debe tener 16, 24 o 32 bytes")
    return key


def encrypt_secret(value: str) -> bytes:
    if not value:
        raise ValueError("El dato bancario no puede estar vacío")
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)


def decrypt_secret(value: bytes) -> str:
    if len(value) <= NONCE_BYTES:
        raise ValueError("Ciphertext bancario inválido")
    nonce, ciphertext = value[:NONCE_BYTES], value[NONCE_BYTES:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, None).decode("utf-8")


def last_four(value: str) -> str:
    compact = "".join(value.split())
    if len(compact) < LAST_FOUR_CHARS:
        raise ValueError("La cuenta debe contener al menos cuatro caracteres")
    return compact[-LAST_FOUR_CHARS:]
