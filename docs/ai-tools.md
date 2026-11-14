# AI Tools, Multi-Agent Harness & Automation Guide

SessionBoard uses a structured, spec-driven AI engineering setup across three layers:

1. **Antigravity IDE Multi-Agent Harness** (initial SDD/TDD build + chat-native post-MVP changes)
2. **Companion AI SDLC Web Workbench** (`tools/ai-sdlc/`, browser control plane calling LLM APIs)
3. **Autonomous Headless Gemini CLI On-Call Responder** (`.github/workflows/oncall.yml`, self-healing operations)

---

## 1. Context Management & Spec-Driven Harness

| Layer | Artifact(s) | Purpose |
|---|---|---|
| **Root Context** | [`AGENTS.md`](../AGENTS.md) | Always-loaded system rules: tech stack, Hard Rules 1–9 (English-only, issue-first, spec-first, TDD, zero-PII, pure domain, scope guard, phase gates), and modular doc map |
| **Constitution & Specs** | [`specs/constitution.md`](../specs/constitution.md), [`specs/product-spec.md`](../specs/product-spec.md), [`specs/nfr-observability.md`](../specs/nfr-observability.md), [`specs/data-model.md`](../specs/data-model.md), [`specs/api/openapi.yaml`](../specs/api/openapi.yaml) | Immutable architecture invariants, BR-1..BR-9, 16 Given/When/Then acceptance criteria (`AC-1.1`..`AC-4.2`), and OpenAPI 3.1 contract |
| **Plan & Tracker** | [`docs/plan/MASTER_PLAN.md`](plan/MASTER_PLAN.md), [`docs/plan/EXECUTION_GUIDE.md`](plan/EXECUTION_GUIDE.md), [`specs/tasks.md`](../specs/tasks.md) | Phase plan (`0`–`10`), subagent dispatch matrix, pitfall safeguards, and GitHub Issues [`#1`–`#17`](https://github.com/brut0/sessionboard/issues) |
| **Guard Rails** | [`scripts/check_repo_hygiene.py`](../scripts/check_repo_hygiene.py), `scripts/install-hooks.*`, `.github/workflows/ci.yml` | Pre-commit and CI enforcement for English-only text, zero forbidden patterns, formatting/linting, integration tests, OpenAPI parity, and Docker reproducibility |

---

## 2. Subagent Roles (`.agents/roles/`)

Rather than letting one unconstrained prompt mutate specs, tests, and code together, work is delegated to **8 single-purpose role definitions** defined in [`.agents/roles/`](../.agents/roles/) and documented in [`docs/agents/team.md`](agents/team.md):

| Role Prompt | Workspace Mode | Core Responsibility & Boundaries |
|---|---|---|
| [`spec.md`](../.agents/roles/spec.md) | `inherit` | Authors constitution, `specs/product-spec.md`, `specs/nfr-observability.md`, `README.md`, and `docs/ai-tools.md`; pauses for explicit human `"spec approved"` before implementation |
| [`architect.md`](../.agents/roles/architect.md) | `inherit` | Authors `specs/api/openapi.yaml` (Redocly linted), `specs/data-model.md`, `docs/architecture.md`, `docs/adr/0001..0003`, `specs/tasks.md`, and labeled GitHub Issues |
| [`backend.md`](../.agents/roles/backend.md) | `share` / `inherit` | TDD loop for `backend/`: pure `domain/` (`time_utils.py`, `conflicts.py`, minutes since midnight, zero SQLAlchemy/FastAPI imports), Alembic migrations, routers, OTel instrumentation |
| [`frontend.md`](../.agents/roles/frontend.md) | `share` / `inherit` | TDD loop (Vitest + RTL + MSW) for React 19 UI; generates types via `npm run gen:api` + `openapi-fetch` (never hand-written types) |
| [`qa.md`](../.agents/roles/qa.md) | `share` (parallel) | Writes independent `test_ac_*` PostgreSQL `testcontainers` integration tests and `test_openapi_contract.py` strictly from specs **before reading implementation code** |
| [`reviewer.md`](../.agents/roles/reviewer.md) | `inherit` (read-only) | Executes a 10-point audit on every PR (scope, ACs, OpenAPI first, domain purity, zero PII/secrets, hygiene, error contract, expand-only migrations, docs sync, trailers/CI) |
| [`devops.md`](../.agents/roles/devops.md) | `inherit` | Builds `Dockerfile`, `docker-compose.yml`, `Makefile`, GitHub Actions CI/CD (`ci.yml`, `cd-dev.yml`, `deploy-prod.yml`, `rollback.yml`), Grafana provisioning, and runbooks |
| [`oncall.md`](../.agents/roles/oncall.md) | GitHub Actions runner | Prompts headless **Gemini CLI** inside `.github/workflows/oncall.yml` with strict minimal-diff and test-first constraints |

---

## 3. Project Skills (`.agents/skills/`) & Engineering Workflows

Project-local skills under [`.agents/skills/`](../.agents/skills/) package repeatable operational procedures loaded automatically by agents:

| Skill | File | Purpose |
|---|---|---|
| **`issue-workflow`** | [`.agents/skills/issue-workflow/SKILL.md`](../.agents/skills/issue-workflow/SKILL.md) | Enforces start/finish issue comments, branch naming (`feat/`, `fix/`, `docs/`, `infra/`), commit trailers (`Agent: <role>-agent`, `Refs: #<n>`), and PR template compliance |
| **`phase-gate`** | [`.agents/skills/phase-gate/SKILL.md`](../.agents/skills/phase-gate/SKILL.md) | Lists the exact deterministic verification commands per phase (`0`–`10`) and formats structured `Phase <N> gate: PASS` reports on pinned Issue `#1` |
| **`release-and-rollback`** | [`.agents/skills/release-and-rollback/SKILL.md`](../.agents/skills/release-and-rollback/SKILL.md) | Governs production promotion (`deploy-prod.yml` with required owner review), rollbacks (`rollback.yml`), and live probe verification (`synthetic-probe.yml`) |
| **`feature-sdlc`** | [`.agents/skills/feature-sdlc/SKILL.md`](../.agents/skills/feature-sdlc/SKILL.md) | Chat-native 6-stage AI SDLC pipeline for post-MVP changes (Constitution guard → Spec + approval → Architect + OpenAPI → Parallel TDD → Gates → Review + CD) |

Complementing these repository skills in Antigravity IDE are disciplined engineering skills (`test-driven-development`, `systematic-debugging`, `requesting-code-review`, `verification-before-completion`, and `subagent-driven-development`).

---

## 4. MCP Servers & Toolchain Integrations

Inside Google Antigravity IDE, the orchestrator and engineering sessions connect to external docs, browsers, and platform APIs cleanly:

- **Context7 MCP (`context7`):** Configured for up-to-date framework and library documentation queries without relying on stale training weights.
- **Built-in Browser Subagent:** Interactive headless browser subagent used to inspect and configure live Grafana Cloud dashboards/rules and visually verify deployed UI behavior.
- **GitHub CLI (`gh`) & REST APIs:** Automates issue creation, PR diffs/checks watching, squash merges, workflow dispatches, and GitHub Actions secrets/variables configuration.

---

## 5. Companion AI SDLC Web Workbench (`tools/ai-sdlc/`)

For interactive browser-driven post-MVP changes side-by-side with SessionBoard (documented in [`docs/ai-sdlc.md`](ai-sdlc.md)), `tools/ai-sdlc/` provides a decoupled FastAPI + HTML workbench (`make ai-sdlc` on `:8090`, `docker compose --profile sdlc up --build`, or owner-gated on Render at `https://essionboard-ai-sdlc.onrender.com`):

- **LLM Providers:** Connects via **Google Gemini API** (`GEMINI_API_KEY`) or any **OpenAI-compatible endpoint** (`OPENAI_API_KEY` + `OPENAI_BASE_URL`), plus optional headless local `gemini --yolo` execution.
- **Hard Guardrails:** Enforces `HTTP 409` spec-approval lock before architect/TDD code stages, `HTTP 422` path containment and hygiene scans, fail-closed owner authentication (`503` when misconfigured, `401`/`429`/`403` CSRF protection), and **39 dedicated tests** verifying workbench security and stages.

---

## 6. Headless Gemini CLI On-Call Agent (`.github/workflows/oncall.yml`)

When live user-impact error ratio exceeds 20% (`B >= 3 && ($A / $B) > 0.2` over 5m), Grafana Cloud fires `BookingErrorRatioHigh` (`ops/grafana/alert-rule.json`) via webhook `repository_dispatch` (`grafana-alert`):

1. Opens a labeled `[incident]` GitHub issue (with run link and commit context).
2. **Rollback First:** Deterministically invokes `rollback.yml` on `dev` to restore the previous healthy SHA before running AI inference.
3. Queries zero-PII Grafana Cloud Loki error logs (`level="ERROR"`, counts only in CI logs) alongside recent `git log` / `git diff`.
4. Invokes headless **Gemini CLI** using `.agents/roles/oncall.md`, configured with model fallback (`GEMINI_MODEL` `gemini-3.1-flash-lite` → `gemini-2.5-flash` → `auto`) and a `210s` per-model timeout.
5. Requires deterministic `ruff check`, `ruff format --check`, and `pytest` (all `49` tests) to pass before opening an auto-merging fix PR (`Closes #<incident>`).

Verified end-to-end during the Phase 9 Chaos Drill: [Incident `#48`](https://github.com/brut0/sessionboard/issues/48) → [`oncall.yml` #43586436665](https://github.com/brut0/sessionboard/actions/runs/43586436665) → [Fix `PR #49`](https://github.com/brut0/sessionboard/pull/49) → [`docs/oncall-demo.md`](oncall-demo.md).
