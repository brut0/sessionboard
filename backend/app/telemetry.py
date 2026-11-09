"""OpenTelemetry initialization and trace correlation helpers."""

import logging
import uuid

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import Settings

logger = logging.getLogger(__name__)


def get_current_trace_id() -> str:
    """Return the active 32-hex trace ID or generate a fresh UUID4 hex string."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return f"{span.get_span_context().trace_id:032x}"
    return uuid.uuid4().hex


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Ensure every HTTP response carries an X-Trace-Id header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = get_current_trace_id()
        # Save trace_id in request state for error handlers
        request.state.trace_id = trace_id
        response = await call_next(request)
        # Update trace_id in case span was started during call_next
        active_trace_id = get_current_trace_id()
        is_blank = active_trace_id == "0" * 32
        response.headers["X-Trace-Id"] = trace_id if is_blank else active_trace_id
        return response


def setup_telemetry(app: FastAPI, settings: Settings) -> None:
    """Configure OpenTelemetry Tracer and FastAPI instrumentation."""
    if settings.otel_sdk_disabled:
        logger.info("OpenTelemetry SDK is disabled by configuration")
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTLP trace exporter configured for %s", endpoint)

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
