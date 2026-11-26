"""V9b: el cliente DTE solo manda el reloj de demostración dentro de la siembra."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import time_machine
from app.infrastructure.dte_demo_clock import HEADER, demo_clock
from app.infrastructure.dte_service_client import HttpDteServiceClient


async def _headers(client: HttpDteServiceClient) -> httpx.Headers:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    client._transport = httpx.MockTransport(handler)
    await client._send("06140101001010", "GET", "/api/health")
    return seen[0].headers


async def test_header_only_inside_the_demo_clock() -> None:
    client = HttpDteServiceClient("http://dte.internal", "clave")
    assert HEADER.lower() not in await _headers(client)
    with time_machine.travel(datetime(2026, 10, 15, 15, 30, tzinfo=UTC), tick=False), demo_clock():
        sent = await _headers(client)
    assert sent[HEADER] == "2026-10-15T15:30:00+00:00"
    assert HEADER.lower() not in await _headers(client)
