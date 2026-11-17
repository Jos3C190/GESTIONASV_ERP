"""Credenciales de Hacienda de la empresa (bloque V3d).

La empresa trae tres cosas del Ministerio de Hacienda:

- la contraseña de la API (para autenticarse en el ambiente de pruebas o de producción);
- su certificado ``{nit}.crt``, el XML que genera Hacienda con la llave pública y la privada;
- la contraseña de la llave privada, cuyo SHA-512 en hexadecimal va en ``privateKey/clave``
  del certificado (así lo comprueba el firmador oficial).

Aquí se valida que el certificado sea de la empresa y que la contraseña privada le corresponda,
para avisar antes de llegar al firmador.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import BusinessRuleError

MAX_CERTIFICATE_BYTES = 256 * 1024
_NIT = re.compile(r"^([0-9]{9}|[0-9]{14})$")
_BLOCKS = re.compile(r"<(publicKey|privateKey|certificado)>.*?</\1>", re.DOTALL)
_MAX_PASSWORD = 500


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True, slots=True)
class CertificateInfo:
    nit: str
    sha256: str
    private_key_hash: str


@dataclass(frozen=True, slots=True)
class HaciendaCredentials:
    """Lo que se puede mostrar: nunca las contraseñas ni el certificado."""

    certificate_nit: str
    certificate_sha256: str
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_error: str | None = None
    updated_at: datetime | None = None


def _tag(xml: str, name: str) -> str | None:
    match = re.search(rf"<{name}>([^<]*)</{name}>", xml)
    return match.group(1).strip() if match else None


def inspect_certificate(data: bytes) -> CertificateInfo:
    if not data:
        raise _rule("Sube el certificado (.crt) de la empresa.", "hacienda_certificate_required")
    if len(data) > MAX_CERTIFICATE_BYTES:
        raise _rule("El certificado pesa más de 256 KB.", "hacienda_certificate_invalid")
    try:
        xml = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _rule(
            "El archivo no es un certificado de Hacienda (.crt).", "hacienda_certificate_invalid"
        ) from exc
    private = re.search(r"<privateKey>(.*?)</privateKey>", xml, re.DOTALL)
    nit = _tag(_BLOCKS.sub("", xml), "nit")
    private_hash = _tag(private.group(1), "clave") if private else None
    if not private or "<publicKey>" not in xml or not nit or not private_hash:
        raise _rule(
            "El archivo no es un certificado de Hacienda (.crt).", "hacienda_certificate_invalid"
        )
    clean_nit = re.sub(r"[\s-]", "", nit)
    if not _NIT.match(clean_nit):
        raise _rule("El NIT del certificado no es válido.", "hacienda_certificate_invalid")
    return CertificateInfo(
        nit=clean_nit,
        sha256=hashlib.sha256(data).hexdigest(),
        private_key_hash=private_hash.lower(),
    )


def require_certificate_matches(
    info: CertificateInfo, company_nit: str | None, private_key_password: str
) -> None:
    """El certificado debe ser del NIT de la empresa y abrir con su contraseña privada."""

    if not company_nit:
        raise _rule(
            "Registra el NIT de la empresa en su ficha antes de cargar el certificado.",
            "hacienda_company_nit_missing",
        )
    if info.nit != company_nit:
        raise _rule(
            f"El certificado es del NIT {info.nit}, no del de la empresa ({company_nit}).",
            "hacienda_certificate_nit_mismatch",
        )
    digest = hashlib.sha512(private_key_password.encode("utf-8")).hexdigest()
    if digest != info.private_key_hash:
        raise _rule(
            "La contraseña de la llave privada no corresponde al certificado.",
            "hacienda_private_key_password_invalid",
        )


def require_passwords(api_password: str | None, private_key_password: str | None) -> None:
    for value, label, code in (
        (api_password, "la contraseña de la API de Hacienda", "hacienda_api_password_required"),
        (
            private_key_password,
            "la contraseña de la llave privada",
            "hacienda_private_key_password_required",
        ),
    ):
        if not value:
            raise _rule(f"Escribe {label}.", code)
        if len(value) > _MAX_PASSWORD:
            raise _rule(f"{label.capitalize()} es demasiado larga.", code)
