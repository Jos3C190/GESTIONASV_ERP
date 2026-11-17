"""Atajos e2e para llegar a una cotización aceptada (V2d) y a su pedido (V2e).

Las pruebas de ventas, entregas y devoluciones necesitan una venta B06, que nace de una
cotización aceptada. Estos atajos recorren el flujo real: habilitar la factura, crear el
borrador (con precio manual, porque la semilla de pruebas no tiene listas de precios),
emitir y registrar la aceptación del cliente.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient, Response


async def enable_invoice(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.put(
        "/api/v1/fiscal/document-types/01",
        json={"is_enabled": True, "certification_status": "pending"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def with_manual_prices(body: dict[str, Any]) -> dict[str, Any]:
    """Convierte las líneas con ``unit_price`` en líneas con precio manual."""

    lines = []
    for original in body.get("lines", []):
        line = dict(original)
        if "unit_price" in line:
            line["manual_price"] = line.pop("unit_price")
        lines.append(line)
    return {**body, "lines": lines}


async def create_quote(
    client: AsyncClient, headers: dict[str, str], key: str, body: dict[str, Any]
) -> Response:
    await enable_invoice(client, headers)
    return await client.post(
        "/api/v1/sales/quotations",
        headers={**headers, "Idempotency-Key": key},
        json=with_manual_prices(body),
    )


async def accept_quote(
    client: AsyncClient, headers: dict[str, str], quote_id: str, version: int
) -> Response:
    """Emite la cotización y registra que el cliente la aceptó."""

    issued = await client.post(
        f"/api/v1/sales/quotations/{quote_id}/issue",
        headers=headers,
        json={"expected_version": version},
    )
    if issued.status_code != 200:
        return issued
    assert issued.json()["status"] == "issued", issued.text
    return await client.post(
        f"/api/v1/sales/quotations/{quote_id}/accept",
        headers=headers,
        json={"expected_version": issued.json()["version"]},
    )


async def order_from_quote(
    client: AsyncClient, headers: dict[str, str], quote_id: str, key: str
) -> Response:
    """Crea el pedido de una cotización aceptada, con retiro en sucursal hoy."""

    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    return await client.post(
        f"/api/v1/sales/quotations/{quote_id}/order",
        headers={**headers, "Idempotency-Key": key},
        json={"promised_date": today, "delivery_mode": "pickup"},
    )
