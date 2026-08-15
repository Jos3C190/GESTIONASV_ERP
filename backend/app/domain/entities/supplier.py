"""Domain entities: Supplier, SupplierContact."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.media_image import SingleImage


@dataclass(frozen=True, slots=True)
class SupplierContact:
    id: int
    supplier_id: int
    full_name: str
    uuid: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    avatar_image: SingleImage | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Supplier:
    id: int
    uuid: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    country_id: int
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    is_active: bool = True
    logo_image: SingleImage | None = None
    contacts: tuple[SupplierContact, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
