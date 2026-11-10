# SessionBoard — Project Constitution

> **Status:** Active (Phase 1)
> **Scope:** Governs all specification, architecture, implementation, testing, deployment, and operations work in this repository.

---

## 1. Mission & Product Identity

**SessionBoard** is a tiny, focused session scheduler for small studios (tutors, coaches, therapists) with 2–5 rooms and a handful of specialists. An administrator books sessions on a daily board, and the system refuses any booking that creates a conflict (same specialist, room, or client in an overlapping time interval).

---

## 2. Fixed Technology Stack

| Layer | Mandatory Choice | Rationale |
|---|---|---|
| **Backend Runtime** | Python **3.12**, managed exclusively via `uv` (`pyproject.toml` + `uv.lock`) | Deterministic builds, fast CI |
| **Web Framework** | FastAPI + Pydantic v2 + `pydantic-settings` | Native OpenAPI generation and validation |
| **Database & ORM** | PostgreSQL **16** + SQLAlchemy **2.x sync** ORM + **psycopg 3** (`psycopg[binary]`) | Sync avoids Windows event-loop quirks and simplifies testing with `TestClient` |
| **Migrations** | Alembic (`0001_initial` and forward-only expand/contract migrations) | `Base.metadata.create_all()` is strictly forbidden in application code |
| **Frontend** | React **19** + Vite + TypeScript + Tailwind CSS (no router, two state tabs) | Minimal surface area; served as static SPA by FastAPI in production |
| **API Client** | `openapi-typescript` + `openapi-fetch` generated from `specs/api/openapi.yaml` | Contract-first type safety; hand-written API types are forbidden |
| **Testing** | Backend: `pytest` + `testcontainers[postgres]` · Frontend: `Vitest` + React Testing Library + `MSW` | Real PostgreSQL for integration tests; zero external network dependencies |
| **Containers** | Multi-stage `Dockerfile` + `docker-compose.yml` (`db` + `app` + `otel-lgtm`) | Single-command local startup (`docker compose up --build` / `make up`) |
| **Hosting & DB** | Render Free Web Services (`sessionboard-dev`, `sessionboard-prod`, Existing Image from GHCR) + Neon Free PostgreSQL (separate projects for `dev` and `prod`) | 100% free tier ($0, no credit card) with isolated environments |
| **Observability** | OpenTelemetry SDK (traces, metrics, structured JSON logs with shared `trace_id`) → local `grafana/otel-lgtm` and Grafana Cloud Free OTLP | Full signal correlation without vendor lock-in |
| **On-Call Agent** | Grafana Alert Webhook → GitHub `repository_dispatch` → `.github/workflows/oncall.yml` (deterministic rollback + headless Gemini CLI fix PR) | Safe automated mitigation first, verified code fix second |

---

## 3. Core Engineering Principles

1. **Spec-First (SDD):**
   - No application or API code is written before its requirement exists in `specs/product-spec.md` and its contract exists in `specs/api/openapi.yaml`.
   - When implementation reveals a gap, update `specs/` first.
2. **Test-First (Strict TDD):**
   - Every task follows: **write failing test → verify fail → implement minimal code → verify pass → commit**.
   - Every Acceptance Criterion (`AC-*`) in `specs/product-spec.md` maps to at least one automated integration test named `test_ac_<story>_<n>_<slug>`.
3. **Pure Domain Layer:**
   - `backend/app/domain/` contains pure Python functions and frozen dataclasses (`time_utils.py`, `conflicts.py`).
   - `backend/app/domain/` must **never** import `sqlalchemy`, `fastapi`, or `pydantic`.
   - All time arithmetic uses **integer minutes since midnight** (`0..1440`), never `datetime.time` addition/subtraction.
4. **KISS & YAGNI (Hard Scope Boundary):**
   - Build only the 4 entities (`Specialist`, `Client`, `Room`, `Session`), 2 UI tabs (`Day Board`, `Directory`), and 14 API operations defined in the specification.
   - Features listed as Out of Scope in `specs/product-spec.md` §6 are permanently forbidden.
   - Developer productivity tooling (such as `tools/ai-sdlc/`) must stay completely decoupled from SessionBoard's FastAPI contract, React bundle, and production `Dockerfile`.
5. **Privacy & Zero-PII Telemetry:**
   - Never record specialist names, client display names, room names, request bodies, headers, or database credentials in spans, metrics, or log lines.
   - Telemetry attributes may only carry numeric IDs, durations, HTTP status codes, and fixed enum strings (`created`, `conflict`, `not_found`, `invalid`, `error`).
6. **English-Only & Clean-Room Hygiene:**
   - Every file, comment, commit message, issue, and pull request in this repository must be in English.
   - `scripts/check_repo_hygiene.py` enforces zero Cyrillic characters and zero matches against the forbidden-terms list in both working files and git history.
7. **Tracker Discipline:**
   - Every change maps to a GitHub Issue (`Refs: #<N>`, `Closes #<N>`), carries an `Agent: <role>-agent` commit trailer, and leaves start/finish evidence comments on the issue.

---

## 4. Global Definition of Done (DoD)

A task, pull request, or phase is **Done** only when all of the following hold:

- [ ] Linked to a specification section and (from Phase 2 onward) a GitHub Issue with start and completion comments from the executing agent.
- [ ] `specs/` and `specs/api/openapi.yaml` are updated first if behavior or schemas changed, and `test_openapi_contract.py` + `npm run gen:api` show zero drift.
- [ ] Automated tests covering all Acceptance Criteria of the task were written before implementation and pass via `make test`.
- [ ] Static checks pass with zero errors via `make lint` (`ruff check`, `ruff format --check`, `tsc --noEmit`).
- [ ] Repository hygiene check passes: `python scripts/check_repo_hygiene.py` outputs `OK: 0 violations`.
- [ ] Reviewed by the Reviewer agent against `.agents/roles/reviewer.md` with zero blocking findings.
- [ ] Affected documentation (`docs/architecture.md`, `docs/testing.md`, `docs/deployment.md`, `docs/observability.md`) is updated in the same change.
- [ ] At every phase gate or architectural change, `README.md` rubric status badges, command examples, and repository structure map are updated before declaring completion.
