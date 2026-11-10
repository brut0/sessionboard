# AGENTS.md

SessionBoard is a tiny session scheduler for small studios: an administrator books sessions on a
daily board and the system refuses double bookings (same specialist, room, or client).
Stack: FastAPI + SQLAlchemy (sync, psycopg 3) + PostgreSQL 16 + React 19/Vite/TypeScript, Docker Compose,
GitHub Actions, Render, Neon, OpenTelemetry + Grafana.

## Read before any change
| Need | Document |
|---|---|
| How the project is built, phases, gates, pitfalls | `docs/plan/MASTER_PLAN.md` |
| How a human runs the agents in Antigravity | `docs/plan/EXECUTION_GUIDE.md` |
| Principles and Definition of Done | `specs/constitution.md` (Phase 1) |
| What to build (source of truth) | `specs/product-spec.md`, `specs/api/openapi.yaml` (Phases 1–2) |
| Process: issues, branches, commits, PRs | `docs/process.md` |
| Agent roles and hand-offs | `docs/agents/team.md`, role prompts in `.agents/roles/` |
| Architecture | `docs/architecture.md` (Phase 2) |
| Testing | `docs/testing.md` (Phase 4) |
| Deploy and rollback | `docs/deployment.md` (Phase 7) |
| Pre-Phase-8 cloud & telemetry checklist | `docs/plan/PRE_PHASE_8_HUMAN_CHECKLIST.md` |
| Adding new features via AI SDLC (Chat + Web UI) | `docs/ai-sdlc.md`, `.agents/skills/feature-sdlc/SKILL.md` |
| Telemetry | `docs/observability.md` (Phase 8) |
| Incidents | `docs/runbooks/` (Phase 9) |

Files marked with a phase do not exist until that phase is done. If you need one earlier, you are in the wrong phase.

## Commands
- `docker compose up --build` (or `make up`) — full system: app http://localhost:8000, Grafana http://localhost:3000
- `make test` — backend unit + integration (Docker required) and frontend tests
- `make lint` — ruff + TypeScript typecheck
- `make ai-sdlc` — companion AI SDLC Web Workbench on http://localhost:8090 (`tools/ai-sdlc/`), or `docker compose --profile sdlc up --build` for full-suite Compose (supports owner-gated `SDLC_REQUIRE_AUTH=true`)
- `python scripts/check_repo_hygiene.py` — English-only and forbidden-terms check

## Hard rules
1. English only in every committed file, commit message, issue, and PR.
2. Every change starts from a GitHub issue; comment when you start and when you finish (skill `issue-workflow`).
3. Spec first: change `specs/` (and `openapi.yaml` for API changes) before code.
4. Tests first (TDD). A PR without tests for its acceptance criteria is rejected.
5. Never put names, display names, request bodies, headers, or credentials into logs, spans, or metrics.
6. Domain code (`backend/app/domain/`) imports neither SQLAlchemy nor FastAPI. Time math uses minutes since midnight.
7. Do not add features listed as out of scope in `docs/plan/MASTER_PLAN.md` §1. Companion developer tooling lives outside SessionBoard's core app (`tools/`) and stays excluded from the runtime container.
8. Do not read or copy anything from outside this repository unless `.local/PROTOTYPE_REUSE.md` explicitly allows it.
9. Before claiming done, run the gate commands (skill `phase-gate`), sync `README.md` rubric statuses/repository layout on phase transitions, and paste their output.
