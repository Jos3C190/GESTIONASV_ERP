"""Tenant-scoped persistence for normalized supplier master data."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secret_encryption import encrypt_secret, last_four
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import (
    CurrencyModel,
    PaymentTermsModel,
    SupplierAddressModel,
    SupplierBankAccountModel,
    SupplierGroupModel,
    SupplierTaxIdentifierModel,
)


class SupplierMasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def supplier_exists(self, company_id: uuid.UUID, supplier_id: int) -> bool:
        return bool(
            await self.session.scalar(
                select(SupplierModel.id_supplier).where(
                    SupplierModel.company_id == company_id,
                    SupplierModel.id_supplier == supplier_id,
                    SupplierModel.deleted_at.is_(None),
                )
            )
        )

    async def list_tax_identifiers(self, company_id: uuid.UUID, supplier_id: int) -> list[SupplierTaxIdentifierModel]:
        return list(
            (
                await self.session.scalars(
                    select(SupplierTaxIdentifierModel)
                    .join(SupplierModel)
                    .where(SupplierModel.company_id == company_id, SupplierModel.id_supplier == supplier_id)
                    .order_by(SupplierTaxIdentifierModel.country_id, SupplierTaxIdentifierModel.identifier_type)
                )
            ).all()
        )

    async def get_tax_identifier(self, company_id: uuid.UUID, supplier_id: int, item_id: uuid.UUID) -> SupplierTaxIdentifierModel | None:
        return await self.session.scalar(
            select(SupplierTaxIdentifierModel)
            .join(SupplierModel)
            .where(
                SupplierModel.company_id == company_id,
                SupplierTaxIdentifierModel.supplier_id == supplier_id,
                SupplierTaxIdentifierModel.id == item_id,
            )
        )

    async def save_tax_identifier(self, item: SupplierTaxIdentifierModel, *, primary: bool) -> SupplierTaxIdentifierModel:
        if primary:
            await self.session.execute(
                update(SupplierTaxIdentifierModel)
                .where(
                    SupplierTaxIdentifierModel.supplier_id == item.supplier_id,
                    SupplierTaxIdentifierModel.country_id == item.country_id,
                )
                .values(is_primary=False)
            )
        item.is_primary = primary
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_tax_identifier(self, item: SupplierTaxIdentifierModel) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def list_addresses(self, company_id: uuid.UUID, supplier_id: int) -> list[SupplierAddressModel]:
        return list(
            (
                await self.session.scalars(
                    select(SupplierAddressModel)
                    .join(SupplierModel)
                    .where(SupplierModel.company_id == company_id, SupplierAddressModel.supplier_id == supplier_id)
                    .order_by(SupplierAddressModel.address_type, SupplierAddressModel.is_primary.desc())
                )
            ).all()
        )

    async def get_address(self, company_id: uuid.UUID, supplier_id: int, item_id: uuid.UUID) -> SupplierAddressModel | None:
        return await self.session.scalar(
            select(SupplierAddressModel)
            .join(SupplierModel)
            .where(SupplierModel.company_id == company_id, SupplierAddressModel.supplier_id == supplier_id, SupplierAddressModel.id == item_id)
        )

    async def save_address(self, item: SupplierAddressModel, *, primary: bool) -> SupplierAddressModel:
        if primary:
            await self.session.execute(
                update(SupplierAddressModel)
                .where(SupplierAddressModel.supplier_id == item.supplier_id, SupplierAddressModel.address_type == item.address_type)
                .values(is_primary=False)
            )
        item.is_primary = primary
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_address(self, item: SupplierAddressModel) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def list_bank_accounts(self, company_id: uuid.UUID, supplier_id: int) -> list[SupplierBankAccountModel]:
        return list(
            (
                await self.session.scalars(
                    select(SupplierBankAccountModel)
                    .join(SupplierModel)
                    .where(SupplierModel.company_id == company_id, SupplierBankAccountModel.supplier_id == supplier_id)
                    .order_by(SupplierBankAccountModel.is_primary.desc(), SupplierBankAccountModel.created_at)
                )
            ).all()
        )

    async def get_bank_account(self, company_id: uuid.UUID, supplier_id: int, item_id: uuid.UUID) -> SupplierBankAccountModel | None:
        return await self.session.scalar(
            select(SupplierBankAccountModel)
            .join(SupplierModel)
            .where(SupplierModel.company_id == company_id, SupplierBankAccountModel.supplier_id == supplier_id, SupplierBankAccountModel.id == item_id)
        )

    async def save_bank_account(self, item: SupplierBankAccountModel, *, primary: bool) -> SupplierBankAccountModel:
        if primary:
            await self.session.execute(
                update(SupplierBankAccountModel)
                .where(SupplierBankAccountModel.supplier_id == item.supplier_id)
                .values(is_primary=False)
            )
        item.is_primary = primary
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_bank_account(self, item: SupplierBankAccountModel) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def list_groups(self, company_id: uuid.UUID) -> list[SupplierGroupModel]:
        return list((await self.session.scalars(select(SupplierGroupModel).where(SupplierGroupModel.company_id == company_id).order_by(SupplierGroupModel.name))).all())

    async def get_group(self, company_id: uuid.UUID, item_id: uuid.UUID) -> SupplierGroupModel | None:
        return await self.session.scalar(select(SupplierGroupModel).where(SupplierGroupModel.company_id == company_id, SupplierGroupModel.id == item_id))

    async def list_payment_terms(self, company_id: uuid.UUID) -> list[PaymentTermsModel]:
        return list((await self.session.scalars(select(PaymentTermsModel).where(PaymentTermsModel.company_id == company_id).order_by(PaymentTermsModel.net_days, PaymentTermsModel.name))).all())

    async def get_payment_terms(self, company_id: uuid.UUID, item_id: uuid.UUID) -> PaymentTermsModel | None:
        return await self.session.scalar(select(PaymentTermsModel).where(PaymentTermsModel.company_id == company_id, PaymentTermsModel.id == item_id))

    async def list_currencies(self) -> list[CurrencyModel]:
        return list((await self.session.scalars(select(CurrencyModel).where(CurrencyModel.is_active.is_(True)).order_by(CurrencyModel.code))).all())

    @staticmethod
    def normalize_tax_value(value: str) -> str:
        return "".join(value.casefold().split())

    @staticmethod
    def build_bank_fields(account_number: str, iban: str | None) -> dict[str, object]:
        return {
            "account_ciphertext": encrypt_secret(account_number),
            "iban_ciphertext": encrypt_secret(iban) if iban else None,
            "last_four": last_four(account_number),
            "encryption_key_version": "v1",
        }
