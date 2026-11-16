"""Emisor de DTE de demostración para Grupo Lorena, en modo simulado.

La casa matriz es el establecimiento M001 (fabricación de pan) y cada pastelería es una
sucursal S001 a S007 (venta al por menor de panadería) con su caja P001. Quedan
habilitados los documentos de una panadería: factura, crédito fiscal, notas de remisión,
crédito y débito; ninguno certificado, porque el modo es simulado.

Pasa por los casos de uso, así que respeta las mismas reglas que la pantalla, y se puede
ejecutar varias veces: solo crea lo que falta.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.fiscal import FiscalSettingsUseCases
from app.domain.entities.fiscal import (
    EstablishmentType,
    OperatingMode,
    PersonType,
    TaxpayerCategory,
    establishment_code,
)
from app.domain.ports.fiscal_repository import ProfileValues
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.organization import Branch, Company
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fiscal_repository import SqlAlchemyFiscalRepository
from sqlalchemy import select

from seed.seed_grupo_lorena import BRANCHES, COMPANY_ID, SUPER_ADMIN_USERNAME

PRODUCTION_ACTIVITY = "10712"  # Fabricación de pan, galletas y barquillos
RETAIL_ACTIVITY = "47215"  # Venta al por menor de productos de panadería, repostería y galletas
ENABLED_DOCUMENTS = ("01", "03", "04", "05", "06")
POINT_OF_SALE = ("P001", "Caja 1")


@dataclass(frozen=True, slots=True)
class EstablishmentSeed:
    branch_code: str | None  # None: la casa matriz, cuyo código de sucursal se genera
    establishment_type: EstablishmentType
    code: str
    activity: str


ESTABLISHMENTS: tuple[EstablishmentSeed, ...] = (
    EstablishmentSeed(None, EstablishmentType.HEADQUARTERS, "M001", PRODUCTION_ACTIVITY),
    *(
        EstablishmentSeed(
            branch.code,
            EstablishmentType.BRANCH,
            establishment_code(EstablishmentType.BRANCH, position),
            RETAIL_ACTIVITY,
        )
        for position, branch in enumerate(BRANCHES, start=1)
    ),
)


async def seed() -> bool:
    async with session_scope() as session:
        company = await session.get(Company, COMPANY_ID)
        actor = await session.scalar(select(User.id).where(User.username == SUPER_ADMIN_USERNAME))
        if company is None or actor is None:
            print("[seed] Fiscal: falta la empresa o el superadministrador; se reintenta después.")
            return False
        fiscal = FiscalSettingsUseCases(SqlAlchemyFiscalRepository(session))

        if not (await fiscal.get_profile(COMPANY_ID)).configured:
            await fiscal.update_profile(
                COMPANY_ID,
                ProfileValues(
                    taxpayer_category=TaxpayerCategory.MEDIUM,
                    person_type=PersonType.LEGAL,
                    operating_mode=OperatingMode.SIMULATED,
                    dte_email=company.email,
                    dte_phone=company.phone,
                ),
                actor,
            )

        activities = {a.code: a for a in await fiscal.list_activities(COMPANY_ID)}
        for code in (PRODUCTION_ACTIVITY, RETAIL_ACTIVITY):
            if code not in activities:
                activities[code] = await fiscal.add_activity(
                    COMPANY_ID, code, is_primary=code == PRODUCTION_ACTIVITY, actor_id=actor
                )

        branches = {
            (None if branch.is_headquarters else branch.code): branch.id
            for branch in (
                await session.scalars(
                    select(Branch).where(
                        Branch.company_id == COMPANY_ID, Branch.deleted_at.is_(None)
                    )
                )
            ).all()
        }
        existing = {e.branch_id: e for e in await fiscal.list_establishments(COMPANY_ID)}
        for item in ESTABLISHMENTS:
            branch_id = branches.get(item.branch_code)
            if branch_id is None:
                continue
            establishment = existing.get(branch_id) or await fiscal.create_establishment(
                COMPANY_ID,
                branch_id=branch_id,
                establishment_type=item.establishment_type,
                code=item.code,
                activity_id=activities[item.activity].id,
                actor_id=actor,
            )
            if not establishment.points_of_sale:
                await fiscal.create_point_of_sale(
                    COMPANY_ID,
                    establishment.id,
                    code=POINT_OF_SALE[0],
                    name=POINT_OF_SALE[1],
                    actor_id=actor,
                )

        saved = {d.document_type: d for d in await fiscal.list_document_types(COMPANY_ID)}
        for document_type in ENABLED_DOCUMENTS:
            if not saved[document_type].is_enabled:
                await fiscal.update_document_type(
                    COMPANY_ID,
                    document_type,
                    is_enabled=True,
                    certification_status=saved[document_type].certification_status,
                    notes=None,
                    actor_id=actor,
                )
    return True
