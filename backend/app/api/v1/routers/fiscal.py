"""Configuración fiscal del emisor de DTE: catálogos de Hacienda, perfil, actividades,
establecimientos, puntos de venta y documentos habilitados.

Todo se resuelve con la empresa del encabezado ``X-Company-ID``; una empresa nunca lee ni
escribe la configuración de otra.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_company_email_settings_use_cases,
    get_fiscal_settings_use_cases,
    get_hacienda_credentials_use_cases,
    require_permission,
)
from app.api.v1.schemas.fiscal import (
    BranchOptionOut,
    CatalogItemOut,
    CatalogSummaryOut,
    DocumentTypeIn,
    DocumentTypeOut,
    EconomicActivityIn,
    EconomicActivityOut,
    EmailSettingsIn,
    EmailSettingsOut,
    EmailTestIn,
    EmailTestOut,
    EstablishmentAddressOut,
    EstablishmentIn,
    EstablishmentOut,
    EstablishmentUpdate,
    FiscalProfileIn,
    FiscalProfileOut,
    HaciendaCredentialsIn,
    HaciendaCredentialsOut,
    HaciendaTestOut,
    PointOfSaleIn,
    PointOfSaleOut,
    PointOfSaleUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.fiscal import FiscalSettingsUseCases
from app.application.fiscal.email_settings import CompanyEmailSettingsUseCases
from app.application.fiscal.hacienda_credentials import HaciendaCredentialsUseCases
from app.core.config import settings as app_settings
from app.core.exceptions import BusinessRuleError
from app.domain.entities.company_email import EmailSettings, EmailSettingsInput
from app.domain.entities.fiscal import (
    DocumentTypeSetting,
    EconomicActivity,
    Establishment,
    FiscalProfile,
    PointOfSale,
)
from app.domain.entities.hacienda_credentials import HaciendaCredentials
from app.domain.ports.fiscal_repository import ProfileValues

router = APIRouter(prefix="/fiscal", tags=["fiscal"])

UseCases = Annotated[FiscalSettingsUseCases, Depends(get_fiscal_settings_use_cases)]
HaciendaUseCases = Annotated[
    HaciendaCredentialsUseCases, Depends(get_hacienda_credentials_use_cases)
]
EmailSettingsUseCases = Annotated[
    CompanyEmailSettingsUseCases, Depends(get_company_email_settings_use_cases)
]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("fiscal_settings:read"))]
_MANAGE = [Depends(require_permission("fiscal_settings:manage"))]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _state(entity: object | None) -> dict[str, Any] | None:
    return _jsonable(asdict(entity)) if entity is not None else None  # type: ignore[call-overload]


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    before: object | None = None,
    after: object | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=_state(before),
        after_state=_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _activity_out(item: EconomicActivity) -> EconomicActivityOut:
    return EconomicActivityOut(
        id=item.id, code=item.code, description=item.description, is_primary=item.is_primary
    )


def _point_out(item: PointOfSale) -> PointOfSaleOut:
    return PointOfSaleOut(
        id=item.id,
        establishment_id=item.establishment_id,
        code=item.code,
        name=item.name,
        is_active=item.is_active,
    )


def _establishment_out(item: Establishment) -> EstablishmentOut:
    address = item.address
    return EstablishmentOut(
        id=item.id,
        branch_id=item.branch_id,
        branch_name=item.branch_name,
        establishment_type=item.establishment_type,
        code=item.code,
        activity_id=item.activity_id,
        activity_code=item.activity_code,
        is_active=item.is_active,
        address=EstablishmentAddressOut(
            department=address.department,
            department_code=address.department_code,
            municipality=address.municipality,
            municipality_code=address.municipality_code,
            district=address.district,
            district_code=address.district_code,
            complement=address.complement,
            complete=address.complete,
        ),
        phone=item.phone,
        email=item.email,
        points_of_sale=[_point_out(p) for p in item.points_of_sale],
    )


def _document_out(item: DocumentTypeSetting) -> DocumentTypeOut:
    return DocumentTypeOut(
        document_type=item.document_type,
        name=item.name,
        is_enabled=item.is_enabled,
        certification_status=item.certification_status,
        certified_at=item.certified_at,
        notes=item.notes,
    )


async def _profile_out(
    use_cases: FiscalSettingsUseCases, company_id: uuid.UUID, profile: FiscalProfile
) -> FiscalProfileOut:
    identity = await use_cases.company_identity(company_id)
    return FiscalProfileOut(
        company_id=company_id,
        company_name=identity.name,
        commercial_name=identity.commercial_name,
        nit=identity.nit,
        nrc=identity.nrc,
        taxpayer_category=profile.taxpayer_category,
        person_type=profile.person_type,
        operating_mode=profile.operating_mode,
        dte_email=profile.dte_email,
        dte_phone=profile.dte_phone,
        configured=profile.configured,
        updated_at=profile.updated_at,
        production_blockers=await use_cases.production_blockers(company_id),
    )


# --- catalogs ---
@router.get(
    "/catalogs",
    response_model=list[CatalogSummaryOut],
    summary="Listar los catálogos de Hacienda",
    dependencies=[Depends(require_permission("reference_data:read"))],
)
async def list_catalogs(use_cases: UseCases) -> list[CatalogSummaryOut]:
    return [
        CatalogSummaryOut(code=code, title=title)
        for code, title in sorted(use_cases.catalog_titles().items())
    ]


@router.get(
    "/catalogs/{catalog_code}",
    response_model=list[CatalogItemOut],
    summary="Consultar un catálogo de Hacienda",
    dependencies=[Depends(require_permission("reference_data:read"))],
)
async def list_catalog_items(
    catalog_code: str,
    use_cases: UseCases,
    group: Annotated[str | None, Query(max_length=16)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> list[CatalogItemOut]:
    items = await use_cases.list_catalog(
        catalog_code.upper(), group_code=group, search=search, limit=limit
    )
    return [CatalogItemOut(group_code=i.group_code, code=i.code, name=i.name) for i in items]


# --- profile ---
@router.get(
    "/profile", response_model=FiscalProfileOut, summary="Perfil de emisor", dependencies=_READ
)
async def get_profile(request: Request, use_cases: UseCases) -> FiscalProfileOut:
    company_id = request_company_id(request)
    return await _profile_out(use_cases, company_id, await use_cases.get_profile(company_id))


@router.put(
    "/profile",
    response_model=FiscalProfileOut,
    summary="Guardar el perfil de emisor",
    dependencies=_MANAGE,
)
async def update_profile(
    body: FiscalProfileIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> FiscalProfileOut:
    company_id = request_company_id(request)
    before = await use_cases.get_profile(company_id)
    saved = await use_cases.update_profile(
        company_id,
        ProfileValues(
            taxpayer_category=body.taxpayer_category,
            person_type=body.person_type,
            operating_mode=body.operating_mode,
            dte_email=str(body.dte_email) if body.dte_email else None,
            dte_phone=body.dte_phone,
        ),
        current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE" if before.configured else "CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_profile",
        resource_id=str(company_id),
        before=before if before.configured else None,
        after=saved,
    )
    return await _profile_out(use_cases, company_id, saved)


# --- activities ---
@router.get(
    "/activities",
    response_model=list[EconomicActivityOut],
    summary="Actividades económicas de la empresa",
    dependencies=_READ,
)
async def list_activities(request: Request, use_cases: UseCases) -> list[EconomicActivityOut]:
    items = await use_cases.list_activities(request_company_id(request))
    return [_activity_out(item) for item in items]


@router.post(
    "/activities",
    response_model=EconomicActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una actividad económica",
    dependencies=_MANAGE,
)
async def add_activity(
    body: EconomicActivityIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> EconomicActivityOut:
    company_id = request_company_id(request)
    item = await use_cases.add_activity(
        company_id, body.code, is_primary=body.is_primary, actor_id=current.id
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_activity",
        resource_id=str(item.id),
        after=item,
    )
    return _activity_out(item)


@router.post(
    "/activities/{activity_id}/primary",
    response_model=EconomicActivityOut,
    summary="Marcar la actividad principal",
    dependencies=_MANAGE,
)
async def set_primary_activity(
    activity_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> EconomicActivityOut:
    company_id = request_company_id(request)
    item = await use_cases.set_primary_activity(company_id, activity_id)
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_activity",
        resource_id=str(item.id),
        after=item,
    )
    return _activity_out(item)


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar una actividad económica",
    dependencies=_MANAGE,
)
async def delete_activity(
    activity_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> None:
    company_id = request_company_id(request)
    removed = await use_cases.delete_activity(company_id, activity_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_activity",
        resource_id=str(activity_id),
        before=removed,
    )


# --- establishments ---
@router.get(
    "/branch-options",
    response_model=list[BranchOptionOut],
    summary="Sucursales y si ya son establecimiento",
    dependencies=_READ,
)
async def list_branch_options(request: Request, use_cases: UseCases) -> list[BranchOptionOut]:
    items = await use_cases.branch_options(request_company_id(request))
    return [BranchOptionOut(**asdict(item)) for item in items]


@router.get(
    "/establishments",
    response_model=list[EstablishmentOut],
    summary="Establecimientos y sus puntos de venta",
    dependencies=_READ,
)
async def list_establishments(request: Request, use_cases: UseCases) -> list[EstablishmentOut]:
    items = await use_cases.list_establishments(request_company_id(request))
    return [_establishment_out(item) for item in items]


@router.post(
    "/establishments",
    response_model=EstablishmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una sucursal como establecimiento",
    dependencies=_MANAGE,
)
async def create_establishment(
    body: EstablishmentIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> EstablishmentOut:
    company_id = request_company_id(request)
    item = await use_cases.create_establishment(
        company_id,
        branch_id=body.branch_id,
        establishment_type=body.establishment_type,
        code=body.code,
        activity_id=body.activity_id,
        actor_id=current.id,
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_establishment",
        resource_id=str(item.id),
        after=item,
    )
    return _establishment_out(item)


@router.get(
    "/establishments/{establishment_id}",
    response_model=EstablishmentOut,
    summary="Detalle de un establecimiento",
    dependencies=_READ,
)
async def get_establishment(
    establishment_id: uuid.UUID, request: Request, use_cases: UseCases
) -> EstablishmentOut:
    item = await use_cases.get_establishment(request_company_id(request), establishment_id)
    return _establishment_out(item)


@router.patch(
    "/establishments/{establishment_id}",
    response_model=EstablishmentOut,
    summary="Editar un establecimiento",
    dependencies=_MANAGE,
)
async def update_establishment(
    establishment_id: uuid.UUID,
    body: EstablishmentUpdate,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> EstablishmentOut:
    company_id = request_company_id(request)
    before = await use_cases.get_establishment(company_id, establishment_id)
    item = await use_cases.update_establishment(
        company_id,
        establishment_id,
        establishment_type=body.establishment_type,
        code=body.code,
        activity_id=body.activity_id,
        is_active=body.is_active,
        actor_id=current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_establishment",
        resource_id=str(item.id),
        before=before,
        after=item,
    )
    return _establishment_out(item)


@router.post(
    "/establishments/{establishment_id}/points-of-sale",
    response_model=PointOfSaleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un punto de venta",
    dependencies=_MANAGE,
)
async def create_point_of_sale(
    establishment_id: uuid.UUID,
    body: PointOfSaleIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> PointOfSaleOut:
    company_id = request_company_id(request)
    item = await use_cases.create_point_of_sale(
        company_id, establishment_id, code=body.code, name=body.name, actor_id=current.id
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_point_of_sale",
        resource_id=str(item.id),
        after=item,
    )
    return _point_out(item)


@router.patch(
    "/points-of-sale/{point_of_sale_id}",
    response_model=PointOfSaleOut,
    summary="Editar un punto de venta",
    dependencies=_MANAGE,
)
async def update_point_of_sale(
    point_of_sale_id: uuid.UUID,
    body: PointOfSaleUpdate,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> PointOfSaleOut:
    company_id = request_company_id(request)
    before = await use_cases.get_point_of_sale(company_id, point_of_sale_id)
    item = await use_cases.update_point_of_sale(
        company_id,
        point_of_sale_id,
        code=body.code,
        name=body.name,
        is_active=body.is_active,
        actor_id=current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_point_of_sale",
        resource_id=str(item.id),
        before=before,
        after=item,
    )
    return _point_out(item)


# --- document types ---
@router.get(
    "/document-types",
    response_model=list[DocumentTypeOut],
    summary="Tipos de documento y su habilitación",
    dependencies=_READ,
)
async def list_document_types(request: Request, use_cases: UseCases) -> list[DocumentTypeOut]:
    items = await use_cases.list_document_types(request_company_id(request))
    return [_document_out(item) for item in items]


@router.put(
    "/document-types/{document_type}",
    response_model=DocumentTypeOut,
    summary="Habilitar un tipo de documento o cambiar su certificación",
    dependencies=_MANAGE,
)
async def update_document_type(
    document_type: str,
    body: DocumentTypeIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> DocumentTypeOut:
    company_id = request_company_id(request)
    before = next(
        (
            d
            for d in await use_cases.list_document_types(company_id)
            if d.document_type == document_type
        ),
        None,
    )
    item = await use_cases.update_document_type(
        company_id,
        document_type,
        is_enabled=body.is_enabled,
        certification_status=body.certification_status,
        notes=body.notes,
        actor_id=current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_document_type",
        resource_id=document_type,
        before=before,
        after=item,
    )
    return _document_out(item)


# --- correo saliente propio (bloque V3c) ---


def _email_settings_out(settings_: EmailSettings | None) -> EmailSettingsOut:
    fallback = bool(app_settings.SMTP_HOST)
    if settings_ is None:
        return EmailSettingsOut(configured=False, server_fallback=fallback)
    return EmailSettingsOut(
        configured=True,
        host=settings_.host,
        port=settings_.port,
        security=settings_.security,
        username=settings_.username,
        has_password=settings_.has_password,
        from_address=settings_.from_address,
        from_name=settings_.from_name,
        is_enabled=settings_.is_enabled,
        last_test_at=settings_.last_test_at,
        last_test_ok=settings_.last_test_ok,
        last_test_error=settings_.last_test_error,
        server_fallback=fallback,
    )


@router.get(
    "/email-settings",
    response_model=EmailSettingsOut,
    summary="Correo saliente propio de la empresa",
    dependencies=_READ,
)
async def get_email_settings(request: Request, email: EmailSettingsUseCases) -> EmailSettingsOut:
    return _email_settings_out(await email.get(request_company_id(request)))


@router.put(
    "/email-settings",
    response_model=EmailSettingsOut,
    summary="Guardar el SMTP propio de la empresa",
    dependencies=_MANAGE,
)
async def save_email_settings(
    body: EmailSettingsIn,
    request: Request,
    current: CurrentUser,
    email: EmailSettingsUseCases,
    audit: Audit,
) -> EmailSettingsOut:
    company_id = request_company_id(request)
    before, saved = await email.save(
        company_id,
        EmailSettingsInput(
            host=body.host,
            port=body.port,
            security=body.security,
            username=body.username,
            password=body.password,
            from_address=body.from_address,
            from_name=body.from_name,
            is_enabled=body.is_enabled,
        ),
        current.id,
    )
    # La contraseña no entra a la bitácora: EmailSettings solo dice si existe.
    await _record(
        audit,
        request,
        action="UPDATE" if before else "CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="company_email_settings",
        resource_id=str(company_id),
        before=before,
        after=saved,
    )
    return _email_settings_out(saved)


@router.delete(
    "/email-settings",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar el SMTP propio de la empresa",
    dependencies=_MANAGE,
)
async def delete_email_settings(
    request: Request, current: CurrentUser, email: EmailSettingsUseCases, audit: Audit
) -> None:
    company_id = request_company_id(request)
    before = await email.get(company_id)
    if before is None:
        return
    await email.remove(company_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        company_id=company_id,
        resource_type="company_email_settings",
        resource_id=str(company_id),
        before=before,
    )


@router.post(
    "/email-settings/test",
    response_model=EmailTestOut,
    summary="Enviar un correo de prueba con el SMTP de la empresa",
    dependencies=_MANAGE,
)
async def test_email_settings(
    body: EmailTestIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    email: EmailSettingsUseCases,
    audit: Audit,
) -> EmailTestOut:
    company_id = request_company_id(request)
    identity = await use_cases.company_identity(company_id)
    result = await email.test(company_id, body.recipient, identity.commercial_name or identity.name)
    await audit.record(
        action="TEST_COMPANY_EMAIL_SETTINGS",
        user_id=current.id,
        company_id=company_id,
        resource_type="company_email_settings",
        resource_id=str(company_id),
        after_state={"ok": result.ok, "recipient": body.recipient.strip().lower()},
        status="success" if result.ok else "failure",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return EmailTestOut(ok=result.ok, message=result.message)


# --- credenciales de Hacienda (bloque V3d) ---


def _hacienda_out(credentials: HaciendaCredentials | None) -> HaciendaCredentialsOut:
    if credentials is None:
        return HaciendaCredentialsOut(configured=False)
    return HaciendaCredentialsOut(
        configured=True,
        certificate_nit=credentials.certificate_nit,
        certificate_sha256=credentials.certificate_sha256,
        last_test_at=credentials.last_test_at,
        last_test_ok=credentials.last_test_ok,
        last_test_error=credentials.last_test_error,
        updated_at=credentials.updated_at,
    )


@router.get(
    "/hacienda-credentials",
    response_model=HaciendaCredentialsOut,
    summary="Credenciales de Hacienda de la empresa (sin secretos)",
    dependencies=_READ,
)
async def get_hacienda_credentials(
    request: Request, hacienda: HaciendaUseCases
) -> HaciendaCredentialsOut:
    return _hacienda_out(await hacienda.get(request_company_id(request)))


@router.put(
    "/hacienda-credentials",
    response_model=HaciendaCredentialsOut,
    summary="Guardar las credenciales de Hacienda (cifradas)",
    dependencies=_MANAGE,
)
async def save_hacienda_credentials(
    body: HaciendaCredentialsIn,
    request: Request,
    current: CurrentUser,
    hacienda: HaciendaUseCases,
    audit: Audit,
) -> HaciendaCredentialsOut:
    company_id = request_company_id(request)
    certificate: bytes | None = None
    if body.certificate_base64:
        try:
            certificate = base64.b64decode(body.certificate_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise BusinessRuleError(
                "El certificado no llegó en base64 válido.", code="hacienda_certificate_invalid"
            ) from exc
    before, saved = await hacienda.save(
        company_id,
        api_password=body.api_password,
        private_key_password=body.private_key_password,
        certificate=certificate,
        actor_id=current.id,
    )
    # La bitácora guarda solo el NIT y la huella del certificado, nunca las contraseñas.
    await _record(
        audit,
        request,
        action="UPDATE" if before else "CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="company_hacienda_credentials",
        resource_id=str(company_id),
        before=before,
        after=saved,
    )
    return _hacienda_out(saved)


@router.delete(
    "/hacienda-credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar las credenciales de Hacienda",
    dependencies=_MANAGE,
)
async def delete_hacienda_credentials(
    request: Request, current: CurrentUser, hacienda: HaciendaUseCases, audit: Audit
) -> None:
    company_id = request_company_id(request)
    before = await hacienda.get(company_id)
    if before is None:
        return
    await hacienda.remove(company_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        company_id=company_id,
        resource_type="company_hacienda_credentials",
        resource_id=str(company_id),
        before=before,
    )


@router.post(
    "/hacienda-credentials/test",
    response_model=HaciendaTestOut,
    summary="Probar la conexión con Hacienda y la firma",
    dependencies=_MANAGE,
)
async def test_hacienda_credentials(
    request: Request, current: CurrentUser, hacienda: HaciendaUseCases, audit: Audit
) -> HaciendaTestOut:
    company_id = request_company_id(request)
    result = await hacienda.test(company_id)
    await audit.record(
        action="TEST_HACIENDA_CREDENTIALS",
        user_id=current.id,
        company_id=company_id,
        resource_type="company_hacienda_credentials",
        resource_id=str(company_id),
        after_state={
            "ok": result.ok,
            "authentication_ok": result.authentication_ok,
            "signature_ok": result.signature_ok,
        },
        status="success" if result.ok else "failure",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return HaciendaTestOut(
        ok=result.ok,
        authentication_ok=result.authentication_ok,
        authentication_message=result.authentication_message,
        signature_ok=result.signature_ok,
        signature_message=result.signature_message,
    )
