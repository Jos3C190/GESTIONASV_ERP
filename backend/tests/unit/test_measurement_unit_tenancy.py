from __future__ import annotations

import uuid

import pytest
from app.application.catalog.use_cases import CatalogUseCases
from app.core.exceptions import ConcurrencyError, ConflictError
from app.domain.entities.catalog import Unit

COMPANY_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
COMPANY_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


class UnitRepositoryFake:
    def __init__(self, unit: Unit) -> None:
        self.unit = unit

    async def list_units(self, company_id: uuid.UUID, active_only: bool = True) -> list[Unit]:
        if self.unit.owner_company_id not in (None, company_id):
            return []
        if active_only and not self.unit.is_enabled:
            return []
        return [self.unit]

    async def list_global_units(self, active_only: bool = False) -> list[Unit]:
        return [self.unit] if self.unit.is_standard else []

    async def get_unit_by_id(
        self, company_id: uuid.UUID, unit_id: int, *, require_enabled: bool = False
    ) -> Unit | None:
        if unit_id != self.unit.id or self.unit.owner_company_id not in (None, company_id):
            return None
        if require_enabled and not self.unit.is_enabled:
            return None
        return self.unit

    async def get_unit_by_code(self, company_id: uuid.UUID | None, code: str) -> Unit | None:
        return self.unit if code == self.unit.code else None

    async def count_unit_usage(self, unit_id: int, company_id: uuid.UUID | None = None) -> int:
        return self.unit.usage_count

    async def create_unit(self, company_id: uuid.UUID | None, **values: object) -> Unit:
        return Unit(
            id=2,
            owner_company_id=company_id,
            is_standard=company_id is None,
            name=str(values["name"]),
            type=str(values["type_"]),
            code=str(values["code"]),
            symbol=str(values["symbol"]),
        )

    async def update_unit(
        self, company_id: uuid.UUID | None, unit_id: int, expected_version: int, **changes: object
    ) -> Unit | None:
        if expected_version != self.unit.version:
            return None
        return self.unit

    async def configure_unit(
        self,
        company_id: uuid.UUID,
        unit_id: int,
        expected_version: int,
        *,
        enabled: bool,
        alias: str | None = None,
    ) -> Unit | None:
        if expected_version != self.unit.configuration_version:
            return None
        return self.unit


def custom_unit(*, usage_count: int = 0, enabled: bool = True) -> Unit:
    return Unit(
        id=1,
        owner_company_id=COMPANY_A,
        is_standard=False,
        name="Bandeja de 24",
        type="Empaque",
        code="TRAY-12",
        symbol="bdj",
        usage_count=usage_count,
        is_enabled=enabled,
        version=3,
        configuration_version=5,
    )


@pytest.mark.asyncio
async def test_custom_unit_is_not_visible_to_another_company() -> None:
    use_cases = CatalogUseCases(UnitRepositoryFake(custom_unit()))
    assert await use_cases.list_units(COMPANY_B) == []


@pytest.mark.asyncio
async def test_unit_in_use_cannot_be_deactivated() -> None:
    use_cases = CatalogUseCases(UnitRepositoryFake(custom_unit(usage_count=2)))
    with pytest.raises(ConflictError, match="2 producto"):
        await use_cases.configure_unit(COMPANY_A, 1, 5, enabled=False)


@pytest.mark.asyncio
async def test_stale_configuration_version_is_rejected() -> None:
    use_cases = CatalogUseCases(UnitRepositoryFake(custom_unit()))
    with pytest.raises(ConcurrencyError, match="otro usuario"):
        await use_cases.configure_unit(COMPANY_A, 1, 4, enabled=True)


@pytest.mark.asyncio
async def test_company_creates_owned_custom_unit() -> None:
    use_cases = CatalogUseCases(UnitRepositoryFake(custom_unit()))
    created = await use_cases.create_unit(
        COMPANY_A,
        name="Bandeja de 24",
        type_="Empaque",
        code="TRAY-24",
        symbol="bdj",
    )
    assert created.owner_company_id == COMPANY_A
    assert created.is_standard is False
