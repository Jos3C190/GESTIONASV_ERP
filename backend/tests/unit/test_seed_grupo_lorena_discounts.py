"""Datos de demostración de descuentos de Grupo Lorena."""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities.sales_margin import require_policy, require_volume_scale
from seed.seed_grupo_lorena_discounts import ROLE_POLICIES, TARGET_MARGINS, WHOLESALE_SCALES


def test_demo_values_pass_the_domain_rules() -> None:
    assert all(Decimal("0") <= margin <= Decimal("95") for margin in TARGET_MARGINS.values())
    for quantity, percent in WHOLESALE_SCALES:
        require_volume_scale(quantity, percent)
    for policy in ROLE_POLICIES.values():
        require_policy(policy)
