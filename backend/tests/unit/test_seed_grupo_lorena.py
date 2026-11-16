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


def test_follow_ups_run_fleet_automatically_and_operations_only_on_request() -> None:
    keys = [step.key for step in seed_data.FOLLOW_UPS]
    assert keys == [
        "seed.catalog.soft_flour_units",
        "seed.grupo_lorena.fleet",
        "seed.grupo_lorena.fiscal_issuer",
        "seed.grupo_lorena.customers",
        "seed.grupo_lorena.privacy_notice",
        "seed.grupo_lorena.price_lists",
        "seed.grupo_lorena.sales_discounts",
        "seed.grupo_lorena.operations",
    ]
    enabled = {step.key: step.enabled for step in seed_data.FOLLOW_UPS}
    assert enabled["seed.grupo_lorena.fleet"]() is True
    assert enabled["seed.grupo_lorena.fiscal_issuer"]() is True


def test_only_the_compose_entrypoint_runs_the_follow_ups(monkeypatch) -> None:
    received: dict[str, object] = {}

    async def fake_bootstrap(**kwargs):
        received.update(kwargs)
        return False

    monkeypatch.setattr(seed_data, "bootstrap", fake_bootstrap)
    seed_data.main()
    assert received == {"follow_ups": True}


def test_demo_operations_need_the_flag_and_never_run_in_production(monkeypatch) -> None:
    monkeypatch.delenv("SEED_DEMO_OPERATIONS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert seed_data.demo_operations_enabled() is False
    monkeypatch.setenv("SEED_DEMO_OPERATIONS", "true")
    assert seed_data.demo_operations_enabled() is True
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert seed_data.demo_operations_enabled() is False


async def _run_follow_ups(monkeypatch, steps, markers, *, force=False):
    written: dict[str, str] = {}

    async def read_marker(_session, key):
        return markers.get(key)

    async def write_marker(_session, key, value):
        written[key] = value

    monkeypatch.setattr(seed_data, "FOLLOW_UPS", steps)
    monkeypatch.setattr(seed_data, "_read_marker", read_marker)
    monkeypatch.setattr(seed_data, "_write_marker", write_marker)
    await seed_data._follow_ups(object(), force)
    return written


async def test_follow_ups_mark_only_finished_steps_and_survive_failures(monkeypatch) -> None:
    calls: list[str] = []

    def step(key, result, enabled=True):
        async def run():
            calls.append(key)
            if isinstance(result, Exception):
                raise result
            return result

        return seed_data.FollowUp(key, "v1", run, lambda: enabled)

    steps = (
        step("done", True),
        step("incomplete", False),
        step("broken", RuntimeError("antivirus caído")),
        step("disabled", True, enabled=False),
        step("already", True),
    )
    written = await _run_follow_ups(monkeypatch, steps, {"already": "v0"})
    assert calls == ["done", "incomplete", "broken"]
    assert written == {"done": "v1"}

    calls.clear()
    written = await _run_follow_ups(monkeypatch, steps, {"already": "v0"}, force=True)
    assert calls == ["done", "incomplete", "broken", "already"]
    assert written == {"done": "v1", "already": "v1"}


def test_grupo_lorena_seed_data_is_consistent() -> None:
    validate_seed_data()
    assert len(BRANCHES) == 7
    assert len(EMPLOYEES) == 30


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
