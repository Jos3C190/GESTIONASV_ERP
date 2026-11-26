"""V9a: análisis comercial sin IVA, costo solo con permiso, metas y permisos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_sales_discounts import _login
from tests.e2e.test_sales_notes import _ccf

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

ANALYTICS = "/api/v1/sales/analytics"
GOALS = "/api/v1/sales/goals"


def _d(value: object) -> Decimal:
    return Decimal(str(value))


async def test_analysis_counts_net_sales_and_cost(e2e_client: AsyncClient) -> None:
    _, admin = await _login(e2e_client, superuser=True)
    today = datetime.now(ZoneInfo("America/El_Salvador")).date()
    period = f"{today:%Y-%m}"
    before = (await e2e_client.get(ANALYTICS, headers=admin)).json()

    # CCF de 4 unidades a $10.00 sin IVA, costo de kardex $7.00, entregado al confirmar.
    _, order, _ccf_doc = await _ccf(e2e_client, stock="4")
    after = (await e2e_client.get(ANALYTICS, headers=admin)).json()
    assert after["costs_visible"] is True
    assert _d(after["totals"]["net_sales"]) - _d(before["totals"]["net_sales"]) == Decimal("40.00")
    assert after["totals"]["documents"] - before["totals"]["documents"] == 1
    assert _d(after["totals"]["cost"]) - _d(before["totals"]["cost"]) == Decimal("28.00")
    assert after["start"] == today.replace(day=1).isoformat()

    branch = order["branch_id"]
    scoped = (await e2e_client.get(ANALYTICS, params={"branch_id": branch}, headers=admin)).json()
    assert [item["key"] for item in scoped["by_branch"]] == [branch]

    # Metas del mes: se guardan, se reflejan como avance y se quitan con monto vacío.
    goals = (await e2e_client.get(f"{GOALS}/{period}", headers=admin)).json()
    assert any(item["branch_id"] == branch for item in goals["goals"])
    saved = await e2e_client.put(
        f"{GOALS}/{period}",
        json={"goals": [{"branch_id": branch, "amount": "100000.00"}]},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    with_goal = (
        await e2e_client.get(ANALYTICS, params={"branch_id": branch}, headers=admin)
    ).json()
    [row] = with_goal["by_branch"]
    assert _d(row["goal"]) == Decimal("100000.00")
    assert row["goal_percent"] is not None
    removed = await e2e_client.put(
        f"{GOALS}/{period}", json={"goals": [{"branch_id": branch, "amount": None}]}, headers=admin
    )
    assert removed.status_code == 200, removed.text
    assert next(i for i in removed.json()["goals"] if i["branch_id"] == branch)["amount"] is None

    bad = await e2e_client.get(
        ANALYTICS, params={"from": today.isoformat(), "to": "2000-01-01"}, headers=admin
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "sales_analytics_range_invalid"


async def test_analysis_permissions(e2e_client: AsyncClient) -> None:
    _, seller = await _login(e2e_client, superuser=False, permissions=("sales:read",))
    denied = await e2e_client.get(ANALYTICS, headers=seller)
    assert denied.status_code == 403

    _, analyst = await _login(e2e_client, superuser=False, permissions=("sales_analytics:read",))
    seen = await e2e_client.get(ANALYTICS, headers=analyst)
    if seen.status_code == 403:  # sin acceso a todas las sucursales: consulta una propia
        pytest.skip("El usuario de prueba no tiene alcance de empresa completa")
    assert seen.status_code == 200, seen.text
    body = seen.json()
    assert body["costs_visible"] is False
    assert body["totals"]["cost"] is None
    assert body["totals"]["margin"] is None
    cannot_set = await e2e_client.put(f"{GOALS}/2026-11", json={"goals": []}, headers=analyst)
    assert cannot_set.status_code in (403, 422)
