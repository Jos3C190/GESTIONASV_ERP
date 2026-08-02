from seed import seed_data
from seed.seed_grupo_lorena import BRANCHES, EMPLOYEES, main, validate_seed_data


def test_default_seed_entrypoint_is_grupo_lorena() -> None:
    assert seed_data.main is main


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
