"""Application use cases for Suppliers and Contacts."""

from __future__ import annotations

import uuid

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.media_image import SingleImageDraft, normalize_single_image_draft
from app.domain.entities.supplier import Supplier, SupplierContact
from app.domain.ports.catalog_repository import CatalogRepository
from app.domain.ports.supplier_repository import SupplierRepository


class SupplierUseCases:
    def __init__(self, supplier_repo: SupplierRepository, catalog_repo: CatalogRepository) -> None:
        self._supplier_repo = supplier_repo
        self._catalog_repo = catalog_repo

    async def list_suppliers(
        self,
        company_id: uuid.UUID,
        country_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Supplier], int]:
        return await self._supplier_repo.list_suppliers(
            company_id,
            country_id=country_id,
            search=search,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )

    async def get_supplier(self, company_id: uuid.UUID, supplier_id: int) -> Supplier:
        supplier = await self._supplier_repo.get_supplier_by_id(company_id, supplier_id)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

    async def get_supplier_by_uuid(
        self, company_id: uuid.UUID, supplier_uuid: uuid.UUID
    ) -> Supplier:
        supplier = await self._supplier_repo.get_supplier_by_uuid(company_id, supplier_uuid)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

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
        # Validate unique code
        existing = await self._supplier_repo.get_supplier_by_code(company_id, code)
        if existing:
            raise ConflictError(
                f"El código de proveedor '{code}' ya existe", code="supplier_code_exists"
            )

        # Validate country exists
        country = await self._catalog_repo.get_country_by_id(country_id)
        if not country:
            raise NotFoundError("País especificado no encontrado", code="country_not_found")

        return await self._supplier_repo.create_supplier(
            company_id,
            code=code,
            name=name,
            country_id=country_id,
            address=address,
            phone=phone,
            email=email,
            website=website,
            image=self._normalize_image(image),
            **master_data,
        )

    async def update_supplier(
        self, company_id: uuid.UUID, supplier_id: int, **kwargs: object
    ) -> Supplier:
        current = await self.get_supplier(company_id, supplier_id)
        if any(
            field in kwargs and kwargs[field] is None
            for field in ("code", "name", "country_id", "is_active")
        ):
            raise ValidationError(
                "No se puede vaciar un campo obligatorio del proveedor.",
                code="supplier_required_field",
            )
        if "country_id" in kwargs and kwargs["country_id"] is not None:
            country = await self._catalog_repo.get_country_by_id(kwargs["country_id"])
            if not country:
                raise NotFoundError("País especificado no encontrado", code="country_not_found")

        if "code" in kwargs:
            duplicate = await self._supplier_repo.get_supplier_by_code(
                company_id, str(kwargs["code"])
            )
            if duplicate and duplicate.id != current.id:
                raise ConflictError(
                    "El código ya está registrado en esta empresa.", code="supplier_code_exists"
                )
        if "image" in kwargs:
            kwargs["image"] = self._normalize_image(kwargs["image"])
        supplier = await self._supplier_repo.update_supplier(company_id, supplier_id, **kwargs)
        if not supplier:
            raise NotFoundError("Proveedor no encontrado", code="supplier_not_found")
        return supplier

    # Contacts
    async def get_contact(self, company_id: uuid.UUID, contact_id: int) -> SupplierContact:
        contact = await self._supplier_repo.get_contact_by_id(company_id, contact_id)
        if not contact:
            raise NotFoundError("Contacto de proveedor no encontrado", code="contact_not_found")
        return contact

    async def add_contact(
        self,
        company_id: uuid.UUID,
        supplier_id: int,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
        image: SingleImageDraft | None = None,
    ) -> SupplierContact:
        await self.get_supplier(company_id, supplier_id)
        return await self._supplier_repo.add_contact(
            company_id,
            supplier_id=supplier_id,
            full_name=full_name,
            phone=phone,
            email=email,
            image=self._normalize_image(image),
        )

    async def update_contact(
        self,
        company_id: uuid.UUID,
        contact_id: int,
        **changes: object,
    ) -> SupplierContact:
        if "image" in changes:
            changes["image"] = self._normalize_image(changes["image"])
        contact = await self._supplier_repo.update_contact(
            company_id,
            contact_id=contact_id,
            **changes,
        )
        if not contact:
            raise NotFoundError("Contacto de proveedor no encontrado", code="contact_not_found")
        return contact

    async def deactivate_contact(self, company_id: uuid.UUID, contact_id: int) -> bool:
        deleted = await self._supplier_repo.deactivate_contact(company_id, contact_id)
        if not deleted:
            raise NotFoundError("Contacto de proveedor no encontrado", code="contact_not_found")
        return True

    @staticmethod
    def _normalize_image(image: object) -> SingleImageDraft | None:
        if image is None:
            return None
        if not isinstance(image, SingleImageDraft):
            raise ValidationError("La imagen del proveedor no es válida.", code="supplier_image_invalid")
        try:
            return normalize_single_image_draft(image)
        except ValueError as exc:
            raise ValidationError(str(exc), code="supplier_image_invalid") from exc
