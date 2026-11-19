"""Puerto del repositorio de la base fiscal del emisor.

Toda operación recibe la empresa: es la unidad de aislamiento del emisor y ninguna
consulta cruza empresas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.fiscal import (
    BranchOption,
    CatalogItem,
    CertificationStatus,
    CompanyIdentity,
    DocumentTypeSetting,
    EconomicActivity,
    Establishment,
    EstablishmentType,
    FiscalProfile,
    IssuerFacts,
    OperatingMode,
    PersonType,
    PointOfSale,
    TaxpayerCategory,
)


@dataclass(frozen=True, slots=True)
class ProfileValues:
    taxpayer_category: TaxpayerCategory
    person_type: PersonType
    operating_mode: OperatingMode
    dte_email: str | None
    dte_phone: str | None


@dataclass(frozen=True, slots=True)
class EstablishmentValues:
    establishment_type: EstablishmentType
    code: str
    activity_id: uuid.UUID | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class DocumentTypeValues:
    is_enabled: bool
    certification_status: CertificationStatus
    notes: str | None


class FiscalRepository(Protocol):
    # --- Hacienda catalogs (global) ---
    def catalog_titles(self) -> dict[str, str]: ...

    async def list_catalog(
        self, catalog_code: str, *, group_code: str | None, search: str | None, limit: int
    ) -> list[CatalogItem]: ...

    async def catalog_item(
        self, catalog_code: str, code: str, group_code: str = ""
    ) -> CatalogItem | None: ...

    # --- profile ---
    async def company_identity(self, company_id: uuid.UUID) -> CompanyIdentity | None: ...

    async def get_profile(self, company_id: uuid.UUID) -> FiscalProfile: ...

    async def save_profile(
        self, company_id: uuid.UUID, values: ProfileValues, actor_id: uuid.UUID
    ) -> FiscalProfile: ...

    async def issuer_facts(self, company_id: uuid.UUID) -> IssuerFacts: ...

    # --- economic activities ---
    async def list_activities(self, company_id: uuid.UUID) -> list[EconomicActivity]: ...

    async def get_activity(
        self, company_id: uuid.UUID, activity_id: uuid.UUID
    ) -> EconomicActivity | None: ...

    async def activity_code_exists(self, company_id: uuid.UUID, code: str) -> bool: ...

    async def add_activity(
        self, company_id: uuid.UUID, code: str, *, is_primary: bool, actor_id: uuid.UUID
    ) -> EconomicActivity: ...

    async def set_activity_renta(
        self,
        company_id: uuid.UUID,
        activity_id: uuid.UUID,
        operation_type: int | None,
        income_type: int | None,
    ) -> None: ...

    async def set_primary_activity(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> None: ...

    async def activity_in_use(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> bool: ...

    async def delete_activity(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> None: ...

    # --- establishments and points of sale ---
    async def list_establishments(self, company_id: uuid.UUID) -> list[Establishment]: ...

    async def get_establishment(
        self, company_id: uuid.UUID, establishment_id: uuid.UUID
    ) -> Establishment | None: ...

    async def branch_options(self, company_id: uuid.UUID) -> list[BranchOption]: ...

    async def branch_name(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> str | None: ...

    async def branch_has_establishment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, exclude_id: uuid.UUID | None = None
    ) -> bool: ...

    async def establishment_code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool: ...

    async def create_establishment(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        values: EstablishmentValues,
        actor_id: uuid.UUID,
    ) -> Establishment: ...

    async def update_establishment(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        values: EstablishmentValues,
        actor_id: uuid.UUID,
    ) -> Establishment: ...

    async def get_point_of_sale(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSale | None: ...

    async def point_of_sale_code_taken(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        code: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def create_point_of_sale(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        code: str,
        name: str,
        actor_id: uuid.UUID,
    ) -> PointOfSale: ...

    async def update_point_of_sale(
        self,
        company_id: uuid.UUID,
        point_of_sale_id: uuid.UUID,
        *,
        code: str,
        name: str,
        is_active: bool,
        actor_id: uuid.UUID,
    ) -> PointOfSale: ...

    # --- document types ---
    async def list_document_types(self, company_id: uuid.UUID) -> list[DocumentTypeSetting]: ...

    async def save_document_type(
        self,
        company_id: uuid.UUID,
        document_type: str,
        values: DocumentTypeValues,
        actor_id: uuid.UUID,
    ) -> DocumentTypeSetting: ...
