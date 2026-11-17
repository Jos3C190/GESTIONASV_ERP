"""Certificado de prueba con el formato del ``{nit}.crt`` de Hacienda (bloque V3d).

Es un XML como el que lee el firmador oficial: ``privateKey/clave`` lleva el SHA-512 en
hexadecimal de la contraseña privada. Las llaves son de relleno; el firmador real se prueba en el
servicio DTE con llaves RSA verdaderas.
"""

from __future__ import annotations

import base64
import hashlib


def hacienda_certificate(nit: str, private_key_password: str) -> bytes:
    clave = hashlib.sha512(private_key_password.encode("utf-8")).hexdigest()
    llave = base64.b64encode(b"llave-de-prueba").decode("ascii")
    return (
        "<CertificadoMH>"
        f"<_id>{nit}</_id><nit>{nit}</nit>"
        "<publicKey><keyType>PUBLIC</keyType><algorithm>RSA</algorithm>"
        f"<encodied>{llave}</encodied><format>X.509</format><clave>{clave}</clave></publicKey>"
        "<privateKey><keyType>PRIVATE</keyType><algorithm>RSA</algorithm>"
        f"<encodied>{llave}</encodied><format>PKCS#8</format><clave>{clave}</clave></privateKey>"
        "<activo>true</activo></CertificadoMH>"
    ).encode()
