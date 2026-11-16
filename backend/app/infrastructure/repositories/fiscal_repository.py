"""SQLAlchemy implementation of the fiscal issuer repository.

Every query filters by company; catalogs are the only global data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal import (
    ACTIVITY_CATALOG,
    DOCUMENT_TYPES,
    BranchOption,
    CatalogItem,
    CertificationStatus,
    CompanyIdentity,
    DocumentTypeSetting,
    EconomicActivity,
    Establishment,
    EstablishmentAddress,
    EstablishmentType,
    FiscalProfile,
    IssuerFacts,
    OperatingMode,
    PersonType,
    PointOfSale,
    TaxpayerCategory,
    dte_nit,
    dte_nrc,
)
from app.domain.ports.fiscal_repository import (
    DocumentTypeValues,
    EstablishmentValues,
    ProfileValues,
)
from app.infrastructure.catalogs.hacienda_dte import CATALOGS
from app.infrastructure.models.fiscal import (
    CompanyDteDocumentTypeModel,
    CompanyEconomicActivityModel,
    CompanyFiscalProfileModel,
    FiscalEstablishmentModel,
    FiscalPointOfSaleModel,
    HaciendaCatalogItemModel,
)
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
)

_ACCENTED = "áéíóúüñ"
_PLAIN = "aeiouun"


def _fold(value: str) -> str:
    """Minúsculas sin acentos, igual que ``translate`` en la consulta."""
    return value.lower().translate(str.maketrans(_ACCENTED, _PLAIN))


def _now() -> datetime:
    return datetime.now(UTC)


def _catalog_item(row: HaciendaCatalogItemModel) -> CatalogItem:
    return CatalogItem(
        catalog_code=row.catalog_code, group_code=row.group_code, code=row.code, name=row.name
    )


def _point_of_sale(row: FiscalPointOfSaleModel) -> PointOfSale:
    return PointOfSale(
        id=row.id,
        establishment_id=row.establishment_id,
        code=row.code,
        name=row.name,
        is_active=row.is_active,
    )


class SqlAlchemyFiscalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- catalogs ---
    def catalog_titles(self) -> dict[str, str]:
        return {code: title for code, (title, _) in CATALOGS.items()}

    async def list_catalog(
        self, catalog_code: str, *, group_code: str | None, search: str | None, limit: int
    ) -> list[CatalogItem]:
        stmt = select(HaciendaCatalogItemModel).where(
            HaciendaCatalogItemModel.catalog_code == catalog_code,
            HaciendaCatalogItemModel.is_active.is_(True),
        )
        if group_code is not None:
            stmt = stmt.where(HaciendaCatalogItemModel.group_code == group_code)
        if search:
            pattern = f"%{_fold(search.strip())}%"
            folded_name = func.translate(
                func.lower(HaciendaCatalogItemModel.name), _ACCENTED, _PLAIN
            )
            stmt = stmt.where(
                HaciendaCatalogItemModel.code.ilike(pattern) | folded_name.like(pattern)
            )
        stmt = stmt.order_by(
            HaciendaCatalogItemModel.group_code, HaciendaCatalogItemModel.sort_order
        ).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_catalog_item(row) for row in rows]

    async def catalog_item(
        self, catalog_code: str, code: str, group_code: str = ""
    ) -> CatalogItem | None:
        row = await self._session.get(HaciendaCatalogItemModel, (catalog_code, group_code, code))
        return _catalog_item(row) if row is not None and row.is_active else None

    # --- profile ---
    async def company_identity(self, company_id: uuid.UUID) -> CompanyIdentity | None:
        company = await self._session.get(Company, company_id)
        if company is None or company.deleted_at is not None:
            return None
        return CompanyIdentity(
            name=company.name,
            commercial_name=company.commercial_name,
            nit=company.nit,
            nrc=company.nrc,
        )

    async def get_profile(self, company_id: uuid.UUID) -> FiscalProfile:
        row = await self._session.get(CompanyFiscalProfileModel, company_id)
        if row is None:
            return FiscalProfile(
                company_id=company_id,
                taxpayer_category=TaxpayerCategory.OTHER,
                person_type=PersonType.LEGAL,
                operating_mode=OperatingMode.SIMULATED,
                dte_email=None,
                dte_phone=None,
                configured=False,
            )
        return FiscalProfile(
            company_id=company_id,
            taxpayer_category=TaxpayerCategory(row.taxpayer_category),
            person_type=PersonType(row.person_type),
            operating_mode=OperatingMode(row.operating_mode),
            dte_email=row.dte_email,
            dte_phone=row.dte_phone,
            configured=True,
            updated_at=row.updated_at,
        )

    async def save_profile(
        self, company_id: uuid.UUID, values: ProfileValues, actor_id: uuid.UUID
    ) -> FiscalProfile:
        row = await self._session.get(CompanyFiscalProfileModel, company_id)
        if row is None:
            row = CompanyFiscalProfileModel(company_id=company_id)
            self._session.add(row)
        row.taxpayer_category = values.taxpayer_category.value
        row.person_type = values.person_type.value
        row.operating_mode = values.operating_mode.value
        row.dte_email = values.dte_email
        row.dte_phone = values.dte_phone
        row.updated_by = actor_id
        row.updated_at = _now()
        await self._session.flush()
        return await self.get_profile(company_id)

    async def issuer_facts(self, company_id: uuid.UUID) -> IssuerFacts:
        company = await self._session.get(Company, company_id)
        has_primary = await self._session.scalar(
            select(
                exists().where(
                    CompanyEconomicActivityModel.company_id == company_id,
                    CompanyEconomicActivityModel.is_primary.is_(True),
                )
            )
        )
        with_pos = await self._session.scalar(
            select(func.count(func.distinct(FiscalEstablishmentModel.id)))
            .join(
                FiscalPointOfSaleModel,
                (FiscalPointOfSaleModel.company_id == FiscalEstablishmentModel.company_id)
                & (FiscalPointOfSaleModel.establishment_id == FiscalEstablishmentModel.id),
            )
            .where(
                FiscalEstablishmentModel.company_id == company_id,
                FiscalEstablishmentModel.is_active.is_(True),
                FiscalPointOfSaleModel.is_active.is_(True),
            )
        )
        documents = (
            await self._session.execute(
                select(
                    CompanyDteDocumentTypeModel.document_type,
                    CompanyDteDocumentTypeModel.certification_status,
                ).where(
                    CompanyDteDocumentTypeModel.company_id == company_id,
                    CompanyDteDocumentTypeModel.is_enabled.is_(True),
                )
            )
        ).all()
        return IssuerFacts(
            has_nit=bool(company and dte_nit(company.nit)),
            has_nrc=bool(company and dte_nrc(company.nrc)),
            has_primary_activity=bool(has_primary),
            establishments_with_point_of_sale=int(with_pos or 0),
            enabled_documents=len(documents),
            enabled_uncertified_documents=tuple(
                sorted(
                    doc for doc, status in documents if status != CertificationStatus.APPROVED.value
                )
            ),
        )

    # --- economic activities ---
    async def list_activities(self, company_id: uuid.UUID) -> list[EconomicActivity]:
        stmt = (
            select(CompanyEconomicActivityModel, HaciendaCatalogItemModel.name)
            .outerjoin(
                HaciendaCatalogItemModel,
                (HaciendaCatalogItemModel.catalog_code == ACTIVITY_CATALOG)
                & (HaciendaCatalogItemModel.group_code == "")
                & (HaciendaCatalogItemModel.code == CompanyEconomicActivityModel.activity_code),
            )
            .where(CompanyEconomicActivityModel.company_id == company_id)
            .order_by(
                CompanyEconomicActivityModel.is_primary.desc(),
                CompanyEconomicActivityModel.activity_code,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            EconomicActivity(
                id=row.id,
                code=row.activity_code,
                description=name or "",
                is_primary=row.is_primary,
            )
            for row, name in rows
        ]

    async def get_activity(
        self, company_id: uuid.UUID, activity_id: uuid.UUID
    ) -> EconomicActivity | None:
        return next(
            (a for a in await self.list_activities(company_id) if a.id == activity_id), None
        )

    async def activity_code_exists(self, company_id: uuid.UUID, code: str) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        CompanyEconomicActivityModel.company_id == company_id,
                        CompanyEconomicActivityModel.activity_code == code,
                    )
                )
            )
        )

    async def add_activity(
        self, company_id: uuid.UUID, code: str, *, is_primary: bool, actor_id: uuid.UUID
    ) -> EconomicActivity:
        row = CompanyEconomicActivityModel(
            company_id=company_id, activity_code=code, is_primary=False, created_by=actor_id
        )
        self._session.add(row)
        await self._session.flush()
        if is_primary:
            await self.set_primary_activity(company_id, row.id)
        activity = await self.get_activity(company_id, row.id)
        assert activity is not None
        return activity

    async def set_primary_activity(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> None:
        # Unset first: the partial unique index allows a single primary per company.
        await self._session.execute(
            update(CompanyEconomicActivityModel)
            .where(
                CompanyEconomicActivityModel.company_id == company_id,
                CompanyEconomicActivityModel.is_primary.is_(True),
            )
            .values(is_primary=False, updated_at=_now())
        )
        await self._session.execute(
            update(CompanyEconomicActivityModel)
            .where(
                CompanyEconomicActivityModel.company_id == company_id,
                CompanyEconomicActivityModel.id == activity_id,
            )
            .values(is_primary=True, updated_at=_now())
        )
        await self._session.flush()

    async def activity_in_use(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        FiscalEstablishmentModel.company_id == company_id,
                        FiscalEstablishmentModel.activity_id == activity_id,
                    )
                )
            )
        )

    async def delete_activity(self, company_id: uuid.UUID, activity_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(CompanyEconomicActivityModel).where(
                CompanyEconomicActivityModel.company_id == company_id,
                CompanyEconomicActivityModel.id == activity_id,
            )
        )
        await self._session.flush()

    # --- establishments ---
    async def list_establishments(self, company_id: uuid.UUID) -> list[Establishment]:
        return await self._establishments(company_id)

    async def get_establishment(
        self, company_id: uuid.UUID, establishment_id: uuid.UUID
    ) -> Establishment | None:
        found = await self._establishments(company_id, establishment_id)
        return found[0] if found else None

    async def _establishments(
        self, company_id: uuid.UUID, establishment_id: uuid.UUID | None = None
    ) -> list[Establishment]:
        stmt = (
            select(
                FiscalEstablishmentModel,
                Branch,
                GeographicDepartment,
                Municipality,
                District,
                CompanyEconomicActivityModel.activity_code,
            )
            .join(
                Branch,
                (Branch.id == FiscalEstablishmentModel.branch_id)
                & (Branch.company_id == FiscalEstablishmentModel.company_id),
            )
            .join(GeographicDepartment, GeographicDepartment.id == Branch.department_id)
            .join(Municipality, Municipality.id == Branch.municipality_id)
            .join(District, District.id == Branch.district_id)
            .outerjoin(
                CompanyEconomicActivityModel,
                (CompanyEconomicActivityModel.company_id == FiscalEstablishmentModel.company_id)
                & (CompanyEconomicActivityModel.id == FiscalEstablishmentModel.activity_id),
            )
            .where(FiscalEstablishmentModel.company_id == company_id)
            .order_by(FiscalEstablishmentModel.code)
        )
        if establishment_id is not None:
            stmt = stmt.where(FiscalEstablishmentModel.id == establishment_id)
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return []
        ids = [row[0].id for row in rows]
        points = (
            (
                await self._session.execute(
                    select(FiscalPointOfSaleModel)
                    .where(
                        FiscalPointOfSaleModel.company_id == company_id,
                        FiscalPointOfSaleModel.establishment_id.in_(ids),
                    )
                    .order_by(FiscalPointOfSaleModel.code)
                )
            )
            .scalars()
            .all()
        )
        by_establishment: dict[uuid.UUID, list[PointOfSale]] = {}
        for point in points:
            by_establishment.setdefault(point.establishment_id, []).append(_point_of_sale(point))
        return [
            Establishment(
                id=est.id,
                branch_id=branch.id,
                branch_name=branch.name,
                establishment_type=EstablishmentType(est.establishment_type),
                code=est.code,
                activity_id=est.activity_id,
                activity_code=activity_code,
                is_active=est.is_active,
                address=EstablishmentAddress(
                    department=department.name,
                    department_code=department.hacienda_code,
                    municipality=municipality.name,
                    municipality_code=municipality.hacienda_code,
                    district=district.name,
                    district_code=district.hacienda_code,
                    complement=branch.address,
                ),
                phone=branch.phone,
                email=branch.email,
                points_of_sale=tuple(by_establishment.get(est.id, ())),
            )
            for est, branch, department, municipality, district, activity_code in rows
        ]

    async def branch_options(self, company_id: uuid.UUID) -> list[BranchOption]:
        rows = (
            await self._session.execute(
                select(Branch, FiscalEstablishmentModel.id)
                .outerjoin(
                    FiscalEstablishmentModel,
                    (FiscalEstablishmentModel.company_id == Branch.company_id)
                    & (FiscalEstablishmentModel.branch_id == Branch.id),
                )
                .where(Branch.company_id == company_id, Branch.deleted_at.is_(None))
                .order_by(Branch.is_headquarters.desc(), Branch.name)
            )
        ).all()
        return [
            BranchOption(
                id=branch.id,
                name=branch.name,
                code=branch.code,
                is_headquarters=branch.is_headquarters,
                establishment_id=establishment_id,
            )
            for branch, establishment_id in rows
        ]

    async def branch_name(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> str | None:
        name: str | None = await self._session.scalar(
            select(Branch.name).where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
                Branch.deleted_at.is_(None),
            )
        )
        return name

    async def branch_has_establishment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(FiscalEstablishmentModel.id).where(
            FiscalEstablishmentModel.company_id == company_id,
            FiscalEstablishmentModel.branch_id == branch_id,
        )
        if exclude_id is not None:
            stmt = stmt.where(FiscalEstablishmentModel.id != exclude_id)
        return bool(await self._session.scalar(select(exists(stmt))))

    async def establishment_code_taken(
        self, company_id: uuid.UUID, code: str, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(FiscalEstablishmentModel.id).where(
            FiscalEstablishmentModel.company_id == company_id,
            FiscalEstablishmentModel.code == code,
        )
        if exclude_id is not None:
            stmt = stmt.where(FiscalEstablishmentModel.id != exclude_id)
        return bool(await self._session.scalar(select(exists(stmt))))

    async def create_establishment(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        values: EstablishmentValues,
        actor_id: uuid.UUID,
    ) -> Establishment:
        row = FiscalEstablishmentModel(
            company_id=company_id,
            branch_id=branch_id,
            establishment_type=values.establishment_type.value,
            code=values.code,
            activity_id=values.activity_id,
            is_active=values.is_active,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        created = await self.get_establishment(company_id, row.id)
        assert created is not None
        return created

    async def update_establishment(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        values: EstablishmentValues,
        actor_id: uuid.UUID,
    ) -> Establishment:
        await self._session.execute(
            update(FiscalEstablishmentModel)
            .where(
                FiscalEstablishmentModel.company_id == company_id,
                FiscalEstablishmentModel.id == establishment_id,
            )
            .values(
                establishment_type=values.establishment_type.value,
                code=values.code,
                activity_id=values.activity_id,
                is_active=values.is_active,
                updated_by=actor_id,
                updated_at=_now(),
            )
        )
        await self._session.flush()
        updated = await self.get_establishment(company_id, establishment_id)
        assert updated is not None
        return updated

    # --- points of sale ---
    async def get_point_of_sale(
        self, company_id: uuid.UUID, point_of_sale_id: uuid.UUID
    ) -> PointOfSale | None:
        row = await self._session.scalar(
            select(FiscalPointOfSaleModel).where(
                FiscalPointOfSaleModel.company_id == company_id,
                FiscalPointOfSaleModel.id == point_of_sale_id,
            )
        )
        return _point_of_sale(row) if row is not None else None

    async def point_of_sale_code_taken(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        code: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = select(FiscalPointOfSaleModel.id).where(
            FiscalPointOfSaleModel.company_id == company_id,
            FiscalPointOfSaleModel.establishment_id == establishment_id,
            FiscalPointOfSaleModel.code == code,
        )
        if exclude_id is not None:
            stmt = stmt.where(FiscalPointOfSaleModel.id != exclude_id)
        return bool(await self._session.scalar(select(exists(stmt))))

    async def create_point_of_sale(
        self,
        company_id: uuid.UUID,
        establishment_id: uuid.UUID,
        code: str,
        name: str,
        actor_id: uuid.UUID,
    ) -> PointOfSale:
        row = FiscalPointOfSaleModel(
            company_id=company_id,
            establishment_id=establishment_id,
            code=code,
            name=name,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        return _point_of_sale(row)

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
        row = await self._session.scalar(
            select(FiscalPointOfSaleModel).where(
                FiscalPointOfSaleModel.company_id == company_id,
                FiscalPointOfSaleModel.id == point_of_sale_id,
            )
        )
        assert row is not None
        row.code = code
        row.name = name
        row.is_active = is_active
        row.updated_by = actor_id
        row.updated_at = _now()
        await self._session.flush()
        return _point_of_sale(row)

    # --- document types ---
    async def list_document_types(self, company_id: uuid.UUID) -> list[DocumentTypeSetting]:
        rows = (
            (
                await self._session.execute(
                    select(CompanyDteDocumentTypeModel).where(
                        CompanyDteDocumentTypeModel.company_id == company_id
                    )
                )
            )
            .scalars()
            .all()
        )
        saved = {row.document_type: row for row in rows}
        settings: list[DocumentTypeSetting] = []
        for code, name in DOCUMENT_TYPES.items():
            row = saved.get(code)
            settings.append(
                DocumentTypeSetting(
                    document_type=code,
                    name=name,
                    is_enabled=bool(row and row.is_enabled),
                    certification_status=CertificationStatus(
                        row.certification_status if row else CertificationStatus.PENDING
                    ),
                    certified_at=row.certified_at if row else None,
                    notes=row.notes if row else None,
                )
            )
        return settings

    async def save_document_type(
        self,
        company_id: uuid.UUID,
        document_type: str,
        values: DocumentTypeValues,
        actor_id: uuid.UUID,
    ) -> DocumentTypeSetting:
        row = await self._session.get(CompanyDteDocumentTypeModel, (company_id, document_type))
        if row is None:
            row = CompanyDteDocumentTypeModel(company_id=company_id, document_type=document_type)
            self._session.add(row)
        approved = values.certification_status == CertificationStatus.APPROVED
        if approved and row.certified_at is None:
            row.certified_at = _now()
        elif not approved:
            row.certified_at = None
        row.is_enabled = values.is_enabled
        row.certification_status = values.certification_status.value
        row.notes = values.notes
        row.updated_by = actor_id
        row.updated_at = _now()
        await self._session.flush()
        return DocumentTypeSetting(
            document_type=document_type,
            name=DOCUMENT_TYPES[document_type],
            is_enabled=row.is_enabled,
            certification_status=CertificationStatus(row.certification_status),
            certified_at=row.certified_at,
            notes=row.notes,
        )
