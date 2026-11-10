"""Structured zero-PII JSON logging configuration and OTel log handler bridge."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO

from opentelemetry import trace
from opentelemetry._logs import LoggerProvider
from opentelemetry.instrumentation.logging.handler import LoggingHandler

_EXTRA_SAFE_FIELDS = ("http.route", "http.status_code", "booking.result", "error.type")


class JsonLogFormatter(logging.Formatter):
    """Render single-line JSON log records without stack traces or request secrets."""

    def __init__(self, env: str = "local") -> None:
        super().__init__()
        self.env = env

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx is not None and ctx.is_valid:
            trace_id = f"{ctx.trace_id:032x}"
            span_id = f"{ctx.span_id:016x}"
        else:
            trace_id = getattr(record, "trace_id", "0" * 32)
            span_id = getattr(record, "span_id", "0" * 16)

        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "app.log"),
            "msg": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
            "env": getattr(record, "env", self.env),
        }

        for field_name in _EXTRA_SAFE_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value

        # Record only the exception class name if exc_info was attached, never raw message/trace
        if record.exc_info and record.exc_info[0] is not None and "error.type" not in payload:
            payload["error.type"] = record.exc_info[0].__name__

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging(
    *,
    env: str,
    logger_provider: LoggerProvider | None = None,
    level: int = logging.INFO,
    stdout_stream: TextIO | None = None,
) -> list[logging.Handler]:
    """Attach structured JSON stdout logging and optional OTLP LoggingHandler to root logger."""
    root = logging.getLogger()
    root.setLevel(level)

    # Re-enable application loggers in case third-party logging config (e.g. Alembic) ran earlier
    for name, logger_obj in logging.Logger.manager.loggerDict.items():
        if name.startswith("app") and isinstance(logger_obj, logging.Logger):
            logger_obj.disabled = False
            logger_obj.propagate = True

    # Remove any previously managed handlers from SessionBoard to prevent duplicate emission
    for existing in list(root.handlers):
        if getattr(existing, "_sessionboard_managed", False):
            root.removeHandler(existing)

    formatter = JsonLogFormatter(env=env)
    managed_handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(stdout_stream or sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler._sessionboard_managed = True  # type: ignore[attr-defined]
    root.addHandler(stream_handler)
    managed_handlers.append(stream_handler)

    if logger_provider is not None:
        otel_handler = LoggingHandler(
            level=level,
            logger_provider=logger_provider,
            log_code_attributes=False,
        )
        otel_handler.setFormatter(formatter)
        otel_handler._sessionboard_managed = True  # type: ignore[attr-defined]
        root.addHandler(otel_handler)
        managed_handlers.append(otel_handler)

    # Keep OTel exporter internals quiet unless warnings/errors occur
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    return managed_handlers


def teardown_logging_handlers(handlers: list[logging.Handler]) -> None:
    """Detach SessionBoard-managed logging handlers from the root logger."""
    root = logging.getLogger()
    for handler in handlers:
        if handler in root.handlers:
            root.removeHandler(handler)
