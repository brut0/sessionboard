"""Unit tests for Phase 9 probe, Grafana alert rule, runbook, and oncall workflow."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_synthetic_probe() -> ModuleType:
    probe_path = REPO_ROOT / "scripts" / "synthetic_probe.py"
    spec = importlib.util.spec_from_file_location("synthetic_probe", probe_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_synthetic_probe_every_third_slot_triggers_minute_overflow() -> None:
    probe = _load_synthetic_probe()
    assert hasattr(probe, "select_probe_slot"), "synthetic_probe must define select_probe_slot()"

    seen_day_slots: set[tuple[int, str]] = set()
    for iteration in range(1, 25):
        offset_days, start_time, duration_minutes = probe.select_probe_slot(iteration)
        assert offset_days >= 400
        hour, minute = (int(part) for part in start_time.split(":"))
        assert minute % 15 == 0
        assert duration_minutes % 15 == 0
        assert 15 <= duration_minutes <= 180
        assert 480 <= (hour * 60 + minute) and (hour * 60 + minute + duration_minutes) <= 1200

        if iteration % 3 == 0:
            assert start_time.endswith(":45"), (
                f"Iteration {iteration} must start at :45 to test overflow, got {start_time}"
            )
            assert duration_minutes == 30
            assert minute + duration_minutes >= 60
        else:
            assert minute + duration_minutes < 60, (
                f"Non-3rd iter {iteration} should avoid :45 overflow so baseline ratio ~33%"
            )

        assert (offset_days, start_time) not in seen_day_slots
        seen_day_slots.add((offset_days, start_time))


def test_synthetic_probe_defaults_and_exits_nonzero_on_5xx(monkeypatch) -> None:
    probe = _load_synthetic_probe()
    args = probe.parse_args([])
    assert args.mode == "once"
    assert args.minutes == 15
    assert args.interval == 10.0

    def fake_http(
        url: str,
        method: str = "GET",
        body: dict | None = None,
        headers: dict | None = None,
    ):
        if url.endswith("/api/health"):
            return 200, {"status": "ok", "db": "ok"}, {}
        if url.endswith("/api/version"):
            return 200, {"version": "deadbeef", "env": "dev"}, {}
        if method == "GET" and url.endswith("/api/specialists"):
            return 200, [{"id": 1, "name": "Probe Specialist"}], {}
        if method == "GET" and url.endswith("/api/clients"):
            return 200, [{"id": 2, "display_name": "Probe Client"}], {}
        if method == "GET" and url.endswith("/api/rooms"):
            return 200, [{"id": 3, "name": "Probe Room"}], {}
        if method == "POST" and url.endswith("/api/sessions"):
            if body and body["start_time"].endswith(":45"):
                return (
                    500,
                    {"detail": "internal_error", "trace_id": "a" * 32},
                    {"x-trace-id": "a" * 32},
                )
            return 201, {"id": 99}, {"x-trace-id": "b" * 32}
        if method == "PATCH" and "/api/sessions/" in url:
            return 200, {"id": 99, "status": "cancelled"}, {}
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(probe, "http_request", fake_http)
    monkeypatch.setattr(probe.time, "sleep", lambda *_a, **_kw: None)
    exit_code = probe.run_probe_suite(
        "http://example.test",
        mode="once",
        burst_minutes=1,
        interval_seconds=0.0,
    )
    assert exit_code == 1


def test_synthetic_probe_once_happy_path_and_burst_mode(monkeypatch) -> None:
    probe = _load_synthetic_probe()
    recorded_starts: list[str] = []

    def make_fake_http(*, fail_on_45: bool, clock: dict[str, float] | None = None):
        def fake_http(
            url: str,
            method: str = "GET",
            body: dict | None = None,
            headers: dict | None = None,
        ):
            if url.endswith("/api/health"):
                return 200, {"status": "ok", "db": "ok"}, {}
            if url.endswith("/api/version"):
                return 200, {"version": "deadbeef", "env": "dev"}, {}
            if method == "GET" and url.endswith("/api/specialists"):
                return 200, [{"id": 1, "name": "Probe Specialist"}], {}
            if method == "GET" and url.endswith("/api/clients"):
                return 200, [{"id": 2, "display_name": "Probe Client"}], {}
            if method == "GET" and url.endswith("/api/rooms"):
                return 200, [{"id": 3, "name": "Probe Room"}], {}
            if method == "POST" and url.endswith("/api/sessions"):
                assert body is not None
                recorded_starts.append(str(body["start_time"]))
                if clock is not None:
                    clock["now"] += 20.0
                if fail_on_45 and str(body["start_time"]).endswith(":45"):
                    return (
                        500,
                        {"detail": "internal_error", "trace_id": "a" * 32},
                        {"x-trace-id": "a" * 32},
                    )
                return 201, {"id": 99}, {"x-trace-id": "b" * 32}
            if method == "PATCH" and "/api/sessions/" in url:
                return 200, {"id": 99, "status": "cancelled"}, {}
            raise AssertionError(f"Unexpected request: {method} {url}")

        return fake_http

    monkeypatch.setattr(probe.time, "sleep", lambda *_a, **_kw: None)

    # Healthy once mode executes 3 lifecycles including a :45 slot and returns 0
    monkeypatch.setattr(probe, "http_request", make_fake_http(fail_on_45=False))
    once_exit = probe.run_probe_suite(
        "http://example.test",
        mode="once",
        burst_minutes=1,
        interval_seconds=0.0,
    )
    assert once_exit == 0
    assert len(recorded_starts) == 3
    assert recorded_starts[-1].endswith(":45")

    # Healthy burst mode executes 3 iterations (0 -> 20 -> 40 -> 60s) and returns 0
    recorded_starts.clear()
    healthy_clock = {"now": 1_800_000_000.0}
    monkeypatch.setattr(probe.time, "time", lambda: healthy_clock["now"])
    monkeypatch.setattr(
        probe,
        "http_request",
        make_fake_http(fail_on_45=False, clock=healthy_clock),
    )
    burst_ok_exit = probe.run_probe_suite(
        "http://example.test",
        mode="burst",
        burst_minutes=1,
        interval_seconds=0.0,
    )
    assert burst_ok_exit == 0
    assert len(recorded_starts) == 3
    assert recorded_starts[-1].endswith(":45")

    # Burst mode with 5xx on every 3rd (:45) booking returns exit code 1
    recorded_starts.clear()
    failing_clock = {"now": 1_800_000_000.0}
    monkeypatch.setattr(probe.time, "time", lambda: failing_clock["now"])
    monkeypatch.setattr(
        probe,
        "http_request",
        make_fake_http(fail_on_45=True, clock=failing_clock),
    )
    burst_fail_exit = probe.run_probe_suite(
        "http://example.test",
        mode="burst",
        burst_minutes=1,
        interval_seconds=0.0,
    )
    assert burst_fail_exit == 1
    assert len(recorded_starts) == 3


def test_grafana_alert_rule_and_contact_point_template_valid() -> None:
    alert_path = REPO_ROOT / "ops" / "grafana" / "alert-rule.json"
    tmpl_path = REPO_ROOT / "ops" / "grafana" / "contact-point-payload.tmpl"
    assert alert_path.exists(), f"Missing {alert_path}"
    assert tmpl_path.exists(), f"Missing {tmpl_path}"

    alert_rule = json.loads(alert_path.read_text(encoding="utf-8"))
    raw_alert = json.dumps(alert_rule)
    assert alert_rule["title"] == "BookingErrorRatioHigh"
    assert alert_rule["noDataState"] == "OK"
    assert alert_rule["for"] == "2m"
    assert alert_rule["labels"]["service"] == "sessionboard"
    assert alert_rule["labels"]["env"] == "dev"
    assert alert_rule["labels"]["severity"] == "page"
    assert "docs/runbooks/booking-errors.md" in alert_rule["annotations"]["runbook_url"]
    assert "sessionboard_bookings_total" in raw_alert
    assert 'result="error"' in raw_alert or 'result=\\"error\\"' in raw_alert
    assert "$B >= 3" in raw_alert
    assert "0.2" in raw_alert

    tmpl = tmpl_path.read_text(encoding="utf-8")
    for token in (
        "grafana-alert",
        "event_type",
        "client_payload",
        ".Status",
        ".CommonLabels.alertname",
        ".CommonLabels.env",
        ".CommonAnnotations.summary",
    ):
        assert token in tmpl


def test_runbook_and_oncall_workflow_contract() -> None:
    runbook_path = REPO_ROOT / "docs" / "runbooks" / "booking-errors.md"
    workflow_path = REPO_ROOT / ".github" / "workflows" / "oncall.yml"
    assert runbook_path.exists(), f"Missing {runbook_path}"
    assert workflow_path.exists(), f"Missing {workflow_path}"

    runbook = runbook_path.read_text(encoding="utf-8")
    assert "BookingErrorRatioHigh" in runbook
    assert "rollback.yml" in runbook
    assert '{service_name="sessionboard"}' in runbook
    assert "minutes since midnight" in runbook.lower()

    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    on_block = workflow.get("on") or workflow.get(True)
    assert "repository_dispatch" in on_block
    assert "grafana-alert" in on_block["repository_dispatch"]["types"]
    assert workflow["concurrency"]["group"] == "oncall"

    raw_workflow = workflow_path.read_text(encoding="utf-8")
    for required in (
        "ONCALL_GH_TOKEN",
        "ONCALL_TOKEN",
        "FORBIDDEN_TERMS",
        "GEMINI_API_KEY",
        "GEMINI_CLI_TRUST_WORKSPACE",
        "GRAFANA_LOGS_URL",
        "GRAFANA_LOGS_USER",
        "GRAFANA_LOGS_TOKEN",
        "rollback.yml",
        "@google/gemini-cli",
        "--yolo",
        "--skip-trust",
        "uv run ruff check",
        "uv run pytest",
        "oncall/incident-",
        "gh pr merge",
        "resolved",
    ):
        assert required in raw_workflow, f"Missing {required!r} in oncall.yml"

    assert 'if [ -z "${{ secrets.ONCALL_GH_TOKEN }}" ]' not in raw_workflow
    oncall_role = (REPO_ROOT / ".agents" / "roles" / "oncall.md").read_text(encoding="utf-8")
    assert "uv run ruff" in oncall_role

    # Verify embedded Python script parses cleanly with zero YAML indentation corruption
    py_script = workflow["jobs"]["mitigate-and-fix"]["steps"][4]["run"]
    marker = "python3 - <<'PY'\n"
    assert marker in py_script
    embedded_py = py_script.split(marker, 1)[1].split("\nPY", 1)[0]
    ast.parse(embedded_py)
