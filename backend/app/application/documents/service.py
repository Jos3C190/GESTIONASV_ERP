from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Literal

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from app.application.audit.audit_service import AuditService
from app.core.config import Settings
from app.core.exceptions import (
    ConflictError,
    InfrastructureError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_derivative import DocumentDerivative
from app.domain.ports.document_derivative_repository import DocumentDerivativeRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.malware_scanner import MalwareScanner, ScanResult
from app.domain.ports.object_storage import ObjectStorage, StoredObjectInfo

ALLOWED_DOCUMENT_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword", "application/octet-stream"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ".xls": frozenset({"application/vnd.ms-excel", "application/octet-stream"}),
    ".xlsx": frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    ".ppt": frozenset({"application/vnd.ms-powerpoint", "application/octet-stream"}),
    ".pptx": frozenset(
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"}
    ),
    ".csv": frozenset({"text/csv", "application/csv", "text/plain"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".json": frozenset({"application/json"}),
    ".xml": frozenset({"application/xml", "text/xml"}),
    ".rtf": frozenset({"application/rtf", "text/rtf"}),
    ".odt": frozenset({"application/vnd.oasis.opendocument.text"}),
    ".ods": frozenset({"application/vnd.oasis.opendocument.spreadsheet"}),
    ".odp": frozenset({"application/vnd.oasis.opendocument.presentation"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
    ".webp": frozenset({"image/webp"}),
    ".gif": frozenset({"image/gif"}),
    ".svg": frozenset({"image/svg+xml"}),
    ".tif": frozenset({"image/tiff"}),
    ".tiff": frozenset({"image/tiff"}),
}
ZIP_EXTENSIONS = frozenset({".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".tif", ".tiff"})
TEXT_EXTENSIONS = frozenset({".csv", ".txt", ".md"})
IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}
OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
OLE_STREAM_MARKERS = {
    ".doc": ("WordDocument".encode("utf-16le"),),
    ".xls": ("Workbook".encode("utf-16le"), "Book".encode("utf-16le")),
    ".ppt": ("PowerPoint Document".encode("utf-16le"),),
}
MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_RATIO = 100
MAX_FILENAME_CHARS = 255
MIN_PRINTABLE_CODEPOINT = 32
SHA256_HEX_CHARS = 64
JPEG_MIN_BYTES = 5
PNG_MIN_BYTES = 24
WEBP_MIN_BYTES = 20
GIF_MIN_BYTES = 10
SVG_MIN_BYTES = 20
RIFF_HEADER_BYTES = 8
RIFF_PAYLOAD_MIN_BYTES = 4
TIFF_MIN_BYTES = 8
TIFF_CLASSIC_MAGIC = 42
TIFF_BIG_MAGIC = 43
TIFF_BIG_HEADER_BYTES = 16
TIFF_BIG_OFFSET_SIZE = 8
TIFF_BIG_RESERVED = 0
SVG_FORBIDDEN_PATTERNS = (
    r"<\s*script\b",
    r"<\s*(?:foreignobject|iframe|object|embed)\b",
    r"<!\s*(?:doctype|entity)",
    r"\bon[a-z][\w:-]*\s*=",
    r"\b(?:java|vb)script\s*:",
    r"\b(?:href|xlink:href|src)\s*=\s*['\"]\s*(?:https?:|//|data:|javascript:)",
    r"@import\b",
    r"url\(\s*(?:https?:|//|data:|javascript:)",
)
DETECTED_CONTENT_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".rtf": "application/rtf",
    ".md": "text/markdown",
    ".json": "application/json",
    ".xml": "application/xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass(frozen=True, slots=True)
class InitiateDocumentInput:
    company_id: uuid.UUID
    actor_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class UploadTicket:
    document: DocumentAsset
    upload_url: str
    required_headers: dict[str, str]
    expires_at: datetime


def normalize_filename(value: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFC", value).replace("\\", "/")
    if "/" in normalized:
        raise ValidationError(
            "El nombre del archivo no es válido.", code="document_filename_invalid"
        )
    filename = PurePosixPath(normalized).name.strip().strip(".")
    if (
        not filename
        or len(filename) > MAX_FILENAME_CHARS
        or any(ord(char) < MIN_PRINTABLE_CODEPOINT for char in filename)
    ):
        raise ValidationError(
            "El nombre del archivo no es válido.", code="document_filename_invalid"
        )
    suffixes = Path(filename).suffixes
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            "El formato del documento no está permitido.", code="document_type_invalid"
        )
    dangerous_suffixes = {".exe", ".com", ".bat", ".cmd", ".ps1", ".js", ".vbs", ".scr"}
    if any(suffix.lower() in dangerous_suffixes for suffix in suffixes):
        raise ValidationError(
            "El nombre contiene una extensión peligrosa.", code="document_type_invalid"
        )
    return filename, extension


def validate_declaration(
    *, filename: str, content_type: str, size_bytes: int, checksum_sha256: str, max_bytes: int
) -> tuple[str, str, str]:
    safe_name, extension = normalize_filename(filename)
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type not in ALLOWED_DOCUMENT_TYPES[extension]:
        raise ValidationError(
            "El tipo MIME no corresponde con la extensión.", code="document_type_invalid"
        )
    if size_bytes < 1 or size_bytes > max_bytes:
        raise ValidationError(
            "El archivo debe pesar entre 1 byte y 50 MB.", code="document_size_invalid"
        )
    checksum = checksum_sha256.strip().lower()
    if len(checksum) != SHA256_HEX_CHARS or any(
        char not in "0123456789abcdef" for char in checksum
    ):
        raise ValidationError("El checksum SHA-256 no es válido.", code="document_checksum_invalid")
    return safe_name, extension, normalized_type


def _validate_zip_entry(entry: zipfile.ZipInfo) -> None:
    posix = PurePosixPath(entry.filename.replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts or entry.flag_bits & 0x1:
        raise ValidationError(
            "El documento comprimido no es seguro.", code="document_archive_invalid"
        )
    if entry.file_size > 0 and entry.compress_size == 0:
        raise ValidationError(
            "La relación de compresión no es segura.", code="document_archive_invalid"
        )
    if entry.compress_size and entry.file_size / entry.compress_size > MAX_ZIP_RATIO:
        raise ValidationError(
            "La relación de compresión no es segura.", code="document_archive_invalid"
        )
    lowered = entry.filename.casefold()
    if "vbaproject.bin" in lowered or lowered.endswith(".vba"):
        raise ValidationError(
            "No se permiten documentos con macros.", code="document_macros_forbidden"
        )


def _validate_zip_structure(
    extension: str,
    names: set[str],
    embedded_mimetype: bytes | None,
    content_types_payload: bytes | None = None,
    *,
    compressed: int,
    uncompressed: int,
) -> str:
    if extension in {".docx", ".xlsx", ".pptx"} and "[Content_Types].xml" not in names:
        raise ValidationError("El documento Office no es válido.", code="document_type_invalid")
    required_prefix = (
        (extension == ".docx" and "word/")
        or (extension == ".xlsx" and "xl/")
        or (extension == ".pptx" and "ppt/")
    )
    if required_prefix and not any(name.startswith(required_prefix) for name in names):
        raise ValidationError("El documento Office no es válido.", code="document_type_invalid")
    if extension == ".pptx" and (
        content_types_payload is None or b"presentationml.presentation" not in content_types_payload
    ):
        raise ValidationError("El documento PowerPoint no es válido.", code="document_type_invalid")
    if extension in {".odt", ".ods", ".odp"} and (
        "mimetype" not in names or embedded_mimetype != DETECTED_CONTENT_TYPES[extension].encode()
    ):
        raise ValidationError(
            "El documento OpenDocument no es válido.", code="document_type_invalid"
        )
    if compressed == 0 or uncompressed / compressed > MAX_ZIP_RATIO:
        raise ValidationError(
            "La relación de compresión no es segura.", code="document_archive_invalid"
        )
    return DETECTED_CONTENT_TYPES[extension]


def _validate_zip(path: Path, extension: str) -> str:
    embedded_mimetype: bytes | None = None
    content_types_payload: bytes | None = None
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ZIP_ENTRIES:
                raise ValidationError(
                    "El documento comprimido contiene demasiados elementos.",
                    code="document_archive_invalid",
                )
            uncompressed = 0
            compressed = 0
            names: set[str] = set()
            for entry in entries:
                _validate_zip_entry(entry)
                uncompressed += entry.file_size
                compressed += entry.compress_size
                if uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise ValidationError(
                        "El contenido descomprimido supera el límite.",
                        code="document_archive_too_large",
                    )
                names.add(entry.filename)
            if extension in {".odt", ".ods", ".odp"} and "mimetype" in names:
                embedded_mimetype = archive.read("mimetype").strip()
            if extension == ".pptx" and "[Content_Types].xml" in names:
                content_types_payload = archive.read("[Content_Types].xml")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValidationError(
            "El documento comprimido no es válido.", code="document_archive_invalid"
        ) from exc
    return _validate_zip_structure(
        extension,
        names,
        embedded_mimetype,
        content_types_payload,
        compressed=compressed,
        uncompressed=uncompressed,
    )


def _validate_ole_container(path: Path, extension: str) -> str:
    markers = OLE_STREAM_MARKERS[extension]
    overlap = max(len(marker) for marker in markers) - 1
    previous = b""
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            window = previous + chunk
            if any(marker in window for marker in markers):
                return {
                    ".doc": "application/msword",
                    ".xls": "application/vnd.ms-excel",
                    ".ppt": "application/vnd.ms-powerpoint",
                }[extension]
            previous = window[-overlap:]
    raise ValidationError(
        "El contenido no corresponde al tipo de documento Office declarado.",
        code="document_type_invalid",
    )


def _validate_rtf(path: Path) -> str:
    try:
        with path.open("rb") as source:
            prefix = source.read(64).lstrip(b"\xef\xbb\xbf \t\r\n")
            source.seek(-1, 2)
            trailing = source.read(1)
    except OSError as exc:
        raise ValidationError("El RTF no se puede leer.", code="document_type_invalid") from exc
    if not prefix.startswith(b"{\\rtf") or trailing != b"}":
        raise ValidationError(
            "El contenido no corresponde a un RTF válido.", code="document_type_invalid"
        )
    return DETECTED_CONTENT_TYPES[".rtf"]


def _validate_tiff(path: Path) -> bool:
    valid = False
    try:
        size = path.stat().st_size
        with path.open("rb") as source:
            header = source.read(TIFF_BIG_HEADER_BYTES)
            if len(header) >= TIFF_MIN_BYTES:
                byte_order = header[:2]
                if byte_order in {b"II", b"MM"}:
                    endian: Literal["little", "big"] = "little" if byte_order == b"II" else "big"
                    magic = int.from_bytes(header[2:4], endian)
                    valid_header = False
                    if magic == TIFF_CLASSIC_MAGIC:
                        ifd_offset = int.from_bytes(header[4:8], endian)
                        count_size = 2
                        entry_size = 12
                        valid_header = True
                    elif magic == TIFF_BIG_MAGIC and len(header) >= TIFF_BIG_HEADER_BYTES:
                        valid_header = (
                            int.from_bytes(header[4:6], endian) == TIFF_BIG_OFFSET_SIZE
                            and int.from_bytes(header[6:8], endian) == TIFF_BIG_RESERVED
                        )
                        ifd_offset = int.from_bytes(header[8:16], endian)
                        count_size = 8
                        entry_size = 20
                    else:
                        ifd_offset = 0
                        count_size = 0
                        entry_size = 0
                    if (
                        valid_header
                        and ifd_offset >= TIFF_MIN_BYTES
                        and ifd_offset + count_size <= size
                    ):
                        source.seek(ifd_offset)
                        count_bytes = source.read(count_size)
                        if len(count_bytes) == count_size:
                            entry_count = int.from_bytes(count_bytes, endian)
                            valid = (
                                entry_count > 0
                                and ifd_offset + count_size + entry_count * entry_size <= size
                            )
    except OSError:
        valid = False
    return valid


def _validate_text_document(path: Path, extension: str) -> str:
    try:
        if extension == ".json":
            with path.open(encoding="utf-8-sig") as source:
                json.load(source)
        elif extension == ".xml":
            DefusedElementTree.parse(path)
        else:
            path.read_text(encoding="utf-8-sig")
    except (
        DefusedElementTree.ParseError,
        DefusedXmlException,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValidationError(
            f"El contenido no corresponde a un archivo {extension.lstrip('.').upper()} válido.",
            code="document_encoding_invalid"
            if extension in TEXT_EXTENSIONS
            else "document_type_invalid",
        ) from exc
    if extension == ".md":
        return "text/markdown"
    if extension == ".json":
        return "application/json"
    if extension == ".xml":
        return "application/xml"
    return "text/csv" if extension == ".csv" else "text/plain"


def _validate_svg(path: Path) -> str:
    try:
        if path.stat().st_size < SVG_MIN_BYTES:
            raise ValidationError("El SVG no es válido o seguro.", code="document_svg_invalid")
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            "El SVG debe usar codificación UTF-8.", code="document_svg_invalid"
        ) from exc
    except OSError as exc:
        raise ValidationError("El SVG no se puede leer.", code="document_svg_invalid") from exc
    has_svg_root = bool(
        re.search(r"<\s*svg(?:\s|>)", content, flags=re.IGNORECASE)
        and re.search(r"</\s*svg\s*>", content, flags=re.IGNORECASE)
    )
    has_unsafe_content = any(
        re.search(pattern, content, flags=re.IGNORECASE) for pattern in SVG_FORBIDDEN_PATTERNS
    )
    if not has_svg_root or has_unsafe_content:
        raise ValidationError("El SVG no es válido o seguro.", code="document_svg_invalid")
    return IMAGE_CONTENT_TYPES[".svg"]


def _validate_raster_image(path: Path, extension: str) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as source:
            header = source.read(32)
            source.seek(max(0, size - 2))
            trailer = source.read(2)
    except OSError as exc:
        raise ValidationError("La imagen no se puede leer.", code="document_type_invalid") from exc

    if extension in {".jpg", ".jpeg"}:
        valid = (
            size >= JPEG_MIN_BYTES and header.startswith(b"\xff\xd8\xff") and trailer == b"\xff\xd9"
        )
    elif extension == ".png":
        valid = (
            size >= PNG_MIN_BYTES
            and header.startswith(b"\x89PNG\r\n\x1a\n")
            and header[12:16] == b"IHDR"
            and int.from_bytes(header[16:20], "big") > 0
            and int.from_bytes(header[20:24], "big") > 0
        )
    elif extension == ".gif":
        valid = (
            size >= GIF_MIN_BYTES
            and header[:6] in {b"GIF87a", b"GIF89a"}
            and int.from_bytes(header[6:8], "little") > 0
            and int.from_bytes(header[8:10], "little") > 0
        )
    elif extension in {".tif", ".tiff"}:
        valid = _validate_tiff(path)
    else:
        riff_size = int.from_bytes(header[4:8], "little") if len(header) >= RIFF_HEADER_BYTES else 0
        valid = (
            size >= WEBP_MIN_BYTES
            and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
            and RIFF_PAYLOAD_MIN_BYTES <= riff_size <= size - RIFF_HEADER_BYTES
        )

    if not valid:
        raise ValidationError(
            "El contenido no corresponde a una imagen válida.", code="document_type_invalid"
        )
    return IMAGE_CONTENT_TYPES[extension]


def _validate_image(path: Path, extension: str) -> str:
    """Validate supported image signatures and static SVG markup."""
    return _validate_svg(path) if extension == ".svg" else _validate_raster_image(path, extension)


def inspect_document(path: Path, extension: str) -> tuple[str, str]:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        header = source.read(16)
        checksum.update(header)
        while chunk := source.read(1024 * 1024):
            checksum.update(chunk)
    if extension == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise ValidationError("El contenido no es un PDF válido.", code="document_type_invalid")
        detected = "application/pdf"
    elif extension in {".doc", ".xls", ".ppt"}:
        if not header.startswith(OLE_SIGNATURE):
            raise ValidationError(
                "El contenido no corresponde a un documento Office clásico.",
                code="document_type_invalid",
            )
        detected = _validate_ole_container(path, extension)
    elif extension in ZIP_EXTENSIONS:
        if not header.startswith(b"PK"):
            raise ValidationError("El documento Office no es válido.", code="document_type_invalid")
        detected = _validate_zip(path, extension)
    elif extension in IMAGE_EXTENSIONS:
        detected = _validate_image(path, extension)
    elif extension in {".rtf", ".json", ".xml"} or extension in TEXT_EXTENSIONS:
        detected = (
            _validate_rtf(path) if extension == ".rtf" else _validate_text_document(path, extension)
        )
    else:
        raise ValidationError(
            "El formato del documento no está permitido.", code="document_type_invalid"
        )
    return detected, checksum.hexdigest()


def _ensure_checksum(actual: str, expected: str) -> None:
    if actual != expected:
        raise ValidationError("El checksum cargado no coincide.", code="document_checksum_mismatch")


def _ensure_completable(document: DocumentAsset) -> None:
    if document.status == "quarantined":
        raise ValidationError(
            "El documento fue puesto en cuarentena.", code="document_malware_detected"
        )
    if document.status == "rejected":
        raise ConflictError("El documento fue rechazado.", code="document_rejected")
    if document.status == "scanning":
        raise ConflictError(
            "El documento ya está siendo analizado.", code="document_scan_in_progress"
        )


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: ObjectStorage,
        scanner: MalwareScanner,
        audit: AuditService,
        settings: Settings,
        derivatives: DocumentDerivativeRepository | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._audit = audit
        self._settings = settings
        self._derivatives = derivatives

    @staticmethod
    def _attach_ocr(
        document: DocumentAsset, derivative: DocumentDerivative | None
    ) -> DocumentAsset:
        if derivative is None:
            document.ocr_status = None
            document.ocr_available = False
            document.ocr_failure_code = None
            document.ocr_completed_at = None
            return document
        document.ocr_status = derivative.status
        document.ocr_available = derivative.status == "ready"
        document.ocr_failure_code = derivative.failure_code
        document.ocr_completed_at = derivative.completed_at
        return document

    async def _ensure_ocr(self, document: DocumentAsset, actor_id: uuid.UUID) -> DocumentAsset:
        if (
            not self._settings.OCR_ENABLED
            or document.extension != ".pdf"
            or self._derivatives is None
        ):
            return self._attach_ocr(document, None)
        existing = await self._derivatives.get_ocr(document.id)
        derivative_id = uuid.uuid4()
        derivative = await self._derivatives.ensure_ocr(
            derivative_id=derivative_id,
            company_id=document.company_id,
            document_id=document.id,
            bucket=document.bucket,
            object_key=(
                f"companies/{document.company_id}/documents/{document.id}/"
                f"derivatives/ocr/{derivative_id}.pdf"
            ),
        )
        if existing is None:
            await self._audit.record(
                action="DOCUMENT_OCR_QUEUED",
                user_id=actor_id,
                company_id=document.company_id,
                resource_type="documents",
                resource_id=str(document.id),
                after_state={"derivative_id": str(derivative.id), "ocr_status": "pending"},
                required=True,
            )
        return self._attach_ocr(document, derivative)

    async def enrich(self, document: DocumentAsset) -> DocumentAsset:
        """Attach the current OCR projection to an already loaded asset.

        Record repositories intentionally know nothing about OCR derivatives;
        this small public adapter keeps that concern in the document service
        and avoids exposing storage keys to the API layer.
        """
        derivative = await self._derivatives.get_ocr(document.id) if self._derivatives else None
        return self._attach_ocr(document, derivative)

    def _ensure_enabled(self) -> None:
        if not self._settings.OBJECT_STORAGE_ENABLED:
            raise InfrastructureError(
                "El almacenamiento documental no está configurado.",
                code="document_storage_unavailable",
            )

    async def initiate(self, data: InitiateDocumentInput) -> UploadTicket:
        self._ensure_enabled()
        if (
            await self._repository.count_pending(data.actor_id)
            >= self._settings.DOCUMENT_MAX_PENDING_PER_USER
        ):
            raise RateLimitError(
                "Complete o espere la limpieza de sus cargas pendientes.",
                code="document_pending_limit_reached",
            )
        filename, extension, content_type = validate_declaration(
            filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            checksum_sha256=data.checksum_sha256,
            max_bytes=self._settings.DOCUMENT_MAX_BYTES,
        )
        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        object_key = f"companies/{data.company_id}/documents/{document_id}/{uuid.uuid4().hex}"
        expires_at = now + timedelta(seconds=self._settings.OBJECT_STORAGE_UPLOAD_TTL_SECONDS)
        document = await self._repository.add(
            DocumentAsset(
                id=document_id,
                company_id=data.company_id,
                original_filename=filename,
                extension=extension,
                declared_content_type=content_type,
                size_bytes=data.size_bytes,
                checksum_sha256=data.checksum_sha256.lower(),
                bucket=self._settings.OBJECT_STORAGE_BUCKET,
                object_key=object_key,
                upload_expires_at=expires_at,
                uploaded_by=data.actor_id,
            )
        )
        metadata = {"document-id": str(document.id), "sha256": document.checksum_sha256}
        upload = await self._storage.presign_upload(
            object_key,
            content_type=content_type,
            metadata=metadata,
            expires_seconds=self._settings.OBJECT_STORAGE_UPLOAD_TTL_SECONDS,
        )
        await self._audit.record(
            action="DOCUMENT_UPLOAD_INITIATED",
            user_id=data.actor_id,
            company_id=data.company_id,
            resource_type="documents",
            resource_id=str(document.id),
            after_state={"filename": filename, "bytes": data.size_bytes, "status": document.status},
            required=True,
        )
        return UploadTicket(document, upload.url, upload.headers, expires_at)

    async def get(self, company_id: uuid.UUID, document_id: uuid.UUID) -> DocumentAsset:
        self._ensure_enabled()
        document = await self._repository.get(document_id)
        if document is None or document.company_id != company_id:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        return await self.enrich(document)

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None,
        status: str | None,
    ) -> tuple[list[DocumentAsset], int]:
        self._ensure_enabled()
        items, total = await self._repository.list(
            company_id, page=page, size=size, search=search, status=status
        )
        documents = list(items)
        if self._derivatives and documents:
            derivatives = await self._derivatives.list_ocr([item.id for item in documents])
            by_document = {item.document_id: item for item in derivatives}
            documents = [self._attach_ocr(item, by_document.get(item.id)) for item in documents]
        return documents, total

    async def _reject_and_delete(
        self, document: DocumentAsset, code: str, *, scan_finished: bool = False
    ) -> None:
        document.status = "rejected"
        document.failure_code = code
        if scan_finished:
            document.scanned_at = datetime.now(UTC)
        await self._repository.save(document)
        try:
            await self._storage.delete(document.object_key)
        except InfrastructureError:
            return
        document.object_deleted_at = datetime.now(UTC)
        await self._repository.save(document)

    async def _validate_object_info(self, document: DocumentAsset, info: StoredObjectInfo) -> None:
        if (
            info.size_bytes != document.size_bytes
            or info.size_bytes > self._settings.DOCUMENT_MAX_BYTES
        ):
            await self._reject_and_delete(document, "document_size_mismatch")
            raise ValidationError("El tamaño cargado no coincide.", code="document_size_mismatch")
        if info.content_type != document.declared_content_type:
            await self._reject_and_delete(document, "document_content_type_mismatch")
            raise ValidationError("El tipo cargado no coincide.", code="document_type_invalid")
        if (
            info.metadata.get("document-id") != str(document.id)
            or info.metadata.get("sha256") != document.checksum_sha256
        ):
            await self._reject_and_delete(document, "document_metadata_invalid")
            raise ValidationError(
                "Los metadatos de la carga no son válidos.", code="document_metadata_invalid"
            )

    async def _claim_scan(self, document: DocumentAsset) -> DocumentAsset:
        claimed = await self._repository.claim_for_scan(document.id, datetime.now(UTC))
        if claimed is not None:
            return claimed
        refreshed = await self._repository.get(document.id)
        if refreshed is not None and refreshed.status == "active":
            return refreshed
        raise ConflictError(
            "El documento ya está siendo analizado.", code="document_scan_in_progress"
        )

    async def _scan_document(self, document: DocumentAsset) -> tuple[str, ScanResult]:
        try:
            with tempfile.TemporaryDirectory(prefix="erp-document-") as directory:
                path = Path(directory) / "payload"
                await self._storage.download_to(
                    document.object_key, path, self._settings.DOCUMENT_MAX_BYTES
                )
                detected_type, checksum = inspect_document(path, document.extension)
                _ensure_checksum(checksum, document.checksum_sha256)
                scan = await self._scanner.scan(path)
                return detected_type, scan
        except InfrastructureError as exc:
            document.status = "pending_scan"
            document.failure_code = exc.code
            await self._repository.save(document)
            raise
        except ValidationError as exc:
            await self._reject_and_delete(document, exc.code, scan_finished=True)
            raise

    async def complete(
        self, company_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentAsset:
        document = await self.get(company_id, document_id)
        if document.status == "active":
            return await self._ensure_ocr(document, actor_id)
        _ensure_completable(document)
        info = await self._storage.head(document.object_key)
        if info is None:
            raise ValidationError(
                "No se encontró el archivo cargado.", code="document_object_missing"
            )
        await self._validate_object_info(document, info)
        document = await self._claim_scan(document)
        if document.status == "active":
            return document
        detected_type, scan = await self._scan_document(document)
        document.detected_content_type = detected_type
        document.etag = info.etag
        document.scanned_at = datetime.now(UTC)
        if not scan.clean:
            document.status = "quarantined"
            document.failure_code = "document_malware_detected"
            document.malware_name = scan.malware_name
            await self._repository.save(document)
            await self._audit.record(
                action="DOCUMENT_QUARANTINED",
                user_id=actor_id,
                company_id=company_id,
                resource_type="documents",
                resource_id=str(document.id),
                after_state={"filename": document.original_filename, "status": document.status},
                required=True,
            )
            raise ValidationError(
                "El antivirus detectó contenido malicioso.", code="document_malware_detected"
            )
        document.status = "active"
        document.failure_code = None
        saved = await self._repository.save(document)
        await self._audit.record(
            action="DOCUMENT_ACTIVATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document.id),
            after_state={"filename": document.original_filename, "status": "active"},
            required=True,
        )
        return await self._ensure_ocr(saved, actor_id)

    async def download_url(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        variant: str = "original",
    ) -> tuple[str, datetime]:
        document = await self.get(company_id, document_id)
        if document.status != "active":
            raise ConflictError(
                "El documento todavía no está disponible.", code="document_not_downloadable"
            )
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS
        )
        object_key = document.object_key
        filename = document.original_filename
        content_type = document.detected_content_type or document.declared_content_type
        action = "DOCUMENT_DOWNLOAD_URL_ISSUED"
        if variant == "ocr":
            derivative = await self._derivatives.get_ocr(document.id) if self._derivatives else None
            if derivative is None or derivative.status != "ready":
                raise ConflictError(
                    "La versión OCR todavía no está disponible.", code="document_ocr_not_ready"
                )
            object_key = derivative.object_key
            filename = f"{Path(document.original_filename).stem}-ocr.pdf"
            content_type = derivative.content_type
            action = "DOCUMENT_OCR_DOWNLOAD_URL_ISSUED"
        url = await self._storage.presign_download(
            object_key,
            filename=filename,
            content_type=content_type,
            expires_seconds=self._settings.OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS,
        )
        await self._audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document.id),
        )
        return url, expires_at

    async def preview_url(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        variant: str = "original",
    ) -> tuple[str, datetime]:
        document = await self.get(company_id, document_id)
        if document.status != "active" or (
            document.extension != ".pdf" and document.extension not in IMAGE_EXTENSIONS
        ):
            raise ConflictError(
                "Solo los PDF e imágenes activas pueden previsualizarse.",
                code="document_preview_not_available",
            )
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS
        )
        object_key = document.object_key
        filename = document.original_filename
        content_type = document.detected_content_type or document.declared_content_type
        action = "DOCUMENT_PREVIEW_URL_ISSUED"
        if variant == "ocr":
            if document.extension != ".pdf":
                raise ConflictError(
                    "Solo los PDF admiten vista previa OCR.",
                    code="document_preview_not_available",
                )
            derivative = await self._derivatives.get_ocr(document.id) if self._derivatives else None
            if derivative is None or derivative.status != "ready":
                raise ConflictError(
                    "La versión OCR todavía no está disponible.", code="document_ocr_not_ready"
                )
            object_key = derivative.object_key
            filename = f"{Path(document.original_filename).stem}-ocr.pdf"
            content_type = derivative.content_type
            action = "DOCUMENT_OCR_PREVIEW_URL_ISSUED"
        elif variant != "original":
            raise ConflictError(
                "La variante de vista previa no es válida.",
                code="document_preview_not_available",
            )
        url = await self._storage.presign_preview(
            object_key,
            filename=filename,
            content_type=content_type,
            expires_seconds=self._settings.OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS,
        )
        await self._audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document.id),
        )
        return url, expires_at

    async def retry_ocr(
        self, company_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentAsset:
        if not self._settings.OCR_ENABLED or self._derivatives is None:
            raise InfrastructureError(
                "El procesamiento OCR no está configurado.",
                code="document_processing_unavailable",
            )
        document = await self.get(company_id, document_id)
        if document.status != "active" or document.extension != ".pdf":
            raise ConflictError(
                "El documento no admite procesamiento OCR.", code="document_ocr_not_available"
            )
        derivative = await self._derivatives.get_ocr(document.id)
        if derivative is None:
            raise ConflictError(
                "El documento no tiene un trabajo OCR.", code="document_ocr_not_available"
            )
        reset = await self._derivatives.reset_for_retry(derivative.id)
        if reset is None:
            raise ConflictError(
                "El trabajo OCR no se puede reintentar en su estado actual.",
                code="document_ocr_retry_not_allowed",
            )
        await self._audit.record(
            action="DOCUMENT_OCR_RETRY_REQUESTED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document.id),
            after_state={"derivative_id": str(reset.id), "ocr_status": reset.status},
            required=True,
        )
        return self._attach_ocr(document, reset)
