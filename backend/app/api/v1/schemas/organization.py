"""DTOs for the organizational hierarchy required by MiniERP ERS v0.5."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    commercial_name: str = Field(min_length=2, max_length=200)
    nit: str = Field(min_length=3, max_length=32)
    nrc: str = Field(min_length=3, max_length=32)
    address: str = Field(min_length=3)
    department_id: uuid.UUID
    municipality_id: uuid.UUID
    district_id: uuid.UUID
    commercial_line_1: str | None = None
    commercial_line_2: str | None = None
    commercial_line_3: str | None = None
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    web_site: str | None = Field(None, max_length=2048)
    logo: str | None = Field(None, max_length=2048)


class GeographicDepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class MunicipalityIn(BaseModel):
    department_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)


class DistrictIn(BaseModel):
    municipality_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)


class BranchIn(BaseModel):
    company_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=3)
    department_id: uuid.UUID
    municipality_id: uuid.UUID
    district_id: uuid.UUID
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None


class WarehouseCategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class WarehouseIn(BaseModel):
    branch_id: uuid.UUID
    warehouse_category_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None


class LocationIn(BaseModel):
    warehouse_id: uuid.UUID
    code: str = Field(min_length=1, max_length=120)
    aisle: str = Field(min_length=1, max_length=64)
    rack: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    position: str = Field(min_length=1, max_length=64)
    capacity: int = Field(gt=0)
    notes: str | None = None
