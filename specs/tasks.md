# SessionBoard — Task Breakdown & Acceptance Criteria Mapping

> **Status:** Approved v1 (Phase 2)
> **Source of truth for:** Implementation tasks `T01`–`T16`, role assignments, phase dependencies, and GitHub Issue mapping.

---

## 1. Tasks Table (`T01`–`T16`)

| Task ID | Issue | Title | Agent Role | Type Label | Phase | Spec & Contract References | Acceptance Criteria / Deliverables |
|---|---|---|---|---|---|---|---|
| **T01** | #2 | Repo skeleton: backend/frontend scaffolds, Makefile, compose, Dockerfile | `agent:devops` | `type:infra` | `phase:3` | `docs/plan/MASTER_PLAN.md` §6, §8, `specs/api/openapi.yaml` (`/api/health`, `/api/version`) | Multi-stage `Dockerfile`, `docker-compose.yml` (`db`, `app`, `otel-lgtm`), `Makefile` (`up`, `down`, `test`, `lint`), minimal FastAPI `/api/health` + `/api/version` and Vite React 19 shell. |
| **T02** | #3 | DB models, Alembic 0001 migration, and synthetic seed | `agent:backend` | `type:feature` | `phase:4` | `specs/data-model.md` §1–§4 | SQLAlchemy 2.x sync models (`Specialist`, `Client`, `Room`, `Session`), `0001_initial` Alembic migration, idempotent `app/seed.py`, `docker-entrypoint.sh`. |
| **T03** | #4 | Pure domain: time utils and conflict detection with unit tests | `agent:backend` | `type:feature` | `phase:4` | `specs/product-spec.md` (`BR-1`..`BR-4`), `docs/architecture.md` §2 | Pure `app/domain/time_utils.py` & `app/domain/conflicts.py` (no ORM/FastAPI imports, minutes since midnight) + table-driven `tests/unit/test_conflicts.py`. |
| **T04** | #5 | Studio Directory API (specialists, clients, rooms) | `agent:backend` | `type:feature` | `phase:4` | `specs/product-spec.md` (`US-1`, `BR-6`, `BR-7`, `BR-9`), `specs/api/openapi.yaml` | `GET`/`POST`/`DELETE` for `/api/specialists`, `/api/clients`, `/api/rooms` covering **AC-1.1**, **AC-1.2**, **AC-1.3**, **AC-1.4**, **AC-1.5**. |
| **T05** | #6 | Sessions API: create with advisory lock & conflict check, list by date, status transitions | `agent:backend` | `type:feature` | `phase:4` | `specs/product-spec.md` (`US-2`..`US-4`, `BR-1`..`BR-5`, `BR-8`), `specs/api/openapi.yaml` | `GET /api/sessions`, `POST /api/sessions` (with `pg_advisory_xact_lock`), `PATCH /api/sessions/{session_id}` covering **AC-2.1**..**AC-2.8**, **AC-3.1**, **AC-4.1**, **AC-4.2**. |
| **T06** | #7 | Backend integration test suite per AC + OpenAPI contract test | `agent:qa` | `type:test` | `phase:4` | `specs/product-spec.md` §5 (`AC-1.1`..`AC-4.2`), `specs/api/openapi.yaml` | `tests/integration/test_sessions_api.py` (16 AC tests via `testcontainers` Postgres), `tests/integration/test_openapi_contract.py`, `docs/testing.md`. |
| **T07** | #8 | Frontend shell, generated OpenAPI client, and tab navigation | `agent:frontend` | `type:feature` | `phase:5` | `docs/plan/MASTER_PLAN.md` §5, §6.3, `specs/api/openapi.yaml` | `npm run gen:api` (`src/api/schema.d.ts`), `src/api/client.ts` (`openapi-fetch`), two-tab header (`Day Board`, `Directory`). |
| **T08** | #9 | Day Board view and session status actions | `agent:frontend` | `type:feature` | `phase:5` | `specs/product-spec.md` (`US-3`, `US-4`, **AC-3.1**, **AC-4.1**, **AC-4.2**) | `DayBoard.tsx`: date picker, `Prev`/`Today`/`Next`, columns per room, session cards, `Done`/`Cancel` buttons, greyed cancelled cards. |
| **T09** | #10 | Booking Modal with 15-min pickers, 409 conflict display, and Trace ID error banner | `agent:frontend` | `type:feature` | `phase:5` | `specs/product-spec.md` (`US-2`, **AC-2.1**..**AC-2.7**), `docs/plan/MASTER_PLAN.md` §6.3 | `BookingModal.tsx`: selects for specialist/client/room, 15-min start time (`08:00`..`19:45`) & duration (`15`..`180`), human-readable 409 conflict lines, 5xx `Trace ID` display. |
| **T10** | #11 | Directory page (Specialists, Clients, Rooms CRUD & 409 messages) | `agent:frontend` | `type:feature` | `phase:5` | `specs/product-spec.md` (`US-1`, **AC-1.1**..**AC-1.5**) | `DirectoryPage.tsx`: 3 cards (Specialists, Clients, Rooms) with list, add form, delete button, and 409 error banners (`has_planned_sessions`, `room_name_taken`). |
| **T11** | #12 | Frontend component test suite (Vitest + RTL + MSW) | `agent:qa` | `type:test` | `phase:5` | `docs/plan/MASTER_PLAN.md` §7 | Component tests for `DayBoard`, `BookingModal` (409 conflict rendering), and `DirectoryPage` (409 delete error); `make test` runs both backend and frontend. |
| **T12** | #13 | GitHub Actions CI pipeline and branch protection | `agent:devops` | `type:infra` | `phase:6` | `docs/plan/MASTER_PLAN.md` §9 | `.github/workflows/ci.yml` (`hygiene`, `backend`, `frontend`, `docker` jobs), branch protection on `main`, auto-merge enabled. |
| **T13** | #14 | Cloud deployment (Render + Neon), CD workflows, and rollback workflow | `agent:devops` | `type:infra` | `phase:7` | `docs/plan/MASTER_PLAN.md` §9, `docs/adr/0002-hosting-and-telemetry.md` | `cd-dev.yml`, `deploy-prod.yml` (manual + `production` approval), `rollback.yml`, `docs/deployment.md`, verified rollback run on `dev`. |
| **T14** | #15 | OpenTelemetry instrumentation (traces, metrics, JSON logs), zero-PII test, and Grafana dashboard | `agent:backend` | `type:feature` | `phase:8` | `specs/nfr-observability.md` §1–§4 | `app/telemetry.py`, `app/logging_config.py`, `X-Trace-Id` middleware, `tests/integration/test_telemetry_no_pii.py`, `ops/grafana/dashboard.json`, `docs/observability.md`. |
| **T15** | #16 | Grafana alert rule, synthetic probe, on-call Gemini CLI responder workflow, and chaos drill | `agent:devops` | `type:infra` | `phase:9` | `specs/nfr-observability.md` §5, `docs/plan/MASTER_PLAN.md` §11–§12 | `scripts/synthetic_probe.py`, `synthetic-probe.yml`, `oncall.yml`, `docs/runbooks/booking-errors.md`, `ops/grafana/alert-rule.json`, `docs/oncall-demo.md`. |
| **T16** | #17 | Final README, AI tools documentation, fresh-clone verification, and submission checklist | `agent:spec` | `type:docs` | `phase:10` | `docs/plan/MASTER_PLAN.md` §2, §14 (Phase 10) | `README.md` (with 12-criterion grading table), `docs/ai-tools.md`, fresh clone verification. |

---

## 2. Acceptance Criteria → Tasks Traceability Matrix

| Acceptance Criterion | Implementing Task(s) | Verifying Test Task(s) |
|---|---|---|
| **AC-1.1** (Create & list directory entities sorted) | T02, T04, T10 | T06, T11 |
| **AC-1.2** (Reject blank/whitespace directory names — 422) | T04 | T06 |
| **AC-1.3** (Reject duplicate room name — 409 `room_name_taken`) | T02, T04, T10 | T06, T11 |
| **AC-1.4** (Delete unused entity 204 / missing 404) | T04, T10 | T06 |
| **AC-1.5** (Block delete with planned sessions — 409 `has_planned_sessions`) | T04, T10 | T06, T11 |
| **AC-2.1** (Valid booking within working hours — 201) | T03, T05, T09 | T03, T06, T11 |
| **AC-2.2** (Reject outside working hours 08:00–20:00 — 422) | T03, T05 | T03, T06 |
| **AC-2.3** (Reject non-15-min start or invalid duration — 422) | T03, T05 | T03, T06 |
| **AC-2.4** (Booking with missing specialist/client/room — 404) | T05 | T06 |
| **AC-2.5** (Detect room overlap conflict — 409) | T03, T05, T09 | T03, T06, T11 |
| **AC-2.6** (Detect specialist, client, and multi-resource overlap — 409) | T03, T05, T09 | T03, T06, T11 |
| **AC-2.7** (Allow back-to-back touching intervals — 201) | T03, T05 | T03, T06 |
| **AC-2.8** (Serialize concurrent bookings on same date — advisory lock) | T05 | T06 |
| **AC-3.1** (List sessions for date sorted by room_id, start_time) | T05, T08 | T06, T11 |
| **AC-4.1** (Transition `planned → done/cancelled`, reject invalid — 409/404) | T05, T08 | T06, T11 |
| **AC-4.2** (Cancelled frees slot; done still blocks overlaps) | T03, T05, T08 | T03, T06 |
