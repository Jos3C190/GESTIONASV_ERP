"""Fault-tolerant, vendor-neutral OpenTelemetry bootstrap and helpers."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from opentelemetry import context, metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.config import Settings, settings

_lock = threading.Lock()
_initialized = False
_service_name: str | None = None
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_logger_provider: LoggerProvider | None = None
_otel_log_handler: LoggingHandler | None = None
_sql_metric_engines: set[int] = set()
_trace_context_propagator = TraceContextTextMapPropagator()

_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|authorization|cookie|credential|signature|"
    r"object[_-]?key|document[_-]?path|x-amz-|aws_access)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://[^:/\s]+:[^@\s]+@|"
    r"bearer\s+[a-z0-9._~+/-]+|x-amz-signature=[^&\s]+|"
    r"(?:password|secret|token|authorization|cookie)=[^&\s]+|"
    r"companies/[0-9a-f-]+/documents/[0-9a-f-]+/[^\s]+)"
)
_MAX_VALUE_LENGTH = 4096
_ALLOWED_METRIC_ATTRIBUTES = frozenset(
    {
        "component",
        "service",
        "operation",
        "result",
        "status",
        "method",
        "route",
        "variant",
        "store",
    }
)
P = ParamSpec("P")
R = TypeVar("R")


class _ExcludeOtelInternalLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("opentelemetry.")


def _headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    result: dict[str, str] = {}
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip():
            result[key.strip()] = value.strip()
    return result


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact secrets and bound untrusted telemetry values."""
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_value(item) for item in value[:100]]
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub("[REDACTED]", value)[:_MAX_VALUE_LENGTH]
    return value


def correlation_ids() -> dict[str, str]:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }


def enrich_log_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict.update(correlation_ids())
    event_dict.setdefault("service", _service_name or "erp-backend")
    event_dict.setdefault("environment", settings.ENVIRONMENT)
    event_dict.setdefault("severity", str(event_dict.get("level", "info")).upper())
    return cast(dict[str, Any], redact_value(event_dict))


def _resource(service_name: str, config: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": service_name,
            "service.namespace": config.OTEL_SERVICE_NAMESPACE,
            "deployment.environment.name": config.ENVIRONMENT,
        }
    )


def _redis_request_hook(span: Any, _instance: Any, _args: Any, _kwargs: Any) -> None:
    if span is not None and span.is_recording():
        span.set_attribute("db.statement", "[REDACTED]")


def _instrument_sqlalchemy_metrics(engine: Any) -> None:  # noqa: C901
    """Attach low-cardinality SQL and pool metrics to one sync engine."""
    from sqlalchemy import event

    engine_id = id(engine)
    if engine_id in _sql_metric_engines:
        return
    _sql_metric_engines.add(engine_id)

    def _operation(statement: Any) -> str:
        token = str(statement).lstrip().split(maxsplit=1)
        operation = token[0].lower() if token else "unknown"
        return operation if operation in {"select", "insert", "update", "delete"} else "other"

    def _pool_state() -> None:
        try:
            record_gauge(
                "erp.postgresql.pool.checked_out",
                int(engine.pool.checkedout()),
            )
            record_gauge("erp.postgresql.pool.size", int(engine.pool.size()))
            record_gauge("erp.postgresql.pool.overflow", int(engine.pool.overflow()))
        except Exception:
            logging.getLogger(__name__).debug("otel_db_pool_metric_failed", exc_info=True)

    def _record_sql(execution_context: Any, result: str) -> None:
        try:
            started = getattr(execution_context, "_erp_otel_started", time.perf_counter())
            attributes = {
                "operation": getattr(execution_context, "_erp_otel_operation", "unknown"),
                "result": result,
            }
            record_counter("erp.postgresql.operations", attributes=attributes)
            record_histogram(
                "erp.postgresql.duration",
                (time.perf_counter() - started) * 1000,
                attributes=attributes,
            )
        except Exception:
            logging.getLogger(__name__).debug("otel_db_metric_failed", exc_info=True)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        _connection: Any,
        _cursor: Any,
        statement: Any,
        _parameters: Any,
        execution_context: Any,
        _executemany: bool,
    ) -> None:
        try:
            execution_context._erp_otel_started = time.perf_counter()
            execution_context._erp_otel_operation = _operation(statement)
        except Exception:
            logging.getLogger(__name__).debug("otel_db_metric_start_failed", exc_info=True)

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        _connection: Any,
        _cursor: Any,
        _statement: Any,
        _parameters: Any,
        execution_context: Any,
        _executemany: bool,
    ) -> None:
        _record_sql(execution_context, "ok")

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context: Any) -> None:
        _record_sql(exception_context.execution_context, "error")

    event.listen(engine.pool, "checkout", lambda *_args: _pool_state())
    event.listen(engine.pool, "checkin", lambda *_args: _pool_state())
    _pool_state()


def _initialize_observability_impl(
    service_name: str, *, app: Any | None = None, config: Settings = settings
) -> bool:
    """Initialize providers once per process and optionally instrument FastAPI."""
    global _initialized, _service_name, _tracer_provider, _meter_provider  # noqa: PLW0603
    global _logger_provider, _otel_log_handler  # noqa: PLW0603

    if not config.OBSERVABILITY_ENABLED:
        return False
    with _lock:
        if not _initialized:
            endpoint = str(config.OTEL_EXPORTER_OTLP_ENDPOINT).rstrip("/")
            exporter_headers = _headers(config.OTEL_EXPORTER_OTLP_HEADERS)
            timeout = config.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS
            resource = _resource(service_name, config)

            tracer_provider = TracerProvider(
                resource=resource,
                sampler=ParentBased(TraceIdRatioBased(config.otel_trace_sample_ratio)),
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=f"{endpoint}/v1/traces", headers=exporter_headers, timeout=timeout
                    )
                )
            )
            trace.set_tracer_provider(tracer_provider)

            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=f"{endpoint}/v1/metrics", headers=exporter_headers, timeout=timeout
                ),
                export_interval_millis=config.OTEL_METRIC_EXPORT_INTERVAL_SECONDS * 1000,
                export_timeout_millis=int(timeout * 1000),
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)

            logger_provider = LoggerProvider(resource=resource)
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    OTLPLogExporter(
                        endpoint=f"{endpoint}/v1/logs", headers=exporter_headers, timeout=timeout
                    )
                )
            )
            _otel_log_handler = LoggingHandler(
                level=logging.NOTSET, logger_provider=logger_provider
            )
            _otel_log_handler.addFilter(_ExcludeOtelInternalLogs())
            logging.getLogger().addHandler(_otel_log_handler)

            # Parameter capture is disabled. Botocore is intentionally not instrumented.
            from app.infrastructure.db.session import get_engine

            SQLAlchemyInstrumentor().instrument(
                engine=get_engine().sync_engine,
                enable_commenter=False,
            )
            _instrument_sqlalchemy_metrics(get_engine().sync_engine)
            AsyncPGInstrumentor().instrument(  # type: ignore[no-untyped-call]
                capture_parameters=False
            )
            RedisInstrumentor().instrument(request_hook=_redis_request_hook)
            # Trace Context carries traceparent and tracestate. Baggage is
            # deliberately excluded so application data cannot cross process
            # boundaries as telemetry metadata.
            set_global_textmap(_trace_context_propagator)

            _service_name = service_name
            _tracer_provider = tracer_provider
            _meter_provider = meter_provider
            _logger_provider = logger_provider
            _initialized = True
            record_counter("erp.process.starts", attributes={"service": service_name})

        # configure_logging() replaces root handlers. Reattach OTLP when the
        # lifespan invokes this idempotent initializer a second time.
        if _otel_log_handler is not None and _otel_log_handler not in logging.getLogger().handlers:
            logging.getLogger().addHandler(_otel_log_handler)

    if app is not None and not getattr(app.state, "otel_instrumented", False):
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls=r".*/health(?:/live|/ready)?$",
            tracer_provider=_tracer_provider,
            meter_provider=_meter_provider,
        )
        app.state.otel_instrumented = True
    return True


def initialize_observability(
    service_name: str, *, app: Any | None = None, config: Settings = settings
) -> bool:
    """Best-effort bootstrap: telemetry can never prevent service startup."""
    try:
        return _initialize_observability_impl(service_name, app=app, config=config)
    except Exception:
        logging.getLogger(__name__).exception("otel_initialization_failed")
        return False


def shutdown_observability() -> None:
    """Bounded, idempotent flush. SDK shutdown errors stay non-fatal."""
    global _initialized, _tracer_provider, _meter_provider, _logger_provider  # noqa: PLW0603
    global _otel_log_handler  # noqa: PLW0603
    with _lock:
        if not _initialized:
            return
        if _otel_log_handler is not None:
            logging.getLogger().removeHandler(_otel_log_handler)
        for provider in (_logger_provider, _meter_provider, _tracer_provider):
            if provider is not None:
                try:
                    provider.shutdown()
                except Exception:
                    logging.getLogger(__name__).debug("otel_shutdown_failed", exc_info=True)
        _initialized = False
        _tracer_provider = None
        _meter_provider = None
        _logger_provider = None
        _otel_log_handler = None


def sanitize_metric_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        return {}
    return {
        key: value
        for key, value in attributes.items()
        if key in _ALLOWED_METRIC_ATTRIBUTES and isinstance(value, str | bool | int | float)
    }


def record_counter(
    name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
) -> None:
    metrics.get_meter("erp.application").create_counter(name).add(
        value, sanitize_metric_attributes(attributes)
    )


def record_histogram(
    name: str, value: float, *, attributes: Mapping[str, Any] | None = None
) -> None:
    metrics.get_meter("erp.application").create_histogram(name).record(
        value, sanitize_metric_attributes(attributes)
    )


def record_gauge(
    name: str, value: int | float, *, attributes: Mapping[str, Any] | None = None
) -> None:
    metrics.get_meter("erp.application").create_gauge(name).set(
        value, sanitize_metric_attributes(attributes)
    )


@contextmanager
def operation_span(name: str, **attributes: str | bool | int | float) -> Iterator[Any]:
    with trace.get_tracer("erp.application").start_as_current_span(name) as span:
        if span.is_recording():
            for key, value in sanitize_metric_attributes(attributes).items():
                span.set_attribute(f"erp.{key}", value)
        yield span


@contextmanager
def observed_operation(service: str, operation: str) -> Iterator[None]:
    """Trace and meter an external operation without sensitive attributes."""
    started = time.perf_counter()
    result = "ok"
    with operation_span(f"{service}.{operation}", service=service, operation=operation):
        try:
            yield
        except Exception:
            result = "error"
            raise
        finally:
            attributes = {"service": service, "operation": operation, "result": result}
            record_counter("erp.external.operations", attributes=attributes)
            record_histogram(
                "erp.external.duration",
                (time.perf_counter() - started) * 1000,
                attributes=attributes,
            )


def observe_async(
    service: str, operation: str
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(function)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            with observed_operation(service, operation):
                return await function(*args, **kwargs)

        return wrapped

    return decorator


def inject_trace_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    _trace_context_propagator.inject(carrier)
    return carrier


@contextmanager
def extracted_trace_context(carrier: Mapping[str, str] | None) -> Iterator[None]:
    token = context.attach(_trace_context_propagator.extract(dict(carrier or {})))
    try:
        yield
    finally:
        context.detach(token)


__all__ = [
    "correlation_ids",
    "enrich_log_event",
    "extracted_trace_context",
    "initialize_observability",
    "inject_trace_context",
    "observe_async",
    "observed_operation",
    "operation_span",
    "record_counter",
    "record_gauge",
    "record_histogram",
    "redact_value",
    "sanitize_metric_attributes",
    "shutdown_observability",
]
