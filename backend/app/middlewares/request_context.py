"""Request context middleware: assigns a request ID and binds it to structlog
contextvars for the lifetime of the request. Also emits a structured access log
line at the end of each HTTP request.

Security note (A09): we log method, normalized route, status, duration and
request ID. We DO NOT log IP addresses, bodies, headers or query strings.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from app.infrastructure.observability import correlation_ids, record_counter, record_histogram

log = structlog.get_logger("app.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=scope.get("method", ""),
        )

        start = time.perf_counter()
        status_code: int = 500

        async def send_with_log(message: object) -> None:
            assert isinstance(message, dict)
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                trace_id = correlation_ids().get("trace_id")
                if trace_id:
                    headers.append((b"x-trace-id", trace_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_log)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            route_obj = scope.get("route")
            route = getattr(route_obj, "path", "unmatched")
            method = str(scope.get("method", ""))
            if not str(scope.get("path", "")).startswith("/health"):
                attributes = {"method": method, "route": route, "status": str(status_code)}
                record_counter("erp.http.server.requests", attributes=attributes)
                record_histogram("erp.http.server.duration", duration_ms, attributes=attributes)
            log.info(
                "http_request",
                status=status_code,
                duration_ms=round(duration_ms, 2),
                route=route,
            )
            structlog.contextvars.clear_contextvars()
