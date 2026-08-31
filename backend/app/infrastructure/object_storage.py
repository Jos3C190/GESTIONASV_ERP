from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.exceptions import InfrastructureError, ValidationError
from app.domain.ports.object_storage import PresignedUpload, StoredObjectInfo


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _client(self, endpoint: str) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self._settings.OBJECT_STORAGE_ACCESS_KEY,
            aws_secret_access_key=self._settings.OBJECT_STORAGE_SECRET_KEY,
            region_name=self._settings.OBJECT_STORAGE_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @property
    def _bucket(self) -> str:
        return str(self._settings.OBJECT_STORAGE_BUCKET)

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            client = self._client(self._settings.OBJECT_STORAGE_INTERNAL_ENDPOINT)
            try:
                client.head_bucket(Bucket=self._bucket)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
                client.create_bucket(Bucket=self._bucket)
            client.put_public_access_block(
                Bucket=self._bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            client.put_bucket_cors(
                Bucket=self._bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": self._settings.object_storage_cors_origin_list,
                            "AllowedMethods": ["PUT", "GET", "HEAD"],
                            "AllowedHeaders": ["*"],
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 600,
                        }
                    ]
                },
            )

        try:
            await asyncio.to_thread(_ensure)
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo inicializar el almacenamiento documental.",
                code="document_storage_initialization_failed",
            ) from exc

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str,
        metadata: dict[str, str],
        expires_seconds: int,
    ) -> PresignedUpload:
        try:
            client = self._client(self._settings.OBJECT_STORAGE_PUBLIC_ENDPOINT)
            params = {
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "Metadata": metadata,
            }
            url = await asyncio.to_thread(
                client.generate_presigned_url,
                "put_object",
                Params=params,
                ExpiresIn=expires_seconds,
                HttpMethod="PUT",
            )
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo autorizar la carga documental.",
                code="document_storage_unavailable",
            ) from exc
        headers = {"Content-Type": content_type}
        headers.update({f"x-amz-meta-{name}": value for name, value in metadata.items()})
        return PresignedUpload(url=str(url), headers=headers)

    async def presign_download(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        try:
            client = self._client(self._settings.OBJECT_STORAGE_PUBLIC_ENDPOINT)
            disposition = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
            url = await asyncio.to_thread(
                client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentDisposition": disposition,
                    "ResponseContentType": content_type,
                },
                ExpiresIn=expires_seconds,
                HttpMethod="GET",
            )
            return str(url)
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo autorizar la descarga documental.",
                code="document_storage_unavailable",
            ) from exc

    async def head(self, key: str) -> StoredObjectInfo | None:
        try:
            client = self._client(self._settings.OBJECT_STORAGE_INTERNAL_ENDPOINT)
            response = await asyncio.to_thread(client.head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise InfrastructureError(
                "No se pudo consultar el documento almacenado.",
                code="document_storage_unavailable",
            ) from exc
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo consultar el documento almacenado.",
                code="document_storage_unavailable",
            ) from exc
        return StoredObjectInfo(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
            etag=str(response.get("ETag", "")).strip('"') or None,
            metadata={str(k): str(v) for k, v in response.get("Metadata", {}).items()},
        )

    async def download_to(self, key: str, destination: Path, max_bytes: int) -> None:
        def _download() -> None:
            client = self._client(self._settings.OBJECT_STORAGE_INTERNAL_ENDPOINT)
            response = client.get_object(Bucket=self._bucket, Key=key)
            total = 0
            with destination.open("wb") as target:
                while chunk := response["Body"].read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValidationError(
                            "El archivo supera el tamaño permitido.",
                            code="document_size_invalid",
                        )
                    target.write(chunk)

        try:
            await asyncio.to_thread(_download)
        except ValidationError:
            raise
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo leer el documento almacenado.", code="document_storage_unavailable"
            ) from exc

    async def delete(self, key: str) -> None:
        try:
            client = self._client(self._settings.OBJECT_STORAGE_INTERNAL_ENDPOINT)
            await asyncio.to_thread(client.delete_object, Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise InfrastructureError(
                "No se pudo eliminar el objeto almacenado.", code="document_storage_unavailable"
            ) from exc

    async def health(self) -> bool:
        try:
            client = self._client(self._settings.OBJECT_STORAGE_INTERNAL_ENDPOINT)
            await asyncio.to_thread(client.head_bucket, Bucket=self._bucket)
        except Exception:
            return False
        else:
            return True
