from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.api.v1.schemas.auth import MeResponse
from pydantic import ValidationError
from scripts.provision_warehouse_operator import operator_email


def test_generated_operator_address_can_load_the_auth_profile():
    user = SimpleNamespace(
        id=uuid4(),
        username="warehouse.operator",
        email=operator_email("warehouse.operator"),
        is_active=True,
        is_superuser=False,
        mfa_enabled=False,
        last_login_at=None,
        failed_login_attempts=0,
        locked_until=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert (
        MeResponse.model_validate(user, from_attributes=True).email
        == "warehouse.operator@example.com"
    )


def test_explicit_operator_email_is_preserved_and_normalized():
    assert operator_email("warehouse.operator", "operador@EXAMPLE.com") == "operador@example.com"


@pytest.mark.parametrize(
    "email", ["operator@gestionasv.invalid", "sin-arroba", "operator@localhost"]
)
def test_invalid_operator_address_is_rejected_before_provisioning(email):
    with pytest.raises(ValidationError, match="email address"):
        operator_email("warehouse.operator", email)
