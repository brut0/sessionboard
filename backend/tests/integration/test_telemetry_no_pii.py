"""Integration tests verifying full OTel instrumentation and zero PII leakage."""

import io
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.config import Settings
from app.db import get_db
from app.main import app
from app.models import Client, Room, Session, Specialist
from app.telemetry import setup_telemetry, shutdown_telemetry

CANARY_PREFIX = "PII-CANARY"
CANARY_SPEC = "PII-CANARY-SPEC-7731"
CANARY_SPECIALTY = "Therapy PII-CANARY-SPEC-7731"
CANARY_CLIENT = "PII-CANARY-CLIENT-7731"
CANARY_ROOM = "PII-CANARY-ROOM-7731"


@pytest.fixture
def telemetry_harness(db_session, db_engine, monkeypatch):
    """Set up real OTel in-memory spans, metrics, OTLP logs, and stdout JSON log stream."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    db_session.query(Session).delete()
    db_session.query(Specialist).delete()
    db_session.query(Client).delete()
    db_session.query(Room).delete()
    db_session.flush()

    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    log_exporter = InMemoryLogRecordExporter()
    stdout_buffer = io.StringIO()

    test_settings = Settings(
        app_env="test",
        app_version="test-sha-1234",
        otel_service_name="sessionboard",
        otel_exporter_otlp_endpoint=None,
        otel_sdk_disabled=False,
    )

    setup_telemetry(
        app,
        test_settings,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        log_exporter=log_exporter,
        engine=db_engine,
        stdout_stream=stdout_buffer,
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    try:
        yield {
            "client": client,
            "span_exporter": span_exporter,
            "metric_reader": metric_reader,
            "log_exporter": log_exporter,
            "stdout_buffer": stdout_buffer,
        }
    finally:
        app.dependency_overrides.clear()
        shutdown_telemetry()


def _collect_counter_totals(metrics_data, metric_name: str) -> dict[str, int | float]:
    counts: dict[str, int | float] = {}
    if metrics_data is None:
        return counts
    for resource_metric in metrics_data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                if metric.name == metric_name:
                    for point in metric.data.data_points:
                        attrs = dict(point.attributes)
                        assert set(attrs.keys()) == {"result", "env"}, (
                            f"Metric {metric_name} must only carry result and env, got {attrs}"
                        )
                        assert attrs["env"] == "test"
                        counts[str(attrs["result"])] = point.value
    return counts


def _collect_histogram_counts(metrics_data, metric_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if metrics_data is None:
        return counts
    for resource_metric in metrics_data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                if metric.name == metric_name:
                    for point in metric.data.data_points:
                        attrs = dict(point.attributes)
                        assert set(attrs.keys()) == {"result", "env"}, (
                            f"Metric {metric_name} must only carry result and env, got {attrs}"
                        )
                        assert attrs["env"] == "test"
                        counts[str(attrs["result"])] = point.count
    return counts


@pytest.mark.integration
def test_telemetry_instrumentation_and_zero_pii(telemetry_harness, monkeypatch):
    """Full telemetry correlation (trace/logs/metrics) across all outcomes with zero PII."""
    client: TestClient = telemetry_harness["client"]
    span_exporter: InMemorySpanExporter = telemetry_harness["span_exporter"]
    metric_reader: InMemoryMetricReader = telemetry_harness["metric_reader"]
    log_exporter: InMemoryLogRecordExporter = telemetry_harness["log_exporter"]
    stdout_buffer: io.StringIO = telemetry_harness["stdout_buffer"]

    # Seed entities with canary names
    spec_res = client.post(
        "/api/specialists", json={"name": CANARY_SPEC, "specialty": CANARY_SPECIALTY}
    )
    cl_res = client.post("/api/clients", json={"display_name": CANARY_CLIENT})
    rm_res = client.post("/api/rooms", json={"name": CANARY_ROOM})
    assert spec_res.status_code == 201
    assert cl_res.status_code == 201
    assert rm_res.status_code == 201

    spec_id = spec_res.json()["id"]
    cl_id = cl_res.json()["id"]
    rm_id = rm_res.json()["id"]
    today = date.today().isoformat()

    # Clear setup spans/logs before testing booking flows
    span_exporter.clear()
    log_exporter.clear()
    stdout_buffer.seek(0)
    stdout_buffer.truncate(0)

    # 1. Valid booking -> 201 created
    res_created = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec_id,
            "client_id": cl_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 60,
        },
    )
    assert res_created.status_code == 201
    created_trace_id = res_created.headers["X-Trace-Id"]
    assert len(created_trace_id) == 32

    # 2. Overlapping conflict on room + specialist -> 409 conflict
    cl2_id = client.post("/api/clients", json={"display_name": "PII-CANARY-CLIENT-2"}).json()["id"]
    res_conflict = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec_id,
            "client_id": cl2_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "10:15",
            "duration_minutes": 30,
        },
    )
    assert res_conflict.status_code == 409
    assert len(res_conflict.headers["X-Trace-Id"]) == 32

    # 3. Non-existent specialist -> 404 not_found
    res_not_found = client.post(
        "/api/sessions",
        json={
            "specialist_id": 999999,
            "client_id": cl_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "12:00",
            "duration_minutes": 30,
        },
    )
    assert res_not_found.status_code == 404

    # 4a. Domain invalid hours -> 422 invalid
    res_invalid_domain = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec_id,
            "client_id": cl_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "07:45",
            "duration_minutes": 30,
        },
    )
    assert res_invalid_domain.status_code == 422

    # 4b. Schema RequestValidationError -> 422 invalid
    res_invalid_schema = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec_id,
            "client_id": cl_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "not-a-time",
            "duration_minutes": 30,
        },
    )
    assert res_invalid_schema.status_code == 422

    # 5. Simulated unhandled 500 carrying canary string inside exception message -> 500 error
    def boom(*_args, **_kwargs):
        raise RuntimeError(f"Simulated crash {CANARY_CLIENT}")

    monkeypatch.setattr("app.routers.sessions.find_conflicts", boom)
    res_error = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec_id,
            "client_id": cl_id,
            "room_id": rm_id,
            "session_date": today,
            "start_time": "14:00",
            "duration_minutes": 30,
        },
    )
    assert res_error.status_code == 500
    error_body = res_error.json()
    assert error_body["detail"] == "internal_error"
    assert len(error_body["trace_id"]) == 32
    assert res_error.headers["X-Trace-Id"] == error_body["trace_id"]

    # --- Assert Spans ---
    finished_spans = span_exporter.get_finished_spans()
    booking_spans = [s for s in finished_spans if s.name == "booking.create"]
    assert len(booking_spans) == 6

    created_span = next(
        s for s in booking_spans if f"{s.context.trace_id:032x}" == created_trace_id
    )
    assert created_span.attributes["booking.result"] == "created"
    assert created_span.attributes["booking.conflict_types"] == ""
    assert created_span.attributes["booking.duration_minutes"] == 60
    assert created_span.attributes["booking.room_id"] == rm_id
    assert created_span.attributes["booking.specialist_id"] == spec_id

    conflict_span = next(
        s for s in booking_spans if s.attributes.get("booking.result") == "conflict"
    )
    assert conflict_span.attributes["booking.conflict_types"] == "room,specialist"

    error_span = next(s for s in booking_spans if s.attributes.get("booking.result") == "error")
    assert f"{error_span.context.trace_id:032x}" == error_body["trace_id"]

    # SQLAlchemy DB spans must be emitted as children
    assert any(
        s.attributes.get("db.system") or s.attributes.get("db.system.name") for s in finished_spans
    )

    # --- Assert Metrics ---
    metrics_data = metric_reader.get_metrics_data()
    booking_counts = _collect_counter_totals(metrics_data, "sessionboard.bookings")
    assert booking_counts == {
        "created": 1,
        "conflict": 1,
        "not_found": 1,
        "invalid": 2,
        "error": 1,
    }
    duration_counts = _collect_histogram_counts(metrics_data, "sessionboard.booking.duration")
    assert duration_counts == booking_counts

    # --- Assert Structured JSON Logs (stdout + OTLP) ---
    stdout_lines = [line for line in stdout_buffer.getvalue().splitlines() if line.strip()]
    parsed_stdout = [json.loads(line) for line in stdout_lines]
    booking_logs = [entry for entry in parsed_stdout if entry.get("event") == "booking.completed"]
    assert len(booking_logs) == 6

    matching_created_log = next(
        entry for entry in booking_logs if entry.get("trace_id") == created_trace_id
    )
    assert matching_created_log["booking.result"] == "created"
    assert matching_created_log["http.route"] == "/api/sessions"
    assert matching_created_log["http.status_code"] == 201
    assert matching_created_log["env"] == "test"
    assert len(matching_created_log["span_id"]) == 16

    otlp_logs = log_exporter.get_finished_logs()
    assert len(otlp_logs) >= 6
    assert any(
        f"{rec.log_record.trace_id:032x}" == created_trace_id
        and rec.log_record.attributes.get("booking.result") == "created"
        for rec in otlp_logs
    )

    # --- Zero-PII Verification Across All Exported Signals ---
    serialized_spans = json.dumps(
        [
            {
                "name": s.name,
                "attributes": dict(s.attributes or {}),
                "status": s.status.description,
                "events": [
                    {"name": e.name, "attributes": dict(e.attributes or {})} for e in s.events
                ],
            }
            for s in finished_spans
        ]
    )
    serialized_otlp_logs = json.dumps(
        [
            {
                "body": rec.log_record.body,
                "attributes": dict(rec.log_record.attributes or {}),
            }
            for rec in otlp_logs
        ]
    )

    assert CANARY_PREFIX not in serialized_spans
    assert CANARY_PREFIX not in stdout_buffer.getvalue()
    assert CANARY_PREFIX not in serialized_otlp_logs
