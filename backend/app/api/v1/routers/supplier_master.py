"""Normalized supplier master endpoints (tax, address, bank and catalog data)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.supplier import (
    CurrencyResponse,
    PaymentTermsCreate,
    PaymentTermsResponse,
    PaymentTermsUpdate,
    SupplierAddressCreate,
    SupplierAddressResponse,
    SupplierAddressUpdate,
    SupplierBankAccountCreate,
    SupplierBankAccountResponse,
    SupplierBankAccountUpdate,
    SupplierGroupCreate,
    SupplierGroupResponse,
    SupplierGroupUpdate,
    SupplierTaxIdentifierCreate,
    SupplierTaxIdentifierResponse,
    SupplierTaxIdentifierUpdate,
)
from app.application.audit.audit_service import AuditService
from app.core.secret_encryption import EncryptionConfigurationError, encrypt_secret
from app.infrastructure.models.supplier_master_data import (
    PaymentTermsModel,
    SupplierAddressModel,
    SupplierBankAccountModel,
    SupplierGroupModel,
    SupplierTaxIdentifierModel,
)
from app.infrastructure.repositories.supplier_master_repository import SupplierMasterRepository

router = APIRouter(tags=["suppliers-master"])


def _repo(session: SessionDep) -> SupplierMasterRepository:
    return SupplierMasterRepository(session)


async def _ensure_supplier(repo: SupplierMasterRepository, company_id: uuid.UUID, supplier_id: int) -> None:
    if not await repo.supplier_exists(company_id, supplier_id):
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")


def _tax(value: SupplierTaxIdentifierModel) -> SupplierTaxIdentifierResponse:
    return SupplierTaxIdentifierResponse.model_validate(value)


def _address(value: SupplierAddressModel) -> SupplierAddressResponse:
    return SupplierAddressResponse.model_validate(value)


def _bank(value: SupplierBankAccountModel) -> SupplierBankAccountResponse:
    return SupplierBankAccountResponse.model_validate(value)


@router.get("/currencies", response_model=list[CurrencyResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_currencies(session: SessionDep, current: CurrentUser, request: Request) -> list[CurrencyResponse]:
    await require_company_access(session, current, request_company_id(request))
    return [CurrencyResponse.model_validate(item) for item in await _repo(session).list_currencies()]


@router.get("/supplier-groups", response_model=list[SupplierGroupResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_supplier_groups(request: Request, session: SessionDep, current: CurrentUser) -> list[SupplierGroupResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return [SupplierGroupResponse.model_validate(item) for item in await _repo(session).list_groups(company_id)]


@router.post("/supplier-groups", response_model=SupplierGroupResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("suppliers:manage"))])
async def create_supplier_group(payload: SupplierGroupCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierGroupResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = SupplierGroupModel(company_id=company_id, **payload.model_dump())
    session.add(item)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="supplier_groups", resource_id=str(item.id), after_state={"code": item.code, "name": item.name})
    return SupplierGroupResponse.model_validate(item)


@router.patch("/supplier-groups/{group_id}", response_model=SupplierGroupResponse, dependencies=[Depends(require_permission("suppliers:manage"))])
async def update_supplier_group(group_id: uuid.UUID, payload: SupplierGroupUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierGroupResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _repo(session).get_group(company_id, group_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Grupo de proveedores no encontrado")
    before = {"code": item.code, "name": item.name, "is_active": item.is_active}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="supplier_groups", resource_id=str(item.id), before_state=before, after_state={"code": item.code, "name": item.name, "is_active": item.is_active})
    return SupplierGroupResponse.model_validate(item)


@router.delete("/supplier-groups/{group_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("suppliers:manage"))])
async def delete_supplier_group(group_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _repo(session).get_group(company_id, group_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Grupo de proveedores no encontrado")
    await session.delete(item)
    await session.flush()
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="supplier_groups", resource_id=str(group_id))


@router.get("/payment-terms", response_model=list[PaymentTermsResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_payment_terms(request: Request, session: SessionDep, current: CurrentUser) -> list[PaymentTermsResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return [PaymentTermsResponse.model_validate(item) for item in await _repo(session).list_payment_terms(company_id)]


@router.post("/payment-terms", response_model=PaymentTermsResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("suppliers:manage"))])
async def create_payment_terms(payload: PaymentTermsCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> PaymentTermsResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if payload.discount_days > payload.net_days:
        raise HTTPException(status_code=422, detail="Los días de descuento no pueden superar los días netos")
    item = PaymentTermsModel(company_id=company_id, **payload.model_dump())
    session.add(item)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="payment_terms", resource_id=str(item.id), after_state={"code": item.code, "net_days": item.net_days})
    return PaymentTermsResponse.model_validate(item)


@router.patch("/payment-terms/{terms_id}", response_model=PaymentTermsResponse, dependencies=[Depends(require_permission("suppliers:manage"))])
async def update_payment_terms(terms_id: uuid.UUID, payload: PaymentTermsUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> PaymentTermsResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _repo(session).get_payment_terms(company_id, terms_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Términos de pago no encontrados")
    values = payload.model_dump(exclude_unset=True)
    net_days = values.get("net_days", item.net_days)
    if values.get("discount_days", item.discount_days) > net_days:
        raise HTTPException(status_code=422, detail="Los días de descuento no pueden superar los días netos")
    for key, value in values.items():
        setattr(item, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="payment_terms", resource_id=str(item.id), after_state={"code": item.code, "net_days": item.net_days})
    return PaymentTermsResponse.model_validate(item)


@router.get("/suppliers/{supplier_id}/tax-identifiers", response_model=list[SupplierTaxIdentifierResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_tax_identifiers(supplier_id: int, request: Request, session: SessionDep, current: CurrentUser) -> list[SupplierTaxIdentifierResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    return [_tax(item) for item in await repo.list_tax_identifiers(company_id, supplier_id)]


@router.post("/suppliers/{supplier_id}/tax-identifiers", response_model=SupplierTaxIdentifierResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("suppliers:tax_identifiers"))])
async def create_tax_identifier(supplier_id: int, payload: SupplierTaxIdentifierCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierTaxIdentifierResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    normalized = repo.normalize_tax_value(payload.value)
    duplicate = await session.scalar(select(SupplierTaxIdentifierModel).where(SupplierTaxIdentifierModel.supplier_id == supplier_id, SupplierTaxIdentifierModel.country_id == payload.country_id, SupplierTaxIdentifierModel.identifier_type == payload.identifier_type, SupplierTaxIdentifierModel.normalized_value == normalized))
    if duplicate:
        raise HTTPException(status_code=409, detail="El identificador fiscal ya existe")
    item = SupplierTaxIdentifierModel(supplier_id=supplier_id, normalized_value=normalized, **payload.model_dump())
    await repo.save_tax_identifier(item, primary=payload.is_primary)
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="supplier_tax_identifiers", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "country_id": item.country_id, "identifier_type": item.identifier_type, "is_primary": item.is_primary})
    return _tax(item)


@router.patch("/suppliers/{supplier_id}/tax-identifiers/{identifier_id}", response_model=SupplierTaxIdentifierResponse, dependencies=[Depends(require_permission("suppliers:tax_identifiers"))])
async def update_tax_identifier(supplier_id: int, identifier_id: uuid.UUID, payload: SupplierTaxIdentifierUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierTaxIdentifierResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_tax_identifier(company_id, supplier_id, identifier_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Identificador fiscal no encontrado")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    if "value" in values:
        item.normalized_value = repo.normalize_tax_value(item.value)
    await repo.save_tax_identifier(item, primary=bool(values.get("is_primary", item.is_primary)))
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="supplier_tax_identifiers", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "country_id": item.country_id, "identifier_type": item.identifier_type, "is_primary": item.is_primary})
    return _tax(item)


@router.delete("/suppliers/{supplier_id}/tax-identifiers/{identifier_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("suppliers:tax_identifiers"))])
async def delete_tax_identifier(supplier_id: int, identifier_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_tax_identifier(company_id, supplier_id, identifier_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Identificador fiscal no encontrado")
    await repo.delete_tax_identifier(item)
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="supplier_tax_identifiers", resource_id=str(identifier_id), after_state={"supplier_id": supplier_id})


@router.get("/suppliers/{supplier_id}/addresses", response_model=list[SupplierAddressResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_addresses(supplier_id: int, request: Request, session: SessionDep, current: CurrentUser) -> list[SupplierAddressResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    return [_address(item) for item in await repo.list_addresses(company_id, supplier_id)]


@router.post("/suppliers/{supplier_id}/addresses", response_model=SupplierAddressResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("suppliers:addresses"))])
async def create_address(supplier_id: int, payload: SupplierAddressCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierAddressResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    item = SupplierAddressModel(supplier_id=supplier_id, **payload.model_dump())
    await repo.save_address(item, primary=payload.is_primary)
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="supplier_addresses", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "address_type": item.address_type, "is_primary": item.is_primary})
    return _address(item)


@router.patch("/suppliers/{supplier_id}/addresses/{address_id}", response_model=SupplierAddressResponse, dependencies=[Depends(require_permission("suppliers:addresses"))])
async def update_address(supplier_id: int, address_id: uuid.UUID, payload: SupplierAddressUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierAddressResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_address(company_id, supplier_id, address_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await repo.save_address(item, primary=bool(item.is_primary))
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="supplier_addresses", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "address_type": item.address_type, "is_primary": item.is_primary})
    return _address(item)


@router.delete("/suppliers/{supplier_id}/addresses/{address_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("suppliers:addresses"))])
async def delete_address(supplier_id: int, address_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_address(company_id, supplier_id, address_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    await repo.delete_address(item)
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="supplier_addresses", resource_id=str(address_id), after_state={"supplier_id": supplier_id})


@router.get("/suppliers/{supplier_id}/bank-accounts", response_model=list[SupplierBankAccountResponse], dependencies=[Depends(require_permission("suppliers:bank_accounts"))])
async def list_bank_accounts(supplier_id: int, request: Request, session: SessionDep, current: CurrentUser) -> list[SupplierBankAccountResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    return [_bank(item) for item in await repo.list_bank_accounts(company_id, supplier_id)]


@router.post("/suppliers/{supplier_id}/bank-accounts", response_model=SupplierBankAccountResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("suppliers:bank_accounts"))])
async def create_bank_account(supplier_id: int, payload: SupplierBankAccountCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierBankAccountResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    await _ensure_supplier(repo, company_id, supplier_id)
    try:
        bank_fields = repo.build_bank_fields(payload.account_number, payload.iban)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=503, detail="El cifrado de datos bancarios no está configurado") from exc
    item = SupplierBankAccountModel(supplier_id=supplier_id, **payload.model_dump(exclude={"account_number", "iban"}), **bank_fields)
    await repo.save_bank_account(item, primary=payload.is_primary)
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="supplier_bank_accounts", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "bank_name": item.bank_name, "last_four": item.last_four, "is_primary": item.is_primary})
    return _bank(item)


@router.patch("/suppliers/{supplier_id}/bank-accounts/{account_id}", response_model=SupplierBankAccountResponse, dependencies=[Depends(require_permission("suppliers:bank_accounts"))])
async def update_bank_account(supplier_id: int, account_id: uuid.UUID, payload: SupplierBankAccountUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> SupplierBankAccountResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_bank_account(company_id, supplier_id, account_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    values = payload.model_dump(exclude_unset=True)
    account = values.pop("account_number", None)
    iban_provided = "iban" in values
    iban = values.pop("iban", None) if iban_provided else None
    if account is not None:
        try:
            bank_fields = repo.build_bank_fields(account, iban if iban_provided else None)
            values["account_ciphertext"] = bank_fields["account_ciphertext"]
            values["last_four"] = bank_fields["last_four"]
            values["encryption_key_version"] = bank_fields["encryption_key_version"]
            if iban_provided:
                values["iban_ciphertext"] = bank_fields["iban_ciphertext"]
        except EncryptionConfigurationError as exc:
            raise HTTPException(status_code=503, detail="El cifrado de datos bancarios no está configurado") from exc
    elif iban_provided:
        try:
            values["iban_ciphertext"] = encrypt_secret(iban) if iban else None
        except EncryptionConfigurationError as exc:
            raise HTTPException(status_code=503, detail="El cifrado de datos bancarios no está configurado") from exc
    for key, value in values.items():
        setattr(item, key, value)
    await repo.save_bank_account(item, primary=bool(values.get("is_primary", item.is_primary)))
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="supplier_bank_accounts", resource_id=str(item.id), after_state={"supplier_id": supplier_id, "bank_name": item.bank_name, "last_four": item.last_four, "is_primary": item.is_primary})
    return _bank(item)


@router.delete("/suppliers/{supplier_id}/bank-accounts/{account_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("suppliers:bank_accounts"))])
async def delete_bank_account(supplier_id: int, account_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    repo = _repo(session)
    item = await repo.get_bank_account(company_id, supplier_id, account_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    await repo.delete_bank_account(item)
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="supplier_bank_accounts", resource_id=str(account_id), after_state={"supplier_id": supplier_id})
