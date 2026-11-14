---
name: feature-sdlc
description: >-
  Use when adding features, changing existing behavior, or fixing bugs in SessionBoard
  through the full chat-native AI SDLC pipeline (triggers: new feature request,
  enhancement, bugfix, spec-to-PR delivery).
---

# Feature AI SDLC (Chat-Native Pipeline)

Use this workflow whenever the human submits a new feature request, enhancement, or non-trivial change directly in Antigravity chat.

For the side-by-side interactive Web Workbench with direct LLM API execution, use **`make ai-sdlc`** (`tools/ai-sdlc/`, documented in `docs/ai-sdlc.md`).

---

## Stage 0 — Intake & Constitution Guard

1. Read `AGENTS.md`, `specs/constitution.md`, `specs/product-spec.md` (§7 Non-Goals), and `docs/plan/MASTER_PLAN.md` (§1 & §16).
2. Check if the request conflicts with:
   - Any permanent **Non-Goal** (`specs/product-spec.md` §7),
   - **Zero-PII telemetry rules** (`AGENTS.md` Hard Rule #5),
   - **Pure domain boundary** (`backend/app/domain/` imports neither SQLAlchemy nor FastAPI; time math in minutes since midnight), or
   - **English-only & clean-room hygiene** (`scripts/check_repo_hygiene.py`).
3. **Gate:** If the request crosses a permanent Non-Goal or constitution rule, **STOP** and ask the human whether to narrow scope or explicitly amend `specs/constitution.md` / `specs/product-spec.md`.

---

## Stage 1 — Specify (`spec-agent`)

1. Define/adopt `.agents/roles/spec.md`.
2. Draft updates to `specs/product-spec.md`:
   - Add or update Business Rule(s) `BR-*` and any error contract rows.
   - Add Given/When/Then Acceptance Criteria (`AC-<story>.<n>`) with concrete inputs, HTTP status codes, JSON response bodies, or exact UI text.
   - Update the BR → AC traceability matrix in `specs/product-spec.md`.
   - Record open design questions under `## Clarifications`.
3. **Human Approval Gate:** Present a concise summary of the proposed spec diff and open clarifications to the human. Wait for explicit approval (e.g., **"spec approved"**) before editing OpenAPI contracts or application code.
   - *Exception:* Pure bug fixes whose expected behavior is already defined by existing ACs in `specs/product-spec.md` may skip re-approval after citing the governing AC ID(s).

---

## Stage 2 — Architect, Contract & Issue Creation (`architect-agent`)

1. Define/adopt `.agents/roles/architect.md`.
2. Update design artifacts **before implementation code**:
   - `specs/api/openapi.yaml` (if any endpoint, field, or status code changed; include `422` wherever FastAPI validates inputs, and `404`/`409`/`503` explicitly) → validate with `npx @redocly/cli lint specs/api/openapi.yaml` (`0` errors).
   - `specs/data-model.md` (if DB schema changes — use backward-compatible **Expand → Migrate → Contract** steps per `docs/deployment.md` §3).
   - `docs/architecture.md` (and `docs/architecture-explorer.html` / `docs/adr/` if system topology or key technical choices changed).
   - `specs/tasks.md` with new task IDs mapped to all new/updated ACs.
3. Create GitHub Issue(s) via `gh issue create` matching `.github/ISSUE_TEMPLATE/task.yml` (Summary, Spec reference, Acceptance criteria checklist, Test plan, Agent role, Out of scope) and appropriate labels (`agent:*`, `type:feature|fix|docs`, etc.).

---

## Stage 3 — Branch & Strict TDD Implementation (`issue-workflow`)

1. Follow `.agents/skills/issue-workflow/SKILL.md`:
   - Post start comment on Issue `#N`.
   - Create branch from updated `main`: `feat/<N>-<slug>` (or `fix/<N>-<slug>`).
2. **Parallel dispatch where layers are independent** (using `invoke_subagent` with `Workspace="share"`):
   - **QA Agent** (`.agents/roles/qa.md`): writes failing integration tests (`test_ac_<story>_<n>_<slug>` in `backend/tests/integration/` with `testcontainers`) and checks `test_openapi_contract.py` strictly from specs **without reading new implementation code first**.
   - **Backend Agent** (`.agents/roles/backend.md`):
     1. Write failing unit/router test → verify **RED** (`cd backend && uv run pytest <test> -q`).
     2. Add Alembic forward-only migration if schema changed (`backend/alembic/versions/`).
     3. Implement minimal pure domain logic (`backend/app/domain/`) + router/schema changes → verify **GREEN**.
     4. Verify telemetry uses IDs/enums only (zero PII).
   - **Contract Sync:** Run `cd frontend && npm run gen:api` to regenerate `frontend/src/api/schema.d.ts` (never hand-write API types).
   - **Frontend Agent** (`.agents/roles/frontend.md`):
     1. Write failing Vitest + RTL + MSW test first → verify **RED**.
     2. Implement UI changes using `openapi-fetch` client in `frontend/src/api/client.ts` + Tailwind + `data-testid` attributes → verify **GREEN**.
3. Commit incrementally with Conventional Commits and agent trailers:
   ```text
   feat: <concise imperative summary>

   Agent: <role>-agent
   Refs: #<N>
   ```

---

## Stage 4 — Local Verification Gate (`phase-gate`)

Run every applicable check (details and Windows notes in [verification-commands.md](../../references/verification-commands.md)) and capture verbatim output for the PR and issue comments:

```powershell
# 1. Hygiene (English-only + forbidden prototype terms across working tree & commits)
uv run python scripts/check_repo_hygiene.py

# 2. Backend lint, format & full test suite (Docker Desktop must be running for testcontainers)
cd backend; uv run ruff check .; uv run ruff format --check .; uv run pytest -v; cd ..

# 3. Frontend OpenAPI drift check, typecheck, tests & production build
cd frontend; npm run gen:api; git diff --exit-code src/api/schema.d.ts; npm run typecheck; npm test; npm run build; cd ..
```

If container/runtime behavior changed, also run:
```powershell
docker compose up --build -d
curl.exe -fsS http://localhost:8000/api/health
docker compose down
```

---

## Stage 5 — Independent Code Review (`reviewer-agent`)

1. Invoke read-only Reviewer subagent (`.agents/roles/reviewer.md`, `EnableWriteTools=false`) to audit `git diff main...HEAD` against:
   - All 10 checklist items in `.agents/roles/reviewer.md` (single issue scope, AC tests present, OpenAPI synced first, pure domain boundary, zero PII, English-only hygiene, error contract parity, expand-only migrations, docs/README updated, trailers present).
2. Fix any blocking findings on the same branch and re-run Stage 4 verification.

---

## Stage 6 — README Sync, PR, CI & Release

1. Update `README.md` (and `docs/testing.md`, `docs/architecture.md`, etc.) if features, structure, commands, or test counts changed.
2. Push branch and create PR using `.github/pull_request_template.md`:
   - Include `Closes #<N>` (or `Refs #<N>` for human-gated infra PRs), checked AC boxes, test list, spec changes, and actual Stage 4 command output.
3. Wait for all required GitHub Actions checks (`Repository Hygiene`, `Backend Lint & Tests`, `Frontend Lint & Tests`, `Docker Build`) to pass:
   ```powershell
   gh pr checks <PR_NUM> --watch
   ```
4. Once merged to `main`:
   - `cd-dev.yml` automatically builds, pushes to GHCR, deploys to Render `dev`, and runs `scripts/synthetic_probe.py`.
   - Comment completion evidence on Issue `#N`.
   - To promote to `prod`, follow `.agents/skills/release-and-rollback/SKILL.md` (`deploy-prod.yml` with owner approval).
