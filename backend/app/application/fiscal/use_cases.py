"""Casos de uso de la configuración fiscal del emisor.

Una empresa en producción nunca queda en un estado desde el que no pueda emitir: cada
cambio se valida contra los requisitos de producción antes de confirmarse, y si los rompe
la petición falla completa (la sesión se revierte).
"""

from __future__ import annotations

import uuid

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.fiscal import (
    ACTIVITY_CATALOG,
    BranchOption,
    CatalogItem,
    CertificationStatus,
    CompanyIdentity,
    DocumentTypeSetting,
    EconomicActivity,
    Establishment,
    EstablishmentType,
    FiscalProfile,
    OperatingMode,
    PointOfSale,
    production_blockers,
    require_can_enable,
    require_document_type,
    require_mode_change,
    validate_activity_code,
    validate_establishment_code,
    validate_point_of_sale_code,
)
from app.domain.ports.fiscal_repository import (
    DocumentTypeValues,
    EstablishmentValues,
    FiscalRepository,
    ProfileValues,
)

MAX_CATALOG_ROWS = 1000


class FiscalSettingsUseCases:
    def __init__(self, repository: FiscalRepository) -> None:
        self._repo = repository

    # --- catalogs ---
    def catalog_titles(self) -> dict[str, str]:
        return self._repo.catalog_titles()

    async def list_catalog(
        self, catalog_code: str, *, group_code: str | None, search: str | None, limit: int
    ) -> list[CatalogItem]:
        if catalog_code not in self._repo.catalog_titles():
            raise NotFoundError(
                "Ese catálogo de Hacienda no existe.", code="fiscal_catalog_unknown"
            )
        return await self._repo.list_catalog(
            catalog_code,
            group_code=group_code,
            search=search,
            limit=max(1, min(limit, MAX_CATALOG_ROWS)),
        )

    # --- profile ---
    async def company_identity(self, company_id: uuid.UUID) -> CompanyIdentity:
        identity = await self._repo.company_identity(company_id)
        if identity is None:
            raise NotFoundError("No se encontró la empresa.", code="fiscal_company_not_found")
        return identity

    async def get_profile(self, company_id: uuid.UUID) -> FiscalProfile:
        return await self._repo.get_profile(company_id)

    async def production_blockers(self, company_id: uuid.UUID) -> list[str]:
        return production_blockers(await self._repo.issuer_facts(company_id))

    async def update_profile(
        self, company_id: uuid.UUID, values: ProfileValues, actor_id: uuid.UUID
    ) -> FiscalProfile:
        require_mode_change(values.operating_mode, await self._repo.issuer_facts(company_id))
        return await self._repo.save_profile(company_id, values, actor_id)

    async def _keep_production_ready(self, company_id: uuid.UUID) -> None:
        profile = await self._repo.get_profile(company_id)
        if profile.operating_mode != OperatingMode.PRODUCTION:
            return
        reasons = production_blockers(await self._repo.issuer_facts(company_id))
        if reasons:
            raise BusinessRuleError(
                "La empresa emite en producción y este cambio la dejaría sin poder emitir: "
                + " ".join(reasons),
                code="fiscal_production_would_break",
            )

    # --- economic activities ---
    async def list_activities(self, company_id: uuid.UUID) -> list[EconomicActivity]:
        return await self._repo.list_activities(company_id)

    async def add_activity(
        self, company_id: uuid.UUID, code: str, *, is_primary: bool, actor_id: uuid.UUID
    ) -> EconomicActivity:
        code = validate_activity_code(code)
        if await self._repo.catalog_item(ACTIVITY_CATALOG, code) is None:
            raise BusinessRuleError(
                "Ese código no está en el catálogo de actividades económicas de Hacienda.",
                code="fiscal_activity_unknown",
            )
        if await self._repo.activity_code_exists(company_id, code):
            raise ConflictError(
                "La empresa ya tiene registrada esa actividad económica.",
                code="fiscal_activity_duplicate",
            )
        first = not await self._repo.list_activities(company_id)
        return await self._repo.add_activity(
            company_id, code, is_primary=is_primary or first, actor_id=actor_id
        )

    async def _activity_or_404(
        self, company_id: uuid.UUID, activity_id: uuid.UUID
    ) -> EconomicActivity:
        activity = await self._repo.get_activity(company_id, activity_id)
        if activity is None:
            raise NotFoundError(
                "No se encontró esa actividad económica en la empresa.",
                code="fiscal_activity_not_found",
            )
        return activity

    async def set_primary_activity(
        self, company_id: uuid.UUID, activity_id: uuid.UUID
    ) -> EconomicActivity:
        await self._activity_or_404(company_id, activity_id)
        await self._repo.set_primary_activity(company_id, activity_id)
        return await self._activity_or_404(company_id, activity_id)

    async def delete_activity(
        self, company_id: uuid.UUID, activity_id: uuid.UUID
    ) -> EconomicActivity:
        activity = await self._activity_or_404(company_id, activity_id)
        if await self._repo.activity_in_use(company_id, activity_id):
            raise ConflictError(
                "Un establecimiento usa esta actividad; cámbiala allí antes de quitarla.",
                code="fiscal_activity_in_use",
            )
        await self._repo.delete_activity(company_id, activity_id)
        await self._keep_production_ready(company_id)
        return activity

    # --- establishments ---
    async def list_establishments(self, company_id: uuid.UUID) -> list[Establishment]:
        return await self._repo.list_establishments(company_id)

    async def branch_options(self, company_id: uuid.UUID) -> list[BranchOption]:
        return await self._repo.branch_options(company_id)

    async def _establishment_or_404(
        self, company_id: uuid.UUID, establishment_id: uuid.UUID
    ) -> Establishment:
        establishment = await self._repo.get_establishment(company_id, establishment_id)
        if establishment is None:
            raise NotFoundError(
                "No se encontró ese establecimiento en la empresa.",
                code="fiscal_establishment_not_found",
            )
        return establishment

    async def get_establishment(
        self, company_id: uuid.UUID, establishment_id: uuid.UUID
    ) -> Establishment:
        return await self._establishment_or_404(company_id, establishment_id)

    async def _checked_values(
        self,
        company_id: uuid.UUID,
        establishment_type: EstablishmentType,
        code: str,
        activity_id: uuid.UUID | None,
        is_active: bool,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> EstablishmentValues:
        code = validate_establishment_code(establishment_type, code)
        if await self._repo.establishment_code_taken(company_id, code, exclude_id=exclude_id):
            raise ConflictError(
                f"Otro establecimiento de la empresa ya usa el código {code}.",
                code="fiscal_establishment_code_duplicate",
            )
        if activity_id is not None:
            await self._activity_or_404(company_id, activity_id)
        return EstablishmentValues(
            establishment_type=establishment_type,
            code=code,
            activity_id=activity_id,
            is_active=is_active,
        )

    async def create_establishment(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID,
        establishment_type: EstablishmentType,
        code: str,
        activity_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> Establishment:
        if await self._repo.branch_name(company_id, branch_id) is None:
            raise NotFoundError(
                "No se encontró esa sucursal en la empresa.", code="fiscal_branch_not_found"
            )
        if await self._repo.branch_has_establishment(company_id, branch_id):
            raise ConflictError(
                "Esa sucursal ya está registrada como establecimiento.",
                code="fiscal_branch_already_establishment",
            )
        values = await self._checked_values(company_id, establishment_type, code, activity_id, True)
        return await self._repo.create_establishment(company_id, branch_id, values, actor_id)

    async def update_establishment(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        *,
        establishment_type: EstablishmentType,
        code: str,
        activity_id: uuid.UUID | None,
        is_active: bool,
        actor_id: uuid.UUID,
    ) -> Establishment:
        await self._establishment_or_404(company_id, establishment_id)
        values = await self._checked_values(
            company_id,
            establishment_type,
            code,
            activity_id,
            is_active,
            exclude_id=establishment_id,
        )
        updated = await self._repo.update_establishment(
            company_id, establishment_id, values, actor_id
        )
        await self._keep_production_ready(company_id)
        return updated

    # --- points of sale ---
    async def _point_of_sale_or_404(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSale:
        point = await self._repo.get_point_of_sale(company_id, point_of_sale_id)
        if point is None:
            raise NotFoundError(
                "No se encontró ese punto de venta en la empresa.",
                code="fiscal_point_of_sale_not_found",
            )
        return point

    async def get_point_of_sale(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSale:
        return await self._point_of_sale_or_404(company_id, point_of_sale_id)

    async def _require_free_point_code(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        code: str,
        exclude_id: uuid.UUID | None = None,
    ) -> str:
        code = validate_point_of_sale_code(code)
        if await self._repo.point_of_sale_code_taken(
            company_id, establishment_id, code, exclude_id=exclude_id
        ):
            raise ConflictError(
                f"El establecimiento ya tiene un punto de venta con el código {code}.",
                code="fiscal_point_of_sale_code_duplicate",
            )
        return code

    async def create_point_of_sale(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        *,
        code: str,
        name: str,
        actor_id: uuid.UUID,
    ) -> PointOfSale:
        await self._establishment_or_404(company_id, establishment_id)
        code = await self._require_free_point_code(company_id, establishment_id, code)
        return await self._repo.create_point_of_sale(
            company_id, establishment_id, code, name.strip(), actor_id
        )

    async def update_point_of_sale(
        self,
        company_id: uuid.UUID,
        point_of_sale_id: uuid.UUID,
        *,
        code: str,
        name: str,
        is_active: bool,
        actor_id: uuid.UUID,
    ) -> PointOfSale:
        current = await self._point_of_sale_or_404(company_id, point_of_sale_id)
        code = await self._require_free_point_code(
            company_id, current.establishment_id, code, exclude_id=point_of_sale_id
        )
        updated = await self._repo.update_point_of_sale(
            company_id,
            point_of_sale_id,
            code=code,
            name=name.strip(),
            is_active=is_active,
            actor_id=actor_id,
        )
        await self._keep_production_ready(company_id)
        return updated

    # --- document types ---
    async def list_document_types(self, company_id: uuid.UUID) -> list[DocumentTypeSetting]:
        return await self._repo.list_document_types(company_id)

    async def update_document_type(
        self,
        company_id: uuid.UUID,
        document_type: str,
        *,
        is_enabled: bool,
        certification_status: CertificationStatus,
        notes: str | None,
        actor_id: uuid.UUID,
    ) -> DocumentTypeSetting:
        require_document_type(document_type)
        if is_enabled:
            profile = await self._repo.get_profile(company_id)
            require_can_enable(profile.operating_mode, document_type, certification_status)
        saved = await self._repo.save_document_type(
            company_id,
            document_type,
            DocumentTypeValues(
                is_enabled=is_enabled,
                certification_status=certification_status,
                notes=(notes or "").strip() or None,
            ),
            actor_id,
        )
        await self._keep_production_ready(company_id)
        return saved
