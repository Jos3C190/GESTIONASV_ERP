"""Catálogos de Hacienda (versión 1.1, julio de 2026) y su enlace con la geografía."""

from __future__ import annotations

from collections import Counter

from app.infrastructure.catalogs.el_salvador_geography import GEOGRAPHY
from app.infrastructure.catalogs.hacienda_dte import CATALOG_VERSION, CATALOGS
from app.infrastructure.catalogs.hacienda_geography import (
    DEPARTMENT_CODES,
    DISTRICT_CODES,
    MUNICIPALITY_CODES,
)


def _codes(catalog: str, group: str | None = None) -> list[str]:
    return [code for g, code, _ in CATALOGS[catalog][1] if group is None or g == group]


def test_version_and_all_catalogs_present() -> None:
    assert CATALOG_VERSION == "1.1"
    assert sorted(CATALOGS) == [f"CAT-{n:03d}" for n in range(1, 34)]


def test_catalog_sizes_match_official_workbook() -> None:
    sizes = {key: len(rows) for key, (_, rows) in CATALOGS.items()}
    assert sizes["CAT-002"] == 13
    assert sizes["CAT-008"] == 263  # 262 distritos + «Otro (para extranjeros)»
    assert sizes["CAT-012"] == 15
    assert sizes["CAT-013"] == 45
    assert sizes["CAT-014"] == 40
    assert sizes["CAT-019"] == 774
    assert sizes["CAT-020"] == 249


def test_document_types_include_v2_events() -> None:
    assert _codes("CAT-002") == [
        "01", "03", "04", "05", "06", "07", "08", "09", "11", "14", "15", "17", "18",
    ]  # fmt: skip


def test_codes_are_unique_within_their_group() -> None:
    for key, (_, rows) in CATALOGS.items():
        repeated = [k for k, n in Counter((g, c) for g, c, _ in rows).items() if n > 1]
        assert repeated == [], key


def test_tax_sections_keep_duplicated_codes_apart() -> None:
    assert "D4" in _codes("CAT-015", "summary")
    assert "D4" in _codes("CAT-015", "body")
    assert "20" in _codes("CAT-015", "summary")


def test_footnote_markers_are_removed_from_units() -> None:
    names = {code: name for _, code, name in CATALOGS["CAT-014"][1]}
    assert names["2"] == "Yarda"
    assert names["22"] == "Galón"
    assert names["59"] == "Unidad"


def test_every_erp_department_municipality_and_district_has_a_code() -> None:
    assert len(DEPARTMENT_CODES) == 14
    assert len(MUNICIPALITY_CODES) == 44
    assert len(DISTRICT_CODES) == 262
    for department, municipalities in GEOGRAPHY.items():
        dep = DEPARTMENT_CODES[department]
        for municipality, districts in municipalities.items():
            assert MUNICIPALITY_CODES[(department, municipality)] in _codes("CAT-013", dep)
            for district in districts:
                assert DISTRICT_CODES[(department, municipality, district)] in _codes(
                    "CAT-008", dep
                )


def test_district_codes_are_unique_per_department() -> None:
    per_department: dict[str, list[str]] = {}
    for (department, _, _), code in DISTRICT_CODES.items():
        per_department.setdefault(department, []).append(code)
    for department, codes in per_department.items():
        assert len(codes) == len(set(codes)), department


def test_sample_of_abbreviated_districts() -> None:
    assert DEPARTMENT_CODES["San Salvador"] == "06"
    assert MUNICIPALITY_CODES[("San Salvador", "San Salvador Centro")] == "23"
    assert DISTRICT_CODES[("San Salvador", "San Salvador Centro", "San Salvador")] == "14"
    assert DISTRICT_CODES[("Santa Ana", "Santa Ana Norte", "Santa Rosa Guachipilín")] == "11"
    assert DISTRICT_CODES[("La Libertad", "La Libertad Este", "Antiguo Cuscatlán")] == "01"
    assert DISTRICT_CODES[("La Unión", "La Unión Norte", "San José La Fuente")] == "15"
