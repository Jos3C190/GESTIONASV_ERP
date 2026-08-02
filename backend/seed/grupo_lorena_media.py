"""Versioned Cloudinary manifest for the Grupo Lorena development seed.

Only public delivery URLs and technical metadata are stored here. Cloudinary
credentials and image binaries remain outside the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

CLOUDINARY_CLOUD_NAME = "ddxoikq8k"
COMPANY_ID = UUID("0a7303f6-64a5-428c-a829-c2b09966fefd")
MEDIA_ROOT = f"erp-mini/development/companies/{COMPANY_ID}"


@dataclass(frozen=True, slots=True)
class MediaSeed:
    purpose: str
    token: str
    version: int
    format: str
    bytes: int
    width: int
    height: int
    caption: str = ""

    @property
    def public_id(self) -> str:
        return f"{MEDIA_ROOT}/{self.purpose}/{self.token}"

    @property
    def secure_url(self) -> str:
        return (
            f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/"
            f"v{self.version}/{self.public_id}.{self.format}"
        )

    def gallery_item(self) -> dict[str, str]:
        return {
            "url": self.secure_url,
            "caption": self.caption,
            "public_id": self.public_id,
        }


def _branch_image(
    token: str,
    version: int,
    bytes_: int,
    width: int,
    height: int,
) -> MediaSeed:
    return MediaSeed("branch_image", token, version, "png", bytes_, width, height)


COMPANY_LOGO = MediaSeed(
    "company_logo",
    "7e9c3c7214794a9a9cc5639edcd29a86",
    1785648409,
    "jpg",
    14_462,
    447,
    447,
)

BRANCH_MEDIA: dict[str, tuple[MediaSeed, ...]] = {
    "LOR-SM-01": (
        _branch_image("7a558dab163b41f784567f95491f0ab8", 1785650025, 901_594, 1267, 758),
        _branch_image("38171c39327a47f387bdbf0826fd91a6", 1785650031, 1_304_576, 1263, 787),
        _branch_image("309feae0e19b4685953ee9724ee93e62", 1785650036, 924_507, 1268, 778),
        _branch_image("48cf55e93c7840d08dffd8e893e797ea", 1785650041, 1_409_667, 1117, 881),
        _branch_image("4c028d9ea0b14fc0a33805cfb8cfcbd2", 1785650047, 1_430_764, 1290, 800),
        _branch_image("07f4849508f544519644b8113d971162", 1785650051, 1_085_121, 709, 873),
        _branch_image("3c987b7f014945338b5cecde48814835", 1785650056, 919_818, 712, 880),
        _branch_image("00db20b0255a4e978b871b675433d321", 1785650064, 1_245_221, 1126, 862),
    ),
    "LOR-USU-01": (
        _branch_image("067a9a1ad1724c5f87a33de67010d64d", 1785651731, 300_229, 534, 509),
    ),
    "LOR-JIQ-01": (
        _branch_image("a0b5a840ad9b4a008feca4b7451964bd", 1785649034, 1_115_066, 1171, 826),
        _branch_image("51ef388caa2744c9af39eee891d5b4a7", 1785649041, 703_214, 717, 884),
        _branch_image("e299a609c0104a979cc1c101c23d92f1", 1785649051, 505_662, 709, 879),
        _branch_image("3bedcc108a3f40ebad7d173c0b495223", 1785649058, 829_677, 533, 876),
        _branch_image("df4c25fee04d417bbbe96a941c55dfcc", 1785649063, 1_339_061, 1168, 873),
        _branch_image("797f95d7263d4202aa98c52da596122d", 1785649068, 1_018_990, 709, 884),
    ),
    "LOR-LU-01": (
        _branch_image("893e8fd6a5bf43b2a2240c631a7cb489", 1785649591, 1_238_402, 1165, 651),
        _branch_image("21d9aeb5bd5749a3b4ab1cc0cae35b03", 1785649596, 718_692, 712, 888),
        _branch_image("2d876894225d45878e78d60ab3c9fff2", 1785649601, 1_163_131, 1169, 785),
        _branch_image("969b992145c24ef28e75b0186dc49a93", 1785649605, 1_283_661, 1314, 792),
        _branch_image("37acecd7295843cda6f278d8fb786e03", 1785649611, 1_537_081, 1311, 835),
        _branch_image("049ec167ee3247dc83d33a1d6630360a", 1785649615, 1_076_860, 1162, 649),
        _branch_image("1294b198e39d4146b63f07ed9a50b905", 1785649620, 835_744, 531, 880),
        _branch_image("74b704a1b26344d582ab9a8a45b546d2", 1785649624, 555_609, 534, 883),
    ),
    "LOR-SRL-01": (
        _branch_image("0475b30a3eb24cee8669c743185735b0", 1785651395, 1_016_439, 1173, 879),
        _branch_image("95c72aa531a44d00821b06e4b7659ee4", 1785651399, 750_618, 713, 881),
        _branch_image("8879ee2cbf2342249896b3e1cea4912a", 1785651404, 904_072, 713, 884),
        _branch_image("66c668a0a14a4935bda216c448864fed", 1785651408, 580_114, 533, 861),
        _branch_image("2599e6e494a1403184f4f125a20389cc", 1785651414, 1_052_127, 1063, 693),
        _branch_image("200f1d4a784a4d6ba9879e18999e7ad5", 1785651418, 966_476, 712, 880),
        _branch_image("343d255a6ea34bc78845d185d53f1dea", 1785651423, 698_680, 710, 865),
        _branch_image("8d2b63d974114890b9dd16d5c5605bb5", 1785651428, 768_844, 712, 876),
    ),
    "LOR-GOT-01": (
        _branch_image("f3b94b9267604c8ba2f802966d6590b1", 1785650801, 851_535, 1089, 620),
        _branch_image("26a2db9d83e04032813b862db909d1bb", 1785650807, 1_268_101, 1182, 870),
        _branch_image("65e9cc01df554a1ab5004a8ef4dbc82a", 1785650812, 1_335_600, 1186, 879),
    ),
    "LOR-ET-01": (
        _branch_image("3618b2093f694587ac4ac02cf62090be", 1785648590, 924_170, 971, 630),
    ),
}


def all_media() -> tuple[MediaSeed, ...]:
    return (COMPANY_LOGO, *(asset for assets in BRANCH_MEDIA.values() for asset in assets))


def validate_media_manifest(branch_codes: set[str]) -> None:
    """Fail fast when the public fixture manifest becomes inconsistent."""
    if set(BRANCH_MEDIA) != branch_codes:
        raise ValueError("El manifiesto multimedia debe cubrir exactamente todas las sucursales.")
    assets = all_media()
    public_ids = [asset.public_id for asset in assets]
    if len(public_ids) != len(set(public_ids)):
        raise ValueError("Los public_id multimedia de la semilla deben ser únicos.")
    if any(asset.bytes <= 0 or asset.width <= 0 or asset.height <= 0 for asset in assets):
        raise ValueError("Los metadatos multimedia deben tener dimensiones y tamaño positivos.")
    if any(
        not asset.secure_url.startswith(
            f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/"
        )
        for asset in assets
    ):
        raise ValueError("Todas las imágenes de la semilla deben usar entrega HTTPS de Cloudinary.")
