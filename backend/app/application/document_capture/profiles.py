"""What a guided capture asks the vision model for each kind of document.

A new document kind only needs a profile here plus its own validation rules.
Only the fields listed are requested, so sensitive data printed on a card (the
license back carries blood type, allergies and medication) never leaves the image.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

FIELD_INSTRUCTIONS = (
    "Extrae de esta {document} estos campos y devuelve JSON. Copia exactamente lo impreso, "
    "sin corregir nada. Usa null si un campo no se puede leer. Campos: "
)


@dataclass(frozen=True, slots=True)
class CaptureSide:
    #: Output key -> where to find it. Order matters: the model fills keys in sequence,
    #: and asking for the DUI before the name lines stopped it from mixing them up.
    fields: Mapping[str, str]
    document: str = "licencia"

    def prompt(self) -> str:
        listed = "; ".join(f"{key}: {hint}" for key, hint in self.fields.items())
        return f"{FIELD_INSTRUCTIONS.format(document=self.document)}{listed}"

    def response_format(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "campos",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {key: {"type": ["string", "null"]} for key in self.fields},
                    "required": list(self.fields),
                    "additionalProperties": False,
                },
            },
        }


@dataclass(frozen=True, slots=True)
class CaptureProfile:
    kind: str
    sides: Mapping[str, CaptureSide]


DRIVER_LICENSE = CaptureProfile(
    kind="driver_license",
    sides={
        "front": CaptureSide(
            {
                "clase": "texto junto a Clase/Class",
                "vence": "texto junto a Vence/Expires, formato MM-AAAA",
                "numero": "número junto a No",
                "dui": "número bajo DUI/ID",
                "nombre_linea_1": "primera línea de texto en mayúsculas bajo Nombre/Name",
                "nombre_linea_2": (
                    "segunda línea de texto en mayúsculas bajo Nombre/Name, "
                    "justo debajo de la primera"
                ),
            }
        ),
        "back": CaptureSide(
            {
                "expedicion": "fecha bajo Expedición/Issue",
                "nacimiento": "fecha bajo Nacimiento/Birth",
                "numero_control": "código bajo No CONTROL",
            }
        ),
    },
)

_CIRCULATION_DOCUMENT = "tarjeta de circulación"

#: The owner's name, DUI and address are printed on the front and are never requested.
#: The key is ``vto`` because the model took ``vence`` for the DUI printed beside it.
CIRCULATION_CARD = CaptureProfile(
    kind="circulation_card",
    sides={
        "front": CaptureSide(
            {
                "placa": "código grande en negrita debajo del nombre",
                "vto": "texto junto a VTO, formato MM-AAAA",
                "emision": "fecha junto a EMISIÓN, formato MM-DD-AAAA",
            },
            document=_CIRCULATION_DOCUMENT,
        ),
        "back": CaptureSide(
            {
                "anio": "número bajo AÑO",
                "marca": "texto bajo MARCA",
                "modelo": "texto bajo MODELO",
                "color": "texto bajo COLOR",
                "chasis": "código bajo Nº CHASIS",
                "motor": "código bajo Nº MOTOR",
                "vin": "código bajo Nº VIN",
            },
            document=_CIRCULATION_DOCUMENT,
        ),
    },
)

PROFILES: Mapping[str, CaptureProfile] = {
    DRIVER_LICENSE.kind: DRIVER_LICENSE,
    CIRCULATION_CARD.kind: CIRCULATION_CARD,
}
