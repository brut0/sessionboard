"""Unit tests for structured JSON logging and OTLP endpoint helpers."""

import json
import logging
from pathlib import Path

from app.logging_config import JsonLogFormatter
from app.telemetry import build_otlp_signal_endpoint


def test_build_otlp_signal_endpoint_variants() -> None:
    assert (
        build_otlp_signal_endpoint("https://otlp-gateway-prod-eu-west-2.grafana.net/otlp", "traces")
        == "https://otlp-gateway-prod-eu-west-2.grafana.net/otlp/v1/traces"
    )
    assert (
        build_otlp_signal_endpoint("http://otel-lgtm:4318/", "metrics")
        == "http://otel-lgtm:4318/v1/metrics"
    )
    assert (
        build_otlp_signal_endpoint("http://otel-lgtm:4318/v1/logs", "logs")
        == "http://otel-lgtm:4318/v1/logs"
    )


def test_json_log_formatter_required_keys_and_no_exception_secrets() -> None:
    formatter = JsonLogFormatter(env="dev")
    logger = logging.getLogger("app.test")

    try:
        raise RuntimeError("postgresql://user:supersecret@db:5432/prod PII-CANARY-7731")
    except RuntimeError as exc:
        record = logger.makeRecord(
            name="app.test",
            level=logging.ERROR,
            fn="test.py",
            lno=10,
            msg="Unhandled server error",
            args=(),
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "event": "request.unhandled_error",
                "http.route": "/api/sessions",
                "http.status_code": 500,
                "booking.result": "error",
                "trace_id": "a" * 32,
                "span_id": "b" * 16,
            },
        )

    formatted = formatter.format(record)
    assert "\n" not in formatted
    assert "supersecret" not in formatted
    assert "PII-CANARY" not in formatted

    data = json.loads(formatted)
    for key in (
        "ts",
        "level",
        "logger",
        "event",
        "msg",
        "trace_id",
        "span_id",
        "env",
        "http.route",
        "http.status_code",
        "booking.result",
    ):
        assert key in data, f"Missing key {key}"

    assert data["level"] == "ERROR"
    assert data["event"] == "request.unhandled_error"
    assert data["env"] == "dev"
    assert data["trace_id"] == "a" * 32
    assert data["span_id"] == "b" * 16
    assert data["booking.result"] == "error"


def test_grafana_dashboard_json_defines_sli_panels() -> None:
    dash_path = Path(__file__).resolve().parents[3] / "ops" / "grafana" / "dashboard.json"
    assert dash_path.exists(), f"Dashboard missing at {dash_path}"
    dashboard = json.loads(dash_path.read_text(encoding="utf-8"))
    panels = dashboard.get("panels", [])
    assert len(panels) >= 4
    raw_queries = json.dumps(panels)
    assert "sessionboard_bookings_total" in raw_queries
    assert "sessionboard_booking_duration_seconds_bucket" in raw_queries
    assert '{service_name=\\"sessionboard\\"' in raw_queries or "service_name" in raw_queries
