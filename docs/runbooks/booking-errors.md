# Runbook: `BookingErrorRatioHigh` (`POST /api/sessions` 5xx Spike)

> **Alert Rule:** [`ops/grafana/alert-rule.json`](../../ops/grafana/alert-rule.json)
> **On-Call Workflow:** [`.github/workflows/oncall.yml`](../../.github/workflows/oncall.yml)
> **Telemetry Contract:** [`specs/nfr-observability.md`](../../specs/nfr-observability.md)

---

## 1. Alert Meaning

`BookingErrorRatioHigh` fires when the user-facing booking endpoint (`POST /api/sessions`) fails with HTTP 5xx errors (`result="error"`) at a ratio **above 20%** over a 5-minute window with at least 3 total booking attempts (`B >= 3 AND A / B > 0.2`) for 2 consecutive evaluation minutes.

Note that **409 Conflict** (`result="conflict"`) and **422 Validation** (`result="invalid"`) responses are excluded from `result="error"` because refusing double bookings and invalid slots is expected business behavior.

---

## 2. Immediate Mitigation (First 2 Minutes)

1. Confirm the active deployed commit on the affected environment:
   ```bash
   curl -fsS https://sessionboard-dev.onrender.com/api/version
   ```
2. Automated mitigation (triggered by `oncall.yml` or manually via Actions):
   - Identify the last healthy commit SHA on `main` whose image exists in GHCR (`ghcr.io/brut0/sessionboard:<sha>`).
   - Run **Actions -> Rollback Environment** (`rollback.yml`) with `env=dev` and `sha=<previous_sha>`.
   - **Never run destructive SQL or down-migrations.** Schema changes follow expand-contract compatibility (`docs/deployment.md`).

---

## 3. Diagnosis in Grafana Cloud

1. **Error Logs (Loki):**
   Query recent 5xx errors in Grafana Explore:
   ```logql
   {service_name="sessionboard"} | json | level="ERROR"
   ```
   Look for `event="request.unhandled_error"` or `event="booking.completed"` with `booking.result="error"` and check `error.type`, `http.route`, and `trace_id`.

2. **Distributed Traces (Tempo):**
   Search Tempo by `trace_id` from the error log or the HTTP `X-Trace-Id` header. Inspect the `POST /api/sessions` span, `booking.create` child attributes (`booking.duration_minutes`, `booking.room_id`), and SQLAlchemy database spans.

3. **Recent Diff Check:**
   Compare the failing deployed SHA against the rollback SHA:
   ```bash
   git log --oneline -5
   git diff <rollback_sha>..<failing_sha> -- backend/
   ```

---

## 4. Common Root Causes & Fix Invariants

### A. Time-Arithmetic Overflow (`ValueError: minute must be in 0..59`)
- **Symptom:** Requests starting at `:45` (or `:30`) with durations crossing an hour boundary fail with `500`, `error.type="ValueError"`.
- **Cause:** Someone replaced pure integer arithmetic in `backend/app/domain/time_utils.py` or `backend/app/routers/sessions.py` with `datetime.time(hour, minute + duration)`.
- **Required Fix (Constitution §3.3):** All session time math MUST use **integer minutes since midnight** (`end_min = start_min + duration_minutes`), never `datetime.time` addition. Restore/add a regression unit test covering `:45 + 30` (e.g., `10:45 + 30 = 11:15`) and verify zero `@pytest.mark.skip` markers remain.

### B. Unhandled Validation or DB Exception
- **Symptom:** `error.type="StatementError"` or `AttributeError` in `booking.create`.
- **Required Fix:** Reproduce in `backend/tests/` first (RED -> GREEN), keep `backend/app/domain/` free of SQLAlchemy/FastAPI imports, and preserve zero-PII logging (never log specialist/client/room names or `DATABASE_URL`).

---

## 5. Recovery Verification

1. Confirm all backend checks pass locally (`cd backend && uv run pytest -v`).
2. Merge the automated `oncall/incident-<n>` PR after CI turns green.
3. Verify `cd-dev.yml` deploys the fixed SHA and `synthetic_probe.py --mode once` succeeds (`3/3`, including `:45 + 30`).
4. Confirm `BookingErrorRatioHigh` transitions back to `Normal` in Grafana Alerting.
