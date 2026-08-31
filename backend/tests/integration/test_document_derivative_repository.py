from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.organization import Company
from app.infrastructure.repositories.document_derivative_repository import (
    SqlAlchemyDocumentDerivativeRepository,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
async def derivative_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


async def add_document(session: AsyncSession) -> DocumentAssetModel:
    company_id = await session.scalar(select(Company.id).limit(1))
    assert company_id is not None
    document = DocumentAssetModel(
        id=uuid.uuid4(),
        company_id=company_id,
        original_filename="integration.pdf",
        extension=".pdf",
        declared_content_type="application/pdf",
        detected_content_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
        bucket="erp-documents",
        object_key=f"integration/original/{uuid.uuid4()}",
        status="active",
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    session.add(document)
    await session.flush()
    return document


@pytest.mark.asyncio
async def test_ocr_derivative_is_idempotent_and_claimed_once(
    derivative_session: AsyncSession,
) -> None:
    document = await add_document(derivative_session)
    repository = SqlAlchemyDocumentDerivativeRepository(derivative_session)
    derivative_id = uuid.uuid4()

    first = await repository.ensure_ocr(
        derivative_id=derivative_id,
        company_id=document.company_id,
        document_id=document.id,
        bucket=document.bucket,
        object_key=f"integration/ocr/{derivative_id}.pdf",
    )
    repeated = await repository.ensure_ocr(
        derivative_id=uuid.uuid4(),
        company_id=document.company_id,
        document_id=document.id,
        bucket=document.bucket,
        object_key=f"integration/ocr/{uuid.uuid4()}.pdf",
    )

    assert repeated.id == first.id
    assert await repository.list_pending_ids(10) == [first.id]
    claimed = await repository.claim(first.id, datetime.now(UTC))
    duplicate = await repository.claim(first.id, datetime.now(UTC))
    assert claimed is not None
    assert claimed.status == "processing"
    assert claimed.attempts == 1
    assert duplicate is None


@pytest.mark.asyncio
async def test_stale_processing_returns_to_pending(
    derivative_session: AsyncSession,
) -> None:
    document = await add_document(derivative_session)
    repository = SqlAlchemyDocumentDerivativeRepository(derivative_session)
    derivative_id = uuid.uuid4()
    derivative = await repository.ensure_ocr(
        derivative_id=derivative_id,
        company_id=document.company_id,
        document_id=document.id,
        bucket=document.bucket,
        object_key=f"integration/ocr/{derivative_id}.pdf",
    )
    old = datetime.now(UTC) - timedelta(minutes=30)
    assert await repository.claim(derivative.id, old) is not None

    assert await repository.reset_stale(datetime.now(UTC) - timedelta(minutes=20)) == 1
    refreshed = await repository.get(derivative.id)
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.failure_code == "ocr_processing_interrupted"
