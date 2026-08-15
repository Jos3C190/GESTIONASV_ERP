"""SQLAlchemy implementation of SupplierRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.media_image import SingleImage, SingleImageDraft
from app.domain.entities.supplier import (
    Supplier,
    SupplierAddress,
    SupplierBankAccount,
    SupplierContact,
    SupplierTaxIdentifier,
)
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel
from app.infrastructure.models.supplier_image import SupplierContactImageModel, SupplierImageModel

_UNSET = object()


def _to_image(orm: SupplierImageModel | SupplierContactImageModel | None) -> SingleImage | None:
    if orm is None:
        return None
    return SingleImage(
        id=orm.id,
        source_type=orm.source_type,
        url=orm.url,
        media_asset_id=orm.media_asset_id,
        alt_text=orm.alt_text,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_supplier_contact(orm: SupplierContactModel) -> SupplierContact:
    return SupplierContact(
        id=orm.id_supplier_contact,
        supplier_id=orm.id_supplier,
        uuid=orm.uuid,
        full_name=orm.full_name,
        phone=orm.phone,
        email=orm.email,
        is_active=orm.is_active,
        avatar_image=_to_image(getattr(orm, "image", None)),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_supplier(orm: SupplierModel, *, include_details: bool = True, include_bank_accounts: bool = True) -> Supplier:
    contacts = (
        tuple(_to_supplier_contact(c) for c in orm.contacts)
        if hasattr(orm, "contacts") and orm.contacts
        else ()
    )
    tax_identifiers = tuple(
        SupplierTaxIdentifier(
            id=item.id,
            supplier_id=item.supplier_id,
            country_id=item.country_id,
            identifier_type=item.identifier_type,
            value=item.value,
            normalized_value=item.normalized_value,
            is_primary=item.is_primary,
            is_verified=item.is_verified,
            verified_at=item.verified_at,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
        )
        for item in getattr(orm, "tax_identifiers", ())
    ) if include_details else ()
    addresses = tuple(
        SupplierAddress(
            id=item.id,
            supplier_id=item.supplier_id,
            address_type=item.address_type,
            line1=item.line1,
            line2=item.line2,
            country_id=item.country_id,
            state_region=item.state_region,
            city=item.city,
            postal_code=item.postal_code,
            phone=item.phone,
            email=item.email,
            is_primary=item.is_primary,
        )
        for item in getattr(orm, "addresses", ())
    ) if include_details else ()
    bank_accounts = tuple(
        SupplierBankAccount(
            id=item.id,
            supplier_id=item.supplier_id,
            bank_name=item.bank_name,
            account_holder=item.account_holder,
            country_id=item.country_id,
            currency_code=item.currency_code,
            account_type=item.account_type,
            last_four=item.last_four,
            is_primary=item.is_primary,
            is_verified=item.is_verified,
            status=item.status,
            verified_at=item.verified_at,
        )
        for item in getattr(orm, "bank_accounts", ())
    ) if include_bank_accounts else ()
    return Supplier(
        id=orm.id_supplier,
        uuid=orm.uuid,
        company_id=orm.company_id,
        code=orm.code,
        name=orm.name,
        country_id=orm.country_id,
        address=orm.address,
        phone=orm.phone,
        email=orm.email,
        website=orm.website,
        is_active=orm.is_active,
        legal_name=orm.legal_name,
        supplier_group_id=orm.supplier_group_id,
        supplier_status=orm.supplier_status,
        hold_reason=orm.hold_reason,
        hold_from=orm.hold_from,
        hold_until=orm.hold_until,
        default_currency_code=orm.default_currency_code,
        payment_terms_id=orm.payment_terms_id,
        default_payment_method=orm.default_payment_method,
        external_reference=orm.external_reference,
        logo_image=_to_image(getattr(orm, "image", None)),
        tax_identifiers=tax_identifiers,
        addresses=addresses,
        bank_accounts=bank_accounts,
        contacts=contacts,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemySupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_suppliers(
        self,
        company_id: uuid.UUID,
        country_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        conditions = [SupplierModel.company_id == company_id]
        if country_id is not None:
            conditions.append(SupplierModel.country_id == country_id)
        if active_only:
            conditions.append(SupplierModel.is_active.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    SupplierModel.name.ilike(pattern),
                    SupplierModel.code.ilike(pattern),
                    SupplierModel.email.ilike(pattern),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(SupplierModel).where(*conditions)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        # Query items
        stmt = (
            select(SupplierModel)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
            )
            .where(*conditions)
            .order_by(SupplierModel.name)
            .offset(skip)
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        items = [_to_supplier(s, include_details=False, include_bank_accounts=False) for s in res.scalars().all()]
        return items, total

    async def get_supplier_by_id(self, company_id: uuid.UUID, supplier_id: int) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
                selectinload(SupplierModel.tax_identifiers),
                selectinload(SupplierModel.addresses),
                selectinload(SupplierModel.bank_accounts),
            )
            .where(SupplierModel.company_id == company_id, SupplierModel.id_supplier == supplier_id)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def get_supplier_by_uuid(
        self, company_id: uuid.UUID, supplier_uuid: uuid.UUID
    ) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
                selectinload(SupplierModel.tax_identifiers),
                selectinload(SupplierModel.addresses),
                selectinload(SupplierModel.bank_accounts),
            )
            .where(SupplierModel.company_id == company_id, SupplierModel.uuid == supplier_uuid)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def get_supplier_by_code(self, company_id: uuid.UUID, code: str) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
                selectinload(SupplierModel.tax_identifiers),
                selectinload(SupplierModel.addresses),
                selectinload(SupplierModel.bank_accounts),
            )
            .where(SupplierModel.company_id == company_id, SupplierModel.code == code)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_supplier(orm) if orm else None

    async def create_supplier(
        self,
        company_id: uuid.UUID,
        code: str,
        name: str,
        country_id: int,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        image: SingleImageDraft | None = None,
        **master_data: object,
    ) -> Supplier:
        orm = SupplierModel(
            company_id=company_id,
            code=code,
            name=name,
            country_id=country_id,
            address=address,
            phone=phone,
            email=email,
            website=website,
            **master_data,
        )
        self._session.add(orm)
        await self._session.flush()
        if image is not None:
            await self._sync_supplier_image(orm, company_id, image)
        return await self._get_supplier_with_media(company_id, orm.id_supplier)

    async def update_supplier(
        self, company_id: uuid.UUID, supplier_id: int, **kwargs
    ) -> Supplier | None:
        stmt = (
            select(SupplierModel)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
                selectinload(SupplierModel.tax_identifiers),
                selectinload(SupplierModel.addresses),
                selectinload(SupplierModel.bank_accounts),
            )
            .where(SupplierModel.company_id == company_id, SupplierModel.id_supplier == supplier_id)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        image_provided = "image" in kwargs
        image = kwargs.pop("image", None)
        for key, value in kwargs.items():
            if hasattr(orm, key):
                setattr(orm, key, value)
        await self._session.flush()
        if image_provided:
            await self._sync_supplier_image(orm, company_id, image)
        return await self._get_supplier_with_media(company_id, supplier_id)

    # Contacts
    async def get_contact_by_id(
        self, company_id: uuid.UUID, contact_id: int
    ) -> SupplierContact | None:
        stmt = (
            select(SupplierContactModel)
            .join(SupplierModel, SupplierModel.id_supplier == SupplierContactModel.id_supplier)
            .options(selectinload(SupplierContactModel.image))
            .where(
                SupplierModel.company_id == company_id,
                SupplierContactModel.id_supplier_contact == contact_id,
            )
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_supplier_contact(orm) if orm else None

    async def add_contact(
        self,
        company_id: uuid.UUID,
        supplier_id: int,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
        image: SingleImageDraft | None = None,
    ) -> SupplierContact:
        supplier = await self._session.scalar(
            select(SupplierModel).where(
                SupplierModel.company_id == company_id,
                SupplierModel.id_supplier == supplier_id,
            )
        )
        if supplier is None:
            raise LookupError("supplier_not_found")
        orm = SupplierContactModel(
            id_supplier=supplier_id,
            full_name=full_name,
            phone=phone,
            email=email,
        )
        self._session.add(orm)
        await self._session.flush()
        if image is not None:
            await self._sync_contact_image(orm, company_id, image)
        return await self._get_contact_with_media(company_id, orm.id_supplier_contact)

    async def update_contact(
        self,
        company_id: uuid.UUID,
        contact_id: int,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
        image: SingleImageDraft | None | object = _UNSET,
    ) -> SupplierContact | None:
        stmt = (
            select(SupplierContactModel)
            .join(SupplierModel, SupplierModel.id_supplier == SupplierContactModel.id_supplier)
            .where(
                SupplierModel.company_id == company_id,
                SupplierContactModel.id_supplier_contact == contact_id,
            )
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if full_name is not None:
            orm.full_name = full_name
        if phone is not None:
            orm.phone = phone
        if email is not None:
            orm.email = email
        if is_active is not None:
            orm.is_active = is_active
        await self._session.flush()
        if image is not _UNSET:
            await self._sync_contact_image(orm, company_id, image)
        return await self._get_contact_with_media(company_id, contact_id)

    async def deactivate_contact(self, company_id: uuid.UUID, contact_id: int) -> bool:
        contact = await self._session.scalar(
            select(SupplierContactModel)
            .join(SupplierModel, SupplierModel.id_supplier == SupplierContactModel.id_supplier)
            .where(
                SupplierModel.company_id == company_id,
                SupplierContactModel.id_supplier_contact == contact_id,
            )
        )
        if contact is None:
            return False
        contact.is_active = False
        await self._session.flush()
        return True

    async def _get_supplier_with_media(self, company_id: uuid.UUID, supplier_id: int) -> Supplier:
        result = await self._session.execute(
            select(SupplierModel)
            .where(SupplierModel.company_id == company_id, SupplierModel.id_supplier == supplier_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(SupplierModel.image),
                selectinload(SupplierModel.contacts).selectinload(SupplierContactModel.image),
                selectinload(SupplierModel.tax_identifiers),
                selectinload(SupplierModel.addresses),
                selectinload(SupplierModel.bank_accounts),
            )
        )
        orm = result.scalar_one()
        return _to_supplier(orm)

    async def _get_contact_with_media(
        self, company_id: uuid.UUID, contact_id: int
    ) -> SupplierContact:
        result = await self._session.execute(
            select(SupplierContactModel)
            .join(SupplierModel, SupplierModel.id_supplier == SupplierContactModel.id_supplier)
            .where(
                SupplierModel.company_id == company_id,
                SupplierContactModel.id_supplier_contact == contact_id,
            )
            .execution_options(populate_existing=True)
            .options(selectinload(SupplierContactModel.image))
        )
        orm = result.scalar_one()
        return _to_supplier_contact(orm)

    async def _claim_asset(
        self,
        *,
        company_id: uuid.UUID,
        asset_id: uuid.UUID,
        purpose: str,
        owner_type: str,
        owner_id: uuid.UUID,
    ) -> MediaAsset:
        asset = await self._session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == asset_id,
                MediaAsset.company_id == company_id,
                MediaAsset.provider == "cloudinary",
                MediaAsset.purpose == purpose,
                MediaAsset.status.in_(("staged", "active")),
            )
        )
        if asset is None:
            raise ValueError("El asset Cloudinary no existe, no pertenece a la empresa o no está disponible.")
        if asset.owner_id not in (None, owner_id) or asset.owner_type not in (None, owner_type):
            raise ValueError("El asset Cloudinary ya está asociado a otro recurso.")
        asset.status = "active"
        asset.owner_type = owner_type
        asset.owner_id = owner_id
        return asset

    async def _sync_supplier_image(
        self,
        supplier: SupplierModel,
        company_id: uuid.UUID,
        image: SingleImageDraft | None,
    ) -> None:
        existing = (
            await self._session.execute(
                select(SupplierImageModel).where(SupplierImageModel.supplier_id == supplier.id_supplier)
            )
        ).scalar_one_or_none()
        if (
            existing is not None
            and image is not None
            and image.source_type == "cloudinary"
            and image.media_asset_id == existing.media_asset_id
        ):
            asset = await self._claim_asset(
                company_id=company_id,
                asset_id=image.media_asset_id,
                purpose="supplier_logo",
                owner_type="supplier",
                owner_id=supplier.uuid,
            )
            existing.url = asset.secure_url
            existing.alt_text = image.alt_text
            await self._session.flush()
            return
        if existing is not None:
            await self._detach_asset(existing.media_asset_id)
            await self._session.delete(existing)
            await self._session.flush()
        if image is None:
            return
        if image.source_type == "cloudinary":
            asset = await self._claim_asset(
                company_id=company_id,
                asset_id=image.media_asset_id,
                purpose="supplier_logo",
                owner_type="supplier",
                owner_id=supplier.uuid,
            )
            url = asset.secure_url
        else:
            url = image.url
        self._session.add(
            SupplierImageModel(
                supplier_id=supplier.id_supplier,
                media_asset_id=image.media_asset_id,
                source_type=image.source_type,
                url=url,
                alt_text=image.alt_text,
            )
        )
        await self._session.flush()

    async def _sync_contact_image(
        self,
        contact: SupplierContactModel,
        company_id: uuid.UUID,
        image: SingleImageDraft | None | object,
    ) -> None:
        existing = (
            await self._session.execute(
                select(SupplierContactImageModel).where(
                    SupplierContactImageModel.supplier_contact_id == contact.id_supplier_contact
                )
            )
        ).scalar_one_or_none()
        if (
            existing is not None
            and image is not None
            and image is not _UNSET
            and image.source_type == "cloudinary"
            and image.media_asset_id == existing.media_asset_id
        ):
            asset = await self._claim_asset(
                company_id=company_id,
                asset_id=image.media_asset_id,
                purpose="supplier_contact_avatar",
                owner_type="supplier_contact",
                owner_id=contact.uuid,
            )
            existing.url = asset.secure_url
            existing.alt_text = image.alt_text
            await self._session.flush()
            return
        if existing is not None:
            await self._detach_asset(existing.media_asset_id)
            await self._session.delete(existing)
            await self._session.flush()
        if image is None or image is _UNSET:
            return
        if image.source_type == "cloudinary":
            asset = await self._claim_asset(
                company_id=company_id,
                asset_id=image.media_asset_id,
                purpose="supplier_contact_avatar",
                owner_type="supplier_contact",
                owner_id=contact.uuid,
            )
            url = asset.secure_url
        else:
            url = image.url
        self._session.add(
            SupplierContactImageModel(
                supplier_contact_id=contact.id_supplier_contact,
                media_asset_id=image.media_asset_id,
                source_type=image.source_type,
                url=url,
                alt_text=image.alt_text,
            )
        )
        await self._session.flush()

    async def _detach_asset(self, asset_id: uuid.UUID | None) -> None:
        if asset_id is None:
            return
        asset = await self._session.get(MediaAsset, asset_id)
        if asset is not None and asset.status != "deleted":
            asset.status = "detached"
            asset.owner_type = None
            asset.owner_id = None
