# SessionBoard — Non-Functional Requirements & Observability Specification

> **Status:** Approved v1 (Phase 1)
> **Covers:** Course criteria 10 (Observability), 11 (Alerting on User Impact), and 12 (On-Call Agent).

---

## 1. Key User Journey Instrumented

The primary user journey is **Book a session (`POST /api/sessions`)**. Every booking attempt directly reflects user value: either a valid session is scheduled (`201`), a real double-booking is prevented (`409`), invalid user input is rejected (`422`/`404`), or the system fails (`500`).

---

## 2. Service Level Indicators (SLIs) & Objectives (SLOs)

| Metric / SLI | Definition | Production SLO | Dev Alert Threshold (Synthetic Traffic) |
|---|---|---|---|
| **Booking Availability (Success Ratio)** | `1 - (sum(increase(sessionboard_bookings_total{result="error"}[5m])) / sum(increase(sessionboard_bookings_total[5m])))` | **≥ 99.0%** over a rolling 7-day window | Alert `BookingErrorRatioHigh` fires when total bookings `B >= 3` in 5m and `error / total > 0.20` for 2m |
| **Booking Latency (p95)** | `histogram_quantile(0.95, sum(rate(sessionboard_booking_duration_seconds_bucket[5m])) by (le))` | **< 500 ms** (warm instance) | Dashboard panel in Grafana |

> **Why `409 Conflict` and `422` are NOT errors in the SLI:** Refusing a double booking (`result="conflict"`) or invalid time slot (`result="invalid"`) is the core expected business behavior of SessionBoard. Only unhandled server failures (`result="error"`, HTTP 5xx) represent broken user experience.

---

## 3. Telemetry Contract (Traces, Metrics, Structured Logs)

### 3.1 OpenTelemetry Resource Attributes
- `service.name = "sessionboard"`
- `service.version = <APP_VERSION>` (Git commit SHA injected at build time)
- `deployment.environment = <APP_ENV>` (`local`, `dev`, `prod`, `test`)

### 3.2 Distributed Traces (Tempo)
- FastAPI HTTP server spans and SQLAlchemy database spans are auto-instrumented.
- Every `POST /api/sessions` creates a child span named **`booking.create`** with attributes:
  - `booking.result`: enum string `"created" | "conflict" | "not_found" | "invalid" | "error"`
  - `booking.conflict_types`: comma-separated sorted string of conflict types (e.g. `"room,specialist"`, or `""` when none)
  - `booking.duration_minutes`: integer
  - `booking.room_id`: integer
  - `booking.specialist_id`: integer
- Every HTTP response includes the header `X-Trace-Id: <32-hex-char trace_id>`. When `OTEL_SDK_DISABLED=true` (unit tests), a deterministic fallback 32-hex trace ID is generated per request so the header and 500 error contract always work.

### 3.3 Metrics (Prometheus / Mimir)
To stay well inside the Grafana Cloud Free limit (10,000 active series), metric attributes are restricted to **low-cardinality enums only** (`result` and `env` — never IDs):
1. `sessionboard.bookings` (Counter) → exported as `sessionboard_bookings_total{result, env}`
2. `sessionboard.booking.duration` (Histogram, unit `s`) → exported as `sessionboard_booking_duration_seconds_{bucket,sum,count}{result, env}`

### 3.4 Structured Logs (Loki)
All application logs are emitted as single-line JSON to `stdout` and bridged to the OpenTelemetry LoggerProvider. Required JSON keys:
- `ts`: ISO-8601 UTC timestamp
- `level`: `"INFO" | "WARNING" | "ERROR"`
- `logger`: logger name
- `event`: machine-readable event name (e.g. `"booking.completed"`, `"request.unhandled_error"`)
- `msg`: static English summary
- `trace_id`: 32-char hex string matching the active span's trace ID
- `span_id`: 16-char hex string matching the active span ID
- `env`: `APP_ENV`
- `booking.result`: (on booking events) `"created" | "conflict" | "not_found" | "invalid" | "error"`

---

## 4. Zero-PII & Secret Protection Policy

1. **Forbidden in telemetry:** `Specialist.name`, `Specialist.specialty`, `Client.display_name`, `Room.name`, raw request bodies, query strings containing names, HTTP headers (`Authorization`, `Cookie`), and `DATABASE_URL`.
2. **Automated verification (`test_telemetry_no_pii.py`):**
   - Integration test creates entities with canary strings (`"PII-CANARY-SPEC-7731"`, `"PII-CANARY-CLIENT-7731"`, `"PII-CANARY-ROOM-7731"`), executes both a `201` booking and a `409` conflicting booking with in-memory span and log exporters enabled, and asserts that `"PII-CANARY"` does not appear anywhere in serialized spans or log records.

---

## 5. Alerting & On-Call Responder Specification

1. **Alert Rule (`ops/grafana/alert-rule.json`):**
   - Name: `BookingErrorRatioHigh`
   - Condition: `B >= 3` and `A / B > 0.2` over `[5m]`, evaluated every `1m`, `for: 2m`, `NoData: Normal`.
2. **Webhook Contact Point (`ops/grafana/contact-point-payload.tmpl`):**
   - Sends `POST https://api.github.com/repos/<owner>/sessionboard/dispatches` with `event_type: "grafana-alert"`.
3. **On-Call Workflow (`.github/workflows/oncall.yml`):**
   - **Step 1 (Track):** Opens a GitHub Issue labelled `incident,oncall,agent:oncall`.
   - **Step 2 (Mitigate):** Queries `$DEV_URL/api/version`, finds the previous healthy commit SHA on `main`, and triggers `rollback.yml` for `dev`.
   - **Step 3 (Diagnose & Fix):** Collects recent Loki `ERROR` logs and `git diff`, invokes headless Gemini CLI (`@google/gemini-cli`) with `.agents/roles/oncall.md` and `docs/runbooks/booking-errors.md` to add a failing regression test and fix the root cause in `backend/`.
   - **Step 4 (Verify & PR):** Runs `uv run pytest` deterministically; if green and `git diff` is non-empty, pushes branch `oncall/incident-<n>`, opens a PR (`Closes #<n>`), and enables auto-merge.
