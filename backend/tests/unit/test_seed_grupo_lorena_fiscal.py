"""Datos del emisor de demostración de Grupo Lorena."""

from __future__ import annotations

from app.domain.entities.fiscal import (
    DOCUMENT_TYPES,
    EstablishmentType,
    validate_activity_code,
    validate_establishment_code,
    validate_point_of_sale_code,
)
from app.infrastructure.catalogs.hacienda_dte import CATALOGS
from seed.seed_grupo_lorena import BRANCHES
from seed.seed_grupo_lorena_fiscal import (
    ENABLED_DOCUMENTS,
    ESTABLISHMENTS,
    POINT_OF_SALE,
    PRODUCTION_ACTIVITY,
    RETAIL_ACTIVITY,
)


def test_headquarters_and_every_store_are_establishments() -> None:
    assert len(ESTABLISHMENTS) == len(BRANCHES) + 1
    headquarters = [e for e in ESTABLISHMENTS if e.branch_code is None]
    assert [(e.establishment_type, e.code) for e in headquarters] == [
        (EstablishmentType.HEADQUARTERS, "M001")
    ]
    stores = [e for e in ESTABLISHMENTS if e.branch_code is not None]
    assert {e.branch_code for e in stores} == {b.code for b in BRANCHES}
    assert [e.code for e in stores] == [f"S{n:03d}" for n in range(1, len(BRANCHES) + 1)]


def test_codes_follow_hacienda_rules() -> None:
    for item in ESTABLISHMENTS:
        assert validate_establishment_code(item.establishment_type, item.code) == item.code
    assert validate_point_of_sale_code(POINT_OF_SALE[0]) == "P001"
    activities = {code for _, code, _ in CATALOGS["CAT-019"][1]}
    for code in (PRODUCTION_ACTIVITY, RETAIL_ACTIVITY):
        assert validate_activity_code(code) in activities


def test_enabled_documents_are_the_ones_a_bakery_issues() -> None:
    assert set(ENABLED_DOCUMENTS) <= set(DOCUMENT_TYPES)
    assert ENABLED_DOCUMENTS == ("01", "03", "04", "05", "06")
