"""Reloj de demostración del servicio DTE (V9b).

La siembra de datos de demostración genera un mes ya pasado con el reloj del proceso movido a
cada día. El servicio DTE fija ``fecEmi`` con su propio reloj, así que, solo mientras la siembra
lo activa, el cliente le envía ``X-DTE-Demo-Clock`` con el instante del proceso. El servicio lo
acepta únicamente con ``DTE_DEMO_CLOCK_ENABLED=true`` y un emisor simulado. En uso normal nunca
se envía.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

HEADER = "X-DTE-Demo-Clock"
_active: ContextVar[bool] = ContextVar("dte_demo_clock", default=False)


@contextmanager
def demo_clock() -> Iterator[None]:
    token = _active.set(True)
    try:
        yield
    finally:
        _active.reset(token)


def demo_clock_headers() -> dict[str, str]:
    """El encabezado con el instante actual del proceso, solo dentro de ``demo_clock()``."""

    if not _active.get():
        return {}
    return {HEADER: datetime.now(UTC).isoformat()}
