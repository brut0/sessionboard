# System Architecture

> **Status:** Approved v1 (Phase 2)
> **Source of truth for:** Component boundaries, layering rules, request/booking flows, and observability integration.

---

## 1. High-Level Component Diagram

```mermaid
flowchart LR
  Admin[Studio Administrator Browser] -->|HTTPS / Same-Origin| APP

  subgraph APP["Docker Container: sessionboard (Python 3.12 + FastAPI)"]
    SPA["React 19 SPA (app/static)"]
    API["FastAPI Routers (/api/*)"]
    DOM["Pure Domain Layer (app/domain/*)"]
    DB_LAYER["SQLAlchemy 2.x Sync + psycopg 3 (app/db.py, app/models.py)"]
    OTEL["OpenTelemetry SDK (app/telemetry.py)"]

    SPA -->|openapi-fetch JSON| API
    API -->|pure dataclasses| DOM
    API -->|Session transaction| DB_LAYER
    API -. spans / metrics / JSON logs .-> OTEL
  end

  DB_LAYER -->|TCP 5432 / TLS| PG[(PostgreSQL 16: Local Container / Neon Cloud)]
  OTEL -->|OTLP HTTP 4318| LGTM["Grafana Stack (Local otel-lgtm / Grafana Cloud)"]
  LGTM -->|Webhook repository_dispatch| GH["GitHub Actions (oncall.yml)"]
  GH -->|1. Rollback + 2. Gemini CLI Fix PR| CD["GitHub Actions CD (cd-dev.yml / deploy-prod.yml)"]
  CD -->|Deploy Hook + imgURL| APP
```

---

## 2. Strict Layering & Dependency Rules

| Layer | Files | Allowed Imports | Forbidden Imports |
|---|---|---|---|
| **Domain (Pure)** | `backend/app/domain/time_utils.py`, `backend/app/domain/conflicts.py` | Python stdlib (`dataclasses`, `typing`) | `sqlalchemy`, `fastapi`, `pydantic`, `app.models`, `app.db`, `app.schemas` |
| **Schemas (DTOs)** | `backend/app/schemas.py` | `pydantic`, `datetime`, `app.domain.time_utils` | `sqlalchemy`, `fastapi`, `app.models`, `app.db` |
| **Persistence (ORM)** | `backend/app/db.py`, `backend/app/models.py` | `sqlalchemy`, `psycopg`, `app.config` | `fastapi`, `app.api` |
| **API / Transport** | `backend/app/api/{system,directory,sessions}.py`, `backend/app/main.py` | `fastapi`, `sqlalchemy`, `app.schemas`, `app.models`, `app.domain`, `app.telemetry` | Direct raw SQL outside advisory lock / health probe |
| **Frontend UI** | `frontend/src/{pages,components,api}/` | `openapi-fetch`, generated `src/api/schema.d.ts`, React 19 | Hand-written API request/response interfaces |

---

## 3. Booking Sequence Diagram (`POST /api/sessions`)

```mermaid
sequenceDiagram
  autonumber
  participant UI as React BookingModal
  participant API as FastAPI /api/sessions
  participant DOM as app/domain/conflicts.py
  participant PG as PostgreSQL 16
  participant OTEL as OTel Tracer & Meter

  UI->>API: POST /api/sessions (SessionCreate JSON)
  API->>API: Pydantic validates BR-1 (08:00-20:00) & BR-2 (15-min step, 15..180m)
  alt Validation fails (BR-1 / BR-2)
    API->>OTEL: bookings_total{result="invalid"}++
    API-->>UI: 422 Unprocessable Entity + X-Trace-Id
  else Input valid
    API->>OTEL: Start child span "booking.create"
    API->>PG: BEGIN TRANSACTION
    API->>PG: SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))
    API->>PG: Verify specialist_id, client_id, room_id exist
    alt Any referenced resource missing
      API->>PG: ROLLBACK
      API->>OTEL: span booking.result="not_found", bookings_total{result="not_found"}++
      API-->>UI: 404 {"detail": "not_found"} + X-Trace-Id
    else All resources exist
      API->>PG: SELECT sessions WHERE session_date = :d AND status != 'cancelled' AND (specialist_id=:s OR room_id=:r OR client_id=:c)
      API->>DOM: find_conflicts(new_slot, existing_slots)
      alt Conflicts found (BR-4)
        API->>PG: ROLLBACK
        API->>OTEL: span booking.result="conflict", bookings_total{result="conflict"}++
        API-->>UI: 409 {"detail": "conflict", "conflicts": [...]} + X-Trace-Id
      else Zero conflicts
        API->>PG: INSERT INTO sessions (...) RETURNING id
        API->>PG: COMMIT
        API->>OTEL: span booking.result="created", bookings_total{result="created"}++
        API-->>UI: 201 Created (Session JSON) + X-Trace-Id
      end
    end
  end
```

---

## 4. Static SPA Serving & Single-Container Topology

In production and `docker compose up --build`, the React 19 frontend is built in Stage 1 of the `Dockerfile` (`node:22-alpine`) and copied into `/app/backend/app/static`. FastAPI mounts `/assets` via `StaticFiles` and serves `index.html` at `/` (and any non-`/api` GET path), eliminating CORS issues in production and allowing the entire application to deploy as a single container image on Render Free.
