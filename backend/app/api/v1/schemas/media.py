from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MediaPurpose = Literal[
    "company_logo", "employee_avatar", "branch_image", "warehouse_image", "product_image"
]


class UploadSignatureIn(BaseModel):
    company_id: uuid.UUID | None = None
    purpose: MediaPurpose


class UploadSignatureOut(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    signature: str
    folder: str
    public_id: str
    upload_url: str
    max_bytes: int
    allowed_formats: list[str]


class DeleteAssetIn(BaseModel):
    company_id: uuid.UUID
    public_id: str | None = Field(None, min_length=3, max_length=500)
    secure_url: str | None = Field(None, min_length=10, max_length=2048)

    @model_validator(mode="after")
    def require_asset_identifier(self) -> DeleteAssetIn:
        if not self.public_id and not self.secure_url:
            raise ValueError("Indique el identificador o la URL del activo.")
        return self


class ConfirmUploadIn(BaseModel):
    company_id: uuid.UUID | None = None
    purpose: MediaPurpose
    public_id: str = Field(min_length=3, max_length=500)
    secure_url: str = Field(min_length=10, max_length=2048)
    format: str = Field(min_length=2, max_length=16)
    bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
