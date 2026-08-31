from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


def _client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.OBJECT_STORAGE_INTERNAL_ENDPOINT,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY,
        region_name=settings.OBJECT_STORAGE_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_object_path(root: Path, key: str) -> Path:
    pure = PurePosixPath(key)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe object key: {key}")
    return root.joinpath(*pure.parts)


def export_backup(root: Path) -> Path:
    client = _client()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = root / stamp
    objects_root = target / "objects"
    objects_root.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "bucket": settings.OBJECT_STORAGE_BUCKET,
        "objects": [],
    }
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.OBJECT_STORAGE_BUCKET):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            path = _safe_object_path(objects_root, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(settings.OBJECT_STORAGE_BUCKET, key, str(path))
            head = client.head_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
            manifest["objects"].append(
                {
                    "key": key,
                    "size": path.stat().st_size,
                    "etag": str(head.get("ETag", "")).strip('"'),
                    "content_type": head.get("ContentType"),
                    "metadata": head.get("Metadata", {}),
                    "sha256": _sha256(path),
                }
            )
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return target


def restore_backup(source: Path, *, force: bool) -> int:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    client = _client()
    restored = 0
    for item in manifest["objects"]:
        key = str(item["key"])
        path = _safe_object_path(source / "objects", key)
        if _sha256(path) != item["sha256"]:
            raise ValueError(f"Checksum mismatch: {key}")
        try:
            client.head_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
            exists = True
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            exists = False
        if exists and not force:
            raise FileExistsError(f"Object already exists: {key}")
        extra: dict[str, Any] = {"Metadata": item.get("metadata", {})}
        if item.get("content_type"):
            extra["ContentType"] = item["content_type"]
        client.upload_file(str(path), settings.OBJECT_STORAGE_BUCKET, key, ExtraArgs=extra)
        restored += 1
    return restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "restore"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.action == "export":
        print(export_backup(args.path))
    else:
        print(restore_backup(args.path, force=os.getenv("STORAGE_RESTORE_FORCE") == "true"))


if __name__ == "__main__":
    main()
