"""Signed Cloudinary upload orchestration for ERP-owned images."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select

from app.api.v1.company_access import require_company_access
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.media import (
    ConfirmUploadIn,
    DeleteAssetIn,
    UploadSignatureIn,
    UploadSignatureOut,
)
from app.application.media import cloudinary_signature
from app.core.config import settings
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.media import MediaAsset

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)


def _credentials() -> tuple[str, str, str]:
    values = (
        settings.CLOUDINARY_CLOUD_NAME,
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    )
    if not all(values):
        raise HTTPException(
            status_code=503,
            detail="Cloudinary no está configurado. Agregue sus credenciales al archivo .env.",
        )
    return values  # type: ignore[return-value]


def _company_folder(company_id: uuid.UUID, purpose: str) -> str:
    root = settings.CLOUDINARY_UPLOAD_FOLDER.strip("/")
    return f"{root}/{settings.ENVIRONMENT}/companies/{company_id}/{purpose}"


@router.post(
    "/upload-signature",
    response_model=UploadSignatureOut,
    dependencies=[Depends(require_permission("media.upload"))],
)
async def create_upload_signature(
    body: UploadSignatureIn, session: SessionDep, current: CurrentUser
) -> UploadSignatureOut:
    await _cleanup_abandoned_assets(session, current)
    if body.company_id is not None:
        await require_company_access(session, current, body.company_id, require_active=True)
    elif body.purpose != "company_logo":
        raise HTTPException(422, "Seleccione una empresa antes de cargar la imagen.")
    cloud_name, api_key, api_secret = _credentials()
    timestamp = int(time.time())
    folder = (
        _company_folder(body.company_id, body.purpose)
        if body.company_id is not None
        else f"{settings.CLOUDINARY_UPLOAD_FOLDER.strip('/')}/{settings.ENVIRONMENT}/staged/users/{current.id}/company_logo"
    )
    public_id = uuid.uuid4().hex
    params = {"folder": folder, "public_id": public_id, "timestamp": timestamp}
    return UploadSignatureOut(
        cloud_name=cloud_name,
        api_key=api_key,
        timestamp=timestamp,
        signature=cloudinary_signature(params, api_secret),
        folder=folder,
        public_id=public_id,
        upload_url=f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
        max_bytes=settings.MEDIA_MAX_IMAGE_BYTES,
        allowed_formats=["jpg", "jpeg", "png", "webp"],
    )


@router.post(
    "/confirm",
    dependencies=[Depends(require_permission("media.upload"))],
)
async def confirm_upload(
    body: ConfirmUploadIn, session: SessionDep, current: CurrentUser
) -> dict[str, object]:
    if body.company_id is not None:
        await require_company_access(session, current, body.company_id, require_active=True)
        expected = _company_folder(body.company_id, body.purpose) + "/"
    else:
        if body.purpose != "company_logo":
            raise HTTPException(422, "La carga debe pertenecer a una empresa.")
        expected = f"{settings.CLOUDINARY_UPLOAD_FOLDER.strip('/')}/{settings.ENVIRONMENT}/staged/users/{current.id}/company_logo/"
    if not body.public_id.startswith(expected):
        raise HTTPException(403, "La imagen no pertenece al contexto solicitado.")
    if not body.secure_url.startswith("https://res.cloudinary.com/"):
        raise HTTPException(422, "La URL de imagen no pertenece a Cloudinary.")
    if body.format.lower() not in {"jpg", "jpeg", "png", "webp"}:
        raise HTTPException(422, "Formato de imagen no permitido.")
    if body.bytes > settings.MEDIA_MAX_IMAGE_BYTES:
        raise HTTPException(422, "La imagen supera el tamaño permitido.")
    asset = MediaAsset(
        company_id=body.company_id,
        purpose=body.purpose,
        public_id=body.public_id,
        secure_url=body.secure_url,
        format=body.format.lower(),
        bytes=body.bytes,
        width=body.width,
        height=body.height,
        status="staged",
        uploaded_by=current.id,
    )
    session.add(asset)
    await session.flush()
    session.add(
        AuditLog(
            action="UPLOAD",
            user_id=current.id,
            company_id=body.company_id,
            resource_type="media_assets",
            resource_id=str(asset.id),
            after_state={"purpose": body.purpose, "format": body.format, "bytes": body.bytes},
        )
    )
    return {"id": str(asset.id), "url": asset.secure_url, "public_id": asset.public_id}


def _destroy_asset(url: str, fields: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(  # noqa: S310
        url,
        data=urllib.parse.urlencode(fields).encode(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        return json.loads(response.read().decode())


async def _destroy_public_id(public_id: str) -> None:
    cloud_name, api_key, api_secret = _credentials()
    timestamp = int(time.time())
    params = {"invalidate": True, "public_id": public_id, "timestamp": timestamp}
    fields = {
        **{
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in params.items()
        },
        "api_key": api_key,
        "signature": cloudinary_signature(params, api_secret),
    }
    result = await asyncio.to_thread(
        _destroy_asset,
        f"https://api.cloudinary.com/v1_1/{cloud_name}/image/destroy",
        fields,
    )
    if result.get("result") not in {"ok", "not found"}:
        raise RuntimeError("Cloudinary rechazó la eliminación del activo.")


async def _cleanup_abandoned_assets(session: SessionDep, current: CurrentUser) -> None:
    """Clean stale uploads opportunistically without a separate worker."""
    now = datetime.now(UTC)
    assets = (
        (
            await session.execute(
                select(MediaAsset)
                .where(
                    MediaAsset.uploaded_by == current.id,
                    or_(
                        (MediaAsset.status == "staged")
                        & (MediaAsset.created_at < now - timedelta(hours=24)),
                        (MediaAsset.status == "detached")
                        & (MediaAsset.updated_at < now - timedelta(hours=1)),
                    ),
                )
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    for asset in assets:
        try:
            await _destroy_public_id(asset.public_id)
        except Exception:
            logger.warning("No se pudo limpiar el activo multimedia abandonado %s", asset.id)
            continue
        asset.status = "deleted"


@router.post(
    "/delete",
    dependencies=[Depends(require_permission("media.delete"))],
)
async def delete_asset(
    body: DeleteAssetIn, session: SessionDep, current: CurrentUser
) -> dict[str, str]:
    await require_company_access(session, current, body.company_id, require_active=True)
    lookup = [MediaAsset.company_id == body.company_id, MediaAsset.status != "deleted"]
    lookup.append(
        MediaAsset.public_id == body.public_id
        if body.public_id
        else MediaAsset.secure_url == body.secure_url
    )
    asset = await session.scalar(select(MediaAsset).where(*lookup))
    if asset is None:
        raise HTTPException(404, "El activo multimedia no está registrado.")
    expected_prefix = f"{_company_folder(body.company_id, '')}".rstrip("/") + "/"
    if not asset.public_id.startswith(expected_prefix):
        raise HTTPException(403, "El activo no pertenece a la empresa seleccionada.")
    try:
        await _destroy_public_id(asset.public_id)
    except Exception as exc:
        raise HTTPException(502, "Cloudinary no pudo eliminar la imagen.") from exc
    asset.status = "deleted"
    session.add(
        AuditLog(
            action="DELETE",
            user_id=current.id,
            company_id=body.company_id,
            resource_type="media_assets",
            resource_id=str(asset.id),
            before_state={"purpose": asset.purpose, "public_id": asset.public_id},
        )
    )
    return {"message": "Imagen eliminada.", "code": "media_deleted"}
