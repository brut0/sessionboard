"""OpenTelemetry setup, tracing, metrics, log correlation, and booking telemetry helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TextIO

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from opentelemetry import _logs, metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Status, StatusCode
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app import db as app_db
from app.config import Settings
from app.logging_config import configure_logging, teardown_logging_handlers

logger = logging.getLogger(__name__)
booking_logger = logging.getLogger("app.booking")

_SECONDS_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


@dataclass
class _TelemetryRuntime:
    enabled: bool = False
    env: str = "local"
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None
    logger_provider: LoggerProvider | None = None
    tracer: trace.Tracer = field(default_factory=lambda: trace.get_tracer("sessionboard"))
    booking_counter: Counter | None = None
    booking_duration_histogram: Histogram | None = None
    instrumented_app: FastAPI | None = None
    instrumented_engine: Engine | None = None
    logging_handlers: list[logging.Handler] = field(default_factory=list)


_runtime = _TelemetryRuntime()


def build_otlp_signal_endpoint(base_endpoint: str, signal: str) -> str:
    """Resolve signal-specific OTLP/HTTP endpoint path for traces, metrics, or logs."""
    cleaned = base_endpoint.rstrip("/")
    suffix = f"/v1/{signal}"
    if cleaned.endswith(suffix):
        return cleaned
    return f"{cleaned}{suffix}"


def get_current_trace_id() -> str:
    """Return the active 32-hex trace ID or generate a fresh UUID4 hex string."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return f"{span.get_span_context().trace_id:032x}"
    return uuid.uuid4().hex


def get_current_span_id() -> str:
    """Return the active 16-hex span ID or zero-filled placeholder."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return f"{span.get_span_context().span_id:016x}"
    return "0" * 16


def get_tracer() -> trace.Tracer:
    """Return the configured tracer for SessionBoard spans."""
    return _runtime.tracer


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Ensure X-Trace-Id propagation and sanitize unhandled errors before OTel ASGI re-raise."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx is not None and ctx.is_valid:
            trace_id = f"{ctx.trace_id:032x}"
            span_id = f"{ctx.span_id:016x}"
        else:
            trace_id = uuid.uuid4().hex
            span_id = "0" * 16

        request.state.trace_id = trace_id
        request.state.span_id = span_id

        try:
            response = await call_next(request)
        except Exception as exc:
            active_span = trace.get_current_span()
            active_ctx = active_span.get_span_context() if active_span else None
            if active_ctx is not None and active_ctx.is_valid:
                trace_id = f"{active_ctx.trace_id:032x}"
                span_id = f"{active_ctx.span_id:016x}"

            error_type = type(exc).__name__
            if active_span is not None and active_span.is_recording():
                active_span.set_attribute("error.type", error_type)
                active_span.set_status(Status(StatusCode.ERROR, error_type))

            if (
                request.url.path == "/api/sessions"
                and request.method.upper() == "POST"
                and not getattr(request.state, "booking_telemetry_recorded", False)
            ):
                record_booking_outcome(
                    result="error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    duration_seconds=0.0,
                    error_type=error_type,
                    trace_id_override=trace_id,
                    span_id_override=span_id,
                )
            else:
                logger.error(
                    "Unhandled server exception: %s",
                    error_type,
                    extra={
                        "event": "request.unhandled_error",
                        "env": _runtime.env,
                        "http.route": request.url.path,
                        "http.status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "error.type": error_type,
                        "trace_id": trace_id,
                        "span_id": span_id,
                    },
                )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "internal_error", "trace_id": trace_id},
                headers={"X-Trace-Id": trace_id},
            )

        active_span = trace.get_current_span()
        active_ctx = active_span.get_span_context() if active_span else None
        if active_ctx is not None and active_ctx.is_valid:
            trace_id = f"{active_ctx.trace_id:032x}"
        response.headers["X-Trace-Id"] = trace_id
        return response


def setup_telemetry(
    app: FastAPI,
    settings: Settings,
    *,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
    log_exporter: LogRecordExporter | None = None,
    engine: Engine | None = None,
    stdout_stream: TextIO | None = None,
) -> _TelemetryRuntime:
    """Configure OTel traces, metrics, logs, and auto-instrumentation."""
    shutdown_telemetry()

    if settings.otel_sdk_disabled:
        handlers = configure_logging(
            env=settings.app_env,
            logger_provider=None,
            stdout_stream=stdout_stream,
        )
        _runtime.enabled = False
        _runtime.env = settings.app_env
        _runtime.logging_handlers = handlers
        logger.info("OpenTelemetry SDK disabled by configuration", extra={"event": "telemetry.off"})
        return _runtime

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    # 1. Traces
    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is not None:
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    elif settings.otel_exporter_otlp_endpoint:
        traces_endpoint = build_otlp_signal_endpoint(settings.otel_exporter_otlp_endpoint, "traces")
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint))
        )

    if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
        trace.set_tracer_provider(tracer_provider)

    # 2. Metrics
    readers: list[MetricReader] = []
    if metric_reader is not None:
        readers.append(metric_reader)
    elif settings.otel_exporter_otlp_endpoint:
        metrics_endpoint = build_otlp_signal_endpoint(
            settings.otel_exporter_otlp_endpoint, "metrics"
        )
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=metrics_endpoint),
                export_interval_millis=15000,
            )
        )

    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    if isinstance(metrics.get_meter_provider(), metrics._internal._ProxyMeterProvider):
        metrics.set_meter_provider(meter_provider)

    # 3. Logs
    logger_provider = LoggerProvider(resource=resource)
    if log_exporter is not None:
        logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
    elif settings.otel_exporter_otlp_endpoint:
        logs_endpoint = build_otlp_signal_endpoint(settings.otel_exporter_otlp_endpoint, "logs")
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=logs_endpoint))
        )

    if isinstance(_logs.get_logger_provider(), _logs._internal.ProxyLoggerProvider):
        _logs.set_logger_provider(logger_provider)

    handlers = configure_logging(
        env=settings.app_env,
        logger_provider=logger_provider,
        stdout_stream=stdout_stream,
    )

    # 4. Instruments (low-cardinality metric labels only: result, env)
    meter = meter_provider.get_meter("sessionboard", settings.app_version)
    booking_counter = meter.create_counter(
        name="sessionboard.bookings",
        unit="1",
        description="Total booking attempts segmented by outcome and environment.",
    )
    booking_duration_histogram = meter.create_histogram(
        name="sessionboard.booking.duration",
        unit="s",
        description="Latency of POST /api/sessions booking operations in seconds.",
        explicit_bucket_boundaries_advisory=_SECONDS_BUCKETS,
    )

    # 5. Framework & ORM Auto-instrumentation
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    target_engine = engine or app_db.engine
    SQLAlchemyInstrumentor().instrument(
        engine=target_engine,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        enable_commenter=False,
    )

    _runtime.enabled = True
    _runtime.env = settings.app_env
    _runtime.tracer_provider = tracer_provider
    _runtime.meter_provider = meter_provider
    _runtime.logger_provider = logger_provider
    _runtime.tracer = tracer_provider.get_tracer("sessionboard", settings.app_version)
    _runtime.booking_counter = booking_counter
    _runtime.booking_duration_histogram = booking_duration_histogram
    _runtime.instrumented_app = app
    _runtime.instrumented_engine = target_engine
    _runtime.logging_handlers = handlers

    logger.info(
        "OpenTelemetry configured for service=%s env=%s",
        settings.otel_service_name,
        settings.app_env,
        extra={"event": "telemetry.configured"},
    )
    return _runtime


def shutdown_telemetry() -> None:
    """Flush and tear down active OTel providers, instrumentations, and log handlers."""
    if _runtime.instrumented_app is not None:
        if getattr(_runtime.instrumented_app, "_is_instrumented_by_opentelemetry", False):
            FastAPIInstrumentor.uninstrument_app(_runtime.instrumented_app)
        _runtime.instrumented_app = None

    if _runtime.instrumented_engine is not None:
        SQLAlchemyInstrumentor().uninstrument()
        _runtime.instrumented_engine = None

    if _runtime.tracer_provider is not None:
        _runtime.tracer_provider.force_flush()
        _runtime.tracer_provider.shutdown()
        _runtime.tracer_provider = None

    if _runtime.meter_provider is not None:
        _runtime.meter_provider.force_flush()
        _runtime.meter_provider.shutdown()
        _runtime.meter_provider = None

    if _runtime.logger_provider is not None:
        _runtime.logger_provider.force_flush()
        _runtime.logger_provider.shutdown()
        _runtime.logger_provider = None

    if _runtime.logging_handlers:
        teardown_logging_handlers(_runtime.logging_handlers)
        _runtime.logging_handlers = []

    _runtime.enabled = False
    _runtime.tracer = trace.get_tracer("sessionboard")
    _runtime.booking_counter = None
    _runtime.booking_duration_histogram = None


def record_booking_outcome(
    *,
    result: str,
    status_code: int,
    duration_seconds: float,
    span: trace.Span | None = None,
    conflict_types: str = "",
    duration_minutes: int | None = None,
    room_id: int | None = None,
    specialist_id: int | None = None,
    error_type: str | None = None,
    trace_id_override: str | None = None,
    span_id_override: str | None = None,
) -> None:
    """Record zero-PII booking attributes on span, increment SLI metrics, and emit JSON log."""
    if span is not None and span.is_recording():
        span.set_attribute("booking.result", result)
        span.set_attribute("booking.conflict_types", conflict_types)
        if duration_minutes is not None:
            span.set_attribute("booking.duration_minutes", duration_minutes)
        if room_id is not None:
            span.set_attribute("booking.room_id", room_id)
        if specialist_id is not None:
            span.set_attribute("booking.specialist_id", specialist_id)
        if result == "error":
            span.set_status(Status(StatusCode.ERROR, error_type or "internal_error"))

    labels = {"result": result, "env": _runtime.env}
    if _runtime.booking_counter is not None:
        _runtime.booking_counter.add(1, attributes=labels)
    if _runtime.booking_duration_histogram is not None:
        _runtime.booking_duration_histogram.record(max(duration_seconds, 0.0), attributes=labels)

    log_level = (
        logging.ERROR
        if result == "error"
        else logging.WARNING
        if result in {"invalid", "not_found"}
        else logging.INFO
    )
    extra: dict[str, object] = {
        "event": "booking.completed",
        "env": _runtime.env,
        "http.route": "/api/sessions",
        "http.status_code": status_code,
        "booking.result": result,
    }
    if error_type is not None:
        extra["error.type"] = error_type
    if trace_id_override is not None:
        extra["trace_id"] = trace_id_override
    if span_id_override is not None:
        extra["span_id"] = span_id_override

    booking_logger.log(log_level, "Booking attempt finished with result=%s", result, extra=extra)
