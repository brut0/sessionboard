# System Architecture

> **Status:** Approved v1 (Phase 2)
> **Interactive Explorer:** Open [`docs/architecture-explorer.html`](architecture-explorer.html) in any browser for an interactive, multi-mode Archify-style diagram viewer (with upstream/downstream node tracing, dark/light theme toggle, and animated flow playback).
> **Source of truth for:** Component boundaries, layering rules, request/booking flows, database schema, CI/CD promotion, and on-call remediation.

---

## 1. Executive Summary (Conclusion First)

**SessionBoard** is engineered around four architectural invariants:
1. **Single-Container Topology (`ADR-0001`):** A multi-stage `Dockerfile` builds the React 19 + TypeScript SPA in Node 22 and embeds the compiled static assets into the Python 3.12 + FastAPI runtime container (`backend/app/static`). FastAPI serves both `/api/*` and the SPA on a single port (`${PORT:-8000}`), eliminating cross-origin issues and cutting cloud compute usage in half.
2. **Pure Domain + Date-Scoped Advisory Locks (`ADR-0003`):** Interval conflict detection (`backend/app/domain/conflicts.py`) is 100% pure Python operating on integer minutes since midnight (`0..1440`). Concurrent bookings on the same date are serialized inside PostgreSQL 16 via `SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))`, preventing race-condition double bookings without locking unrelated dates.
3. **Contract-First Type Safety:** `specs/api/openapi.yaml` (OpenAPI 3.1) is authored before code. Backend routes are verified against it via `test_openapi_contract.py`, and frontend TypeScript types are generated automatically via `openapi-typescript` + `openapi-fetch`.
4. **Zero-PII Observability & Rollback-First On-Call (`ADR-0002`):** Every booking emits correlated OpenTelemetry traces (`booking.create`), low-cardinality Prometheus metrics (`sessionboard_bookings_total{result,env}`), and JSON logs sharing `trace_id` (`X-Trace-Id` response header) with zero personal names. When Grafana's `BookingErrorRatioHigh` alert fires, GitHub Actions (`oncall.yml`) **deterministically rolls back `dev` first**, and then invokes headless **Gemini CLI** to author a regression test and fix PR gated by `pytest`.

---

## 2. Runtime & Cloud Topology Diagram

```mermaid
flowchart LR
  Admin["👤 Studio Admin<br/>(Browser)"] -->|HTTPS :8000| SPA

  subgraph APP["🐳 Docker Container: sessionboard (Render Free / Local Compose)"]
    direction TB
    SPA["⚛️ React 19 SPA<br/>(DayBoard · BookingModal · Directory)"]
    API["⚡ FastAPI Routers<br/>(/api/sessions · /api/specialists · /api/rooms)"]
    DOM["🧠 Pure Domain Engine<br/>(time_utils.py · conflicts.py)"]
    ORM["🗄️ SQLAlchemy 2.x Sync<br/>(psycopg 3 · Alembic 0001)"]
    OTEL["📡 OpenTelemetry SDK<br/>(Tracer · Meter · JSON Logger)"]

    SPA -->|"openapi-fetch JSON"| API
    API -->|"Slot dataclasses (minutes)"| DOM
    API -->|"Transaction + Advisory Lock"| ORM
    API -. "booking.create span + metrics + logs" .-> OTEL
  end

  ORM -->|"TCP 5432 / TLS"| PG[("🐘 PostgreSQL 16<br/>(Local Container / 2× Neon Projects)")]
  OTEL -->|"OTLP HTTP 4318"| LGTM["📊 Grafana Stack<br/>(Tempo · Loki · Mimir · Alerting)"]
  LGTM -->|"Webhook repository_dispatch"| ONCALL["🤖 GitHub Actions: oncall.yml<br/>(1. Rollback · 2. Gemini CLI Fix PR)"]
  ONCALL -->|"Render Deploy Hook (&imgURL=)"| APP

  subgraph SDLC["🛠️ Optional Decoupled Companion: sessionboard-ai-sdlc (:8090 / Render Free)"]
    OWNER["🔐 Owner Passphrase<br/>(Signed __Host- Cookie / Bearer)"] --> WB["AI SDLC Web Workbench<br/>(LLM API + Hygiene + Git/PR)"]
  end
  OWNER -. "Local --profile sdlc / Cloud GHCR" .-> APP
```

---

## 3. Strict Layering & Dependency Matrix

| Layer | Directory / Files | Allowed Imports | Forbidden Imports (Enforced by Review & Tests) |
|---|---|---|---|
| **1. Pure Domain** | `backend/app/domain/time_utils.py`<br/>`backend/app/domain/conflicts.py` | Python stdlib only (`dataclasses`, `typing`) | `sqlalchemy`, `fastapi`, `pydantic`, `app.models`, `app.db`, `app.schemas` |
| **2. DTO Schemas** | `backend/app/schemas.py` | `pydantic`, `datetime`, `app.domain.time_utils` | `sqlalchemy`, `fastapi`, `app.models`, `app.db` |
| **3. Persistence (ORM)** | `backend/app/db.py`<br/>`backend/app/models.py`<br/>`backend/app/seed.py` | `sqlalchemy`, `psycopg`, `app.config` | `fastapi`, `app.api` |
| **4. API / Transport** | `backend/app/api/{system,directory,sessions}.py`<br/>`backend/app/main.py` | `fastapi`, `sqlalchemy`, `app.schemas`, `app.models`, `app.domain`, `app.telemetry` | Raw SQL outside advisory lock and `/api/health` probe |
| **5. Frontend UI** | `frontend/src/{pages,components,api}/` | `react`, `openapi-fetch`, generated `src/api/schema.d.ts` | Hand-written API request/response TypeScript interfaces |

---

## 4. Atomic Booking & Conflict Detection Sequence (`POST /api/sessions`)

```mermaid
sequenceDiagram
  autonumber
  participant UI as React BookingModal
  participant API as FastAPI /api/sessions
  participant DOM as app/domain/conflicts.py
  participant PG as PostgreSQL 16
  participant OTEL as OpenTelemetry SDK

  UI->>API: POST /api/sessions (SessionCreate JSON)
  API->>API: Pydantic validates BR-1 (08:00–20:00) & BR-2 (15m step, 15..180m)
  alt Schema or BR-1 / BR-2 violation
    API->>OTEL: sessionboard_bookings_total{result="invalid"}++
    API-->>UI: 422 Unprocessable Entity + Header X-Trace-Id
  else Input valid
    API->>OTEL: Start child span "booking.create"
    API->>PG: BEGIN TRANSACTION
    API->>PG: SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))
    API->>PG: Verify specialist_id, client_id, room_id exist
    alt Any referenced resource does not exist
      API->>PG: ROLLBACK
      API->>OTEL: span booking.result="not_found", bookings_total{result="not_found"}++
      API-->>UI: 404 {"detail": "not_found"} + Header X-Trace-Id
    else All resources exist
      API->>PG: SELECT sessions WHERE session_date = :d AND status != 'cancelled' AND (specialist_id=:s OR room_id=:r OR client_id=:c)
      API->>DOM: find_conflicts(new_slot, existing_slots)
      alt Conflicts detected (BR-4)
        API->>PG: ROLLBACK
        API->>OTEL: span booking.result="conflict", bookings_total{result="conflict"}++
        API-->>UI: 409 {"detail": "conflict", "conflicts": [...]} + Header X-Trace-Id
      else Zero conflicts
        API->>PG: INSERT INTO sessions (...) RETURNING id
        API->>PG: COMMIT
        API->>OTEL: span booking.result="created", bookings_total{result="created"}++, JSON log "booking.completed"
        API-->>UI: 201 Created (Session JSON) + Header X-Trace-Id
      end
    end
  end
```

---

## 5. Session Lifecycle State Machine (`US-4`, `BR-5`)

```mermaid
stateDiagram-v2
  [*] --> planned : POST /api/sessions (201 Created)<br/>Blocks overlapping specialist, room & client slots

  planned --> done : PATCH /api/sessions/{id} {"status": "done"} (200 OK)<br/>Preserved in history; continues to block overlaps
  planned --> cancelled : PATCH /api/sessions/{id} {"status": "cancelled"} (200 OK)<br/>Immediately releases specialist, room & client slots

  done --> done : Any PATCH -> 409 invalid_status_transition
  cancelled --> cancelled : Any PATCH -> 409 invalid_status_transition
```

---

## 6. CI/CD Promotion, Rollback & Self-Healing On-Call Pipeline

```mermaid
flowchart TD
  PR["Pull Request Opened"] --> CI["ci.yml: hygiene + ruff + pytest (testcontainers) + vitest + docker build"]
  CI -->|"All 4 checks green + Reviewer Agent approve"| MERGE["Squash Merge to main"]
  MERGE --> CD_DEV["cd-dev.yml: Push ghcr.io/brut0/sessionboard:<sha> -> Render Dev Hook -> Smoke Probe"]
  CD_DEV -->|"Manual workflow_dispatch + production approval"| CD_PROD["deploy-prod.yml: Render Prod Hook -> Read-Only Smoke"]

  PROBE["synthetic-probe.yml (Hourly / Burst)"] -->|"POST & cancel bookings on dev"| DEV_APP["sessionboard-dev (Render)"]
  DEV_APP -->|"OTLP metrics & logs"| GRAFANA["Grafana Cloud Alert: BookingErrorRatioHigh (B>=3 & error/B > 0.2)"]
  GRAFANA -->|"Webhook repository_dispatch (grafana-alert)"| ONCALL["oncall.yml Responder Workflow"]

  ONCALL --> STEP1["1. Open [incident] Issue (#N)"]
  STEP1 --> STEP2["2. Deterministic Mitigation: Trigger rollback.yml on dev to previous healthy SHA"]
  STEP2 --> STEP3["3. Collect Loki ERROR logs + git diff -> Run Headless Gemini CLI (.agents/roles/oncall.md)"]
  STEP3 --> STEP4{"4. Deterministic Gate:<br/>uv run pytest green & diff non-empty?"}
  STEP4 -->|"Yes"| STEP5["5. Push branch oncall/incident-N -> Open PR (Closes #N) -> Enable Auto-Merge"]
  STEP4 -->|"No"| STEP6["Comment on Issue: Mitigated by rollback; human review needed"]
  STEP5 --> CI
```

---

## 7. Architecture Decision Records (ADRs)

| ADR | Title | Key Decision |
|---|---|---|
| [`docs/adr/0001-stack.md`](adr/0001-stack.md) | Core Technology Stack & Single-Container Topology | FastAPI + React 19 SPA compiled into one container image; contract-first OpenAPI client generation. |
| [`docs/adr/0002-hosting-and-telemetry.md`](adr/0002-hosting-and-telemetry.md) | Zero-Cost Cloud Hosting, Telemetry Stack & Headless On-Call | Render Free + 2 isolated Neon Free projects + Grafana Cloud Free + rollback-first headless Gemini CLI responder. |
| [`docs/adr/0003-sync-sqlalchemy.md`](adr/0003-sync-sqlalchemy.md) | Synchronous SQLAlchemy 2.x with `psycopg 3` & Date Advisory Locks | Sync engine avoids Windows async event-loop issues; transaction-scoped `pg_advisory_xact_lock` prevents race-condition double bookings. |
