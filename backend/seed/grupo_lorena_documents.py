"""Demonstration documents for seeded vehicles and drivers.

Compliance only counts documents whose file passed the antivirus, so the seed
uses the same pipeline as a user: the file goes to object storage, the document
service scans and activates it, and the record is created the way each screen
does it. Circulation cards and driver licenses are registered only through the
guided capture, which ends by adopting the scanned asset; the seed adopts it the
same way. Every file is an image clearly marked as demonstration data.
"""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.infrastructure.object_storage import S3ObjectStorage

CONTENT_TYPE = "image/png"
DEMO_NOTICE = "DOCUMENTO DE DEMOSTRACIÓN - DATOS FICTICIOS"


@dataclass(frozen=True, slots=True)
class DocumentSeed:
    category_code: str
    title: str
    reference_code: str | None = None
    issuer: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    confidentiality: str = "internal"
    lines: tuple[str, ...] = ()


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 de febrero
        return value.replace(year=value.year + years, day=28)


def vehicle_documents(
    code: str, plate: str, brand: str, model: str, today: date
) -> tuple[DocumentSeed, ...]:
    issued = today.replace(day=1)
    expires = add_years(issued, 1)
    vehicle = f"{brand} {model} · {code}"
    card = (f"Placa: {plate}", f"Vehículo: {vehicle}")
    return (
        DocumentSeed(
            "circulation_card",
            "Tarjeta de circulación",
            plate,
            None,
            issued,
            expires,
            lines=card,
        ),
        DocumentSeed(
            "circulation_card_back",
            "Reverso de tarjeta de circulación",
            plate,
            None,
            issued,
            expires,
            lines=card,
        ),
        DocumentSeed(
            "insurance_policy",
            "Póliza de seguro",
            f"POL-DEMO-{code}",
            "Aseguradora de demostración",
            issued,
            expires,
            lines=card,
        ),
        DocumentSeed(
            "technical_inspection",
            "Revisión técnica",
            f"RT-DEMO-{code}",
            "Centro de revisión técnica de demostración",
            issued,
            expires,
            lines=card,
        ),
    )


def driver_documents(
    employee_code: str, name: str, license_class: str, today: date
) -> tuple[DocumentSeed, ...]:
    issued = add_years(today.replace(day=1), -1)
    holder = (f"Titular: {name}", f"Clase: {license_class.replace('_', ' ').title()}")
    return (
        DocumentSeed(
            "driver_license",
            "Licencia de conducir",
            f"DEMO-{employee_code}",
            None,
            issued,
            add_years(issued, 5),
            lines=holder,
        ),
        DocumentSeed(
            "driver_license_back",
            "Reverso de licencia de conducir",
            confidentiality="restricted",
            lines=holder,
        ),
    )


def render_demo_document(seed: DocumentSeed) -> bytes:
    """A deterministic card-sized PNG that says what it is and that it is fictional."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1200, 760), "white")
    draw = ImageDraw.Draw(image)
    heading = ImageFont.load_default(size=44)
    body = ImageFont.load_default(size=30)
    draw.rectangle((24, 24, 1176, 736), outline=(31, 64, 122), width=6)
    draw.text((64, 64), seed.title, fill=(31, 64, 122), font=heading)
    lines = list(seed.lines)
    if seed.reference_code:
        lines.append(f"Referencia: {seed.reference_code}")
    if seed.issuer:
        lines.append(f"Emisor: {seed.issuer}")
    if seed.issued_on:
        lines.append(f"Emisión: {seed.issued_on:%d/%m/%Y}")
    if seed.expires_on:
        lines.append(f"Vencimiento: {seed.expires_on:%d/%m/%Y}")
    for index, line in enumerate(lines):
        draw.text((64, 160 + index * 52), line, fill=(30, 30, 30), font=body)
    draw.text((64, 660), DEMO_NOTICE, fill=(176, 32, 32), font=body)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _has_valid_document(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    module: str,
    owner_type: str,
    owner_id: uuid.UUID,
    category_code: str,
    valid_after: date,
) -> bool:
    from app.infrastructure.models.document import DocumentAssetModel
    from app.infrastructure.models.document_record import (
        DocumentCategoryModel,
        DocumentRecordModel,
    )

    rows = await session.scalars(
        select(DocumentRecordModel.expires_on)
        .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
        .join(DocumentCategoryModel, DocumentCategoryModel.id == DocumentRecordModel.category_id)
        .where(
            DocumentRecordModel.company_id == company_id,
            DocumentRecordModel.module == module,
            DocumentRecordModel.owner_type == owner_type,
            DocumentRecordModel.owner_id == owner_id,
            DocumentRecordModel.is_current.is_(True),
            DocumentCategoryModel.code == category_code,
            DocumentAssetModel.status == "active",
            DocumentAssetModel.deleted_at.is_(None),
        )
    )
    return any(expires_on is None or expires_on > valid_after for expires_on in rows)


async def ensure_documents(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
    module: str,
    owner_type: str,
    owner_id: uuid.UUID,
    documents: Sequence[DocumentSeed],
    today: date,
    warning_days: int,
) -> int:
    """Upload whatever is missing or about to expire; return how many were added.

    The document service commits while it claims the antivirus scan, so this
    runs after the seed's own transaction and commits each document.
    """
    from app.application.audit.audit_service import AuditService
    from app.application.documents.record_service import (
        CAPTURE_ONLY_CATEGORY_CODES,
        DocumentMetadataInput,
        DocumentRecordService,
    )
    from app.application.documents.service import DocumentService, InitiateDocumentInput
    from app.core.config import settings
    from app.infrastructure.malware_scanner import ClamAVScanner
    from app.infrastructure.models.document_record import DocumentCategoryModel
    from app.infrastructure.object_storage import S3ObjectStorage
    from app.infrastructure.repositories import SqlAlchemyEmployeeRepository
    from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
    from app.infrastructure.repositories.document_derivative_repository import (
        SqlAlchemyDocumentDerivativeRepository,
    )
    from app.infrastructure.repositories.document_record_repository import (
        SqlAlchemyDocumentRecordRepository,
    )
    from app.infrastructure.repositories.document_repository import (
        SqlAlchemyDocumentRepository,
    )

    storage = S3ObjectStorage(settings)
    audit = AuditService(SqlAlchemyAuditRepository(session))
    service = DocumentService(
        SqlAlchemyDocumentRepository(session),
        storage,
        ClamAVScanner(settings.CLAMAV_HOST, settings.CLAMAV_PORT, settings.CLAMAV_TIMEOUT_SECONDS),
        audit,
        settings,
        SqlAlchemyDocumentDerivativeRepository(session),
    )
    records = DocumentRecordService(
        service,
        SqlAlchemyDocumentRecordRepository(session),
        SqlAlchemyEmployeeRepository(session),
        audit,
    )
    valid_after = today + timedelta(days=warning_days)
    added = 0
    for document in documents:
        if await _has_valid_document(
            session,
            company_id=company_id,
            module=module,
            owner_type=owner_type,
            owner_id=owner_id,
            category_code=document.category_code,
            valid_after=valid_after,
        ):
            continue
        category_id = await session.scalar(
            select(DocumentCategoryModel.id).where(
                DocumentCategoryModel.company_id == company_id,
                DocumentCategoryModel.module == module,
                DocumentCategoryModel.code == document.category_code,
                DocumentCategoryModel.is_active.is_(True),
            )
        )
        if category_id is None:
            raise RuntimeError(f"Falta la categoría de documentos {document.category_code}.")
        payload = render_demo_document(document)
        upload = InitiateDocumentInput(
            company_id=company_id,
            actor_id=actor_id,
            filename=f"{document.category_code}-demo.png",
            content_type=CONTENT_TYPE,
            size_bytes=len(payload),
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
        )
        metadata = DocumentMetadataInput(
            category_id=category_id,
            title=document.title,
            description="Documento de demostración generado por el seed de desarrollo.",
            reference_code=document.reference_code,
            issuer=document.issuer,
            issued_on=document.issued_on,
            expires_on=document.expires_on,
            confidentiality=document.confidentiality,
        )
        if document.category_code in CAPTURE_ONLY_CATEGORY_CODES:
            # Como al confirmar la captura guiada: el archivo escaneado se adopta.
            asset = (await service.initiate(upload)).document
            await _put(storage, asset.object_key, asset.id, upload.checksum_sha256, payload)
            await service.complete(company_id, asset.id, actor_id)
            await records.adopt_asset(
                company_id,
                asset.id,
                actor_id,
                module=module,
                owner_type=owner_type,
                owner_id=owner_id,
                category_code=document.category_code,
                metadata=metadata,
            )
        else:
            ticket = (
                await records.initiate_owned(module, owner_type, owner_id, upload, metadata)
            ).ticket
            asset = ticket.document
            await _put(storage, asset.object_key, asset.id, upload.checksum_sha256, payload)
            await records.complete(company_id, asset.id, actor_id)
        await session.commit()
        added += 1
    return added


async def _put(
    storage: S3ObjectStorage, key: str, document_id: uuid.UUID, checksum: str, payload: bytes
) -> None:
    """Upload what the browser would send to the presigned URL."""
    with tempfile.TemporaryDirectory(prefix="erp-seed-") as directory:
        path = Path(directory) / "payload.png"
        path.write_bytes(payload)
        await storage.upload_from(
            key,
            path,
            content_type=CONTENT_TYPE,
            metadata={"document-id": str(document_id), "sha256": checksum},
        )
