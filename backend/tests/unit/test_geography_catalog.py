from app.infrastructure.catalogs.el_salvador_geography import GEOGRAPHY, catalog_counts


def test_official_geography_catalog_has_complete_legal_structure() -> None:
    assert catalog_counts() == (14, 44, 262)
    assert len(set(GEOGRAPHY)) == 14
    assert "San Salvador" in GEOGRAPHY["San Salvador"]["San Salvador Centro"]


def test_geography_names_are_unique_within_each_parent() -> None:
    for municipalities in GEOGRAPHY.values():
        assert len(municipalities) == len(set(municipalities))
        for districts in municipalities.values():
            assert len(districts) == len(set(districts))
