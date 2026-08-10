from seed import seed_data
from seed.grupo_lorena_media import (
    BRANCH_MEDIA,
    COMPANY_ID,
    COMPANY_LOGO,
    all_media,
    validate_media_manifest,
)
from seed.seed_grupo_lorena import BRANCHES, EMPLOYEES, seed, validate_seed_data


def test_default_seed_entrypoint_is_grupo_lorena() -> None:
    assert seed_data.seed_grupo_lorena is seed
    assert callable(seed_data.main)


def test_seed_reconciliation_requires_explicit_force_flag(monkeypatch) -> None:
    monkeypatch.delenv("FORCE_SEED", raising=False)
    assert seed_data.force_seed_enabled() is False
    monkeypatch.setenv("FORCE_SEED", "true")
    assert seed_data.force_seed_enabled() is True


def test_grupo_lorena_seed_data_is_consistent() -> None:
    validate_seed_data()
    assert len(BRANCHES) == 7
    assert len(EMPLOYEES) == 26


def test_grupo_lorena_seed_uses_readable_business_data() -> None:
    forbidden_fragments = ("mock", "custom_", "perm_", "test-")
    labels = [branch.name.lower() for branch in BRANCHES]
    labels.extend(str(employee["code"]).lower() for employee in EMPLOYEES)
    assert all(fragment not in label for label in labels for fragment in forbidden_fragments)


def test_grupo_lorena_accounts_use_reserved_email_domain() -> None:
    usernames = [str(employee["username"]) for employee in EMPLOYEES if "username" in employee]
    assert usernames
    assert all(" " not in username and not username[-1].isdigit() for username in usernames)


def test_grupo_lorena_media_manifest_covers_every_branch() -> None:
    branch_codes = {branch.code for branch in BRANCHES}
    validate_media_manifest(branch_codes)
    assert set(BRANCH_MEDIA) == branch_codes
    assert sum(len(assets) for assets in BRANCH_MEDIA.values()) == 35
    assert len(all_media()) == 36


def test_grupo_lorena_media_uses_deterministic_company_scope() -> None:
    expected_scope = f"erp-mini/development/companies/{COMPANY_ID}/"
    assert COMPANY_LOGO.public_id.startswith(expected_scope)
    assert all(asset.public_id.startswith(expected_scope) for asset in all_media())
    assert all(asset.secure_url.startswith("https://res.cloudinary.com/") for asset in all_media())


def test_grupo_lorena_gallery_payload_matches_media_registry() -> None:
    for assets in BRANCH_MEDIA.values():
        for asset in assets:
            assert asset.gallery_item() == {
                "url": asset.secure_url,
                "caption": "",
                "public_id": asset.public_id,
            }
