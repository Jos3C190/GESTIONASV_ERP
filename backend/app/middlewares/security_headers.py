"""Security headers middleware (OWASP A05).

Adds a conservative set of security headers to every response. HSTS is only
emitted in production because dev runs on plain HTTP.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

_DEFAULTS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "cross-origin",
}

# Conservative CSP. Tightened further in Phase 1 when we know exact needs.
_DEV_CSP = "default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' https://api.cloudinary.com http://localhost:8000 http://127.0.0.1:8000 ws://localhost:* ws://127.0.0.1:*; frame-ancestors 'none'"
_PROD_CSP = "default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https://api.cloudinary.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (no Starlette BaseHTTPMiddleware overhead)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        csp = _PROD_CSP if settings.is_production else _DEV_CSP
        extra = {"Content-Security-Policy": csp}
        if settings.is_production:
            extra["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        headers = {**_DEFAULTS, **extra}

        async def send_with_headers(message: object) -> None:
            assert isinstance(message, dict)
            if message.get("type") == "http.response.start":
                raw = message.get("headers", [])
                existing = {k.decode().lower() for k, _ in (raw or []) if isinstance(k, bytes | bytearray)}
                for k, v in headers.items():
                    lk = k.lower()
                    if lk not in existing:
                        raw.append((k.encode(), v.encode()))
                message["headers"] = raw
            await send(message)

        await self.app(scope, receive, send_with_headers)
