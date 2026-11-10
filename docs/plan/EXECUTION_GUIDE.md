# Execution Guide (for the human owner)

How to run the SessionBoard build with AI agents in Google Antigravity, phase by phase.
The plan itself is `docs/plan/MASTER_PLAN.md`; this guide covers **who does what, when, and with which prompt**.

---

## 1. The harness

No custom orchestration code is needed. The harness is made of files in this repository plus Antigravity's built-in subagents:

| Layer | Where | Purpose |
|---|---|---|
| Context | `AGENTS.md` → modular docs | Every agent session loads `AGENTS.md` automatically |
| Plan | `docs/plan/MASTER_PLAN.md` | Phases, gates, exact decisions, pitfalls |
| Roles | `.agents/roles/*.md` | System prompts for subagents |
| Skills | `.agents/skills/{issue-workflow,phase-gate,release-and-rollback}` | Repeatable procedures, loaded on demand |
| Shared state | GitHub Issues, PRs, pinned "Phase gates log" issue | Memory between sessions and agents; evidence for reviewers |
| Guard rails | `scripts/check_repo_hygiene.py` (pre-commit + CI), branch protection, CI | Stop leaks, untested code, and non-English text |

Also use the globally installed Superpowers skills where they fit: `test-driven-development`, `requesting-code-review`, `verification-before-completion`, `subagent-driven-development`.

**Session model:** one Antigravity conversation per phase (fresh context). The conversation is the **orchestrator**; it dispatches one subagent per issue using the matching role prompt, then a Reviewer subagent per PR, then runs the gate. Long phases (4, 5) can be started with `/goal`. Use `/compact` if a session grows long.

---

## 2. Human checklist (do these at the indicated time)

### Before Phase 0 (5 min)
- [x] Docker Desktop is installed (`docker --version` works; keep Docker Desktop running for Phase 3+).
- [x] `gh auth status` is logged in (`brut0`, scopes `repo`, `workflow` verified).
- [x] `.local/forbidden-terms.txt` is populated and `scripts/check_repo_hygiene.py` passes (`OK: 0 violations`).

### Phase 1 end
- [ ] Read `specs/product-spec.md`, answer clarifications, reply **"spec approved"**.

### Before Phase 7 (≈30 min) — hosting
> 👉 **Detailed step-by-step guide:** See [`docs/plan/PRE_PHASE_8_HUMAN_CHECKLIST.md`](PRE_PHASE_8_HUMAN_CHECKLIST.md) for exact UI clicks, Pitfall #6 / #14 checks, and Phase 7 Gate verification steps up to Phase 8.

1. **Neon** (https://neon.tech, sign in with GitHub, no card): create project `sessionboard-dev` (Postgres 16, region `AWS Europe Central 1 (Frankfurt)`), then project `sessionboard-prod` (same). For each: Dashboard → Connect → **turn "Connection pooling" off** → copy the connection string.
2. **Render** (https://render.com, sign in with GitHub): after the first `cd-dev.yml` run has pushed an image **and** you made the GHCR package public (GitHub → your profile → Packages → `sessionboard` → Package settings → Change visibility → Public):
   - New → Web Service → **Existing Image** → `ghcr.io/<owner>/sessionboard:<sha from the run>` → name `sessionboard-dev`, region Frankfurt, instance type **Free**.
   - Environment: `DATABASE_URL=<neon dev string>`, `APP_ENV=dev`, `SEED_DEMO_DATA=true`, `OTEL_SDK_DISABLED=true` (until Phase 8).
   - Settings → Health Check Path `/api/health`; Settings → Deploy Hook → copy.
   - Repeat for `sessionboard-prod` with the prod DB and `APP_ENV=prod`.
3. GitHub repo → Settings → Secrets and variables → Actions:
   - Secrets: `RENDER_DEPLOY_HOOK_DEV`, `RENDER_DEPLOY_HOOK_PROD`
   - Variables: `DEV_URL=https://sessionboard-dev.onrender.com`, `PROD_URL=https://sessionboard-prod.onrender.com` (use the real URLs Render shows)
4. Settings → Environments → New `production` → Required reviewers: you.

> Chicken-and-egg note: Render needs an existing image to create the service, and `cd-dev.yml` needs the hook. The DevOps agent will make the deploy step skip with a warning while `RENDER_DEPLOY_HOOK_DEV` is unset, so the first run only pushes the image.

### Before Phase 8 (≈15 min) — telemetry
1. **Grafana Cloud** (https://grafana.com, free, no card): create a stack (region EU).
2. Stack → Connections → **OpenTelemetry (OTLP)** → create token (scopes metrics/logs/traces write) → note `OTEL_EXPORTER_OTLP_ENDPOINT` and the generated `OTEL_EXPORTER_OTLP_HEADERS` (must look like `Authorization=Basic%20...`).
3. In both Render services set: `OTEL_SDK_DISABLED=false`, `OTEL_SERVICE_NAME=sessionboard`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT=...`, `OTEL_EXPORTER_OTLP_HEADERS=...`.

### Before Phase 9 (≈20 min) — alert and on-call
1. **Google AI Studio** (https://aistudio.google.com) → Get API key (free) → secret `GEMINI_API_KEY`; variable `GEMINI_MODEL` = the current free Flash model id shown in AI Studio.
2. GitHub → Settings → Developer settings → Fine-grained tokens:
   - `oncall-bot` (repo `sessionboard` only; Contents RW, Pull requests RW, Issues RW, Actions RW) → secret `ONCALL_GH_TOKEN`.
   - `grafana-dispatch` (repo `sessionboard` only; Contents RW) → used only inside Grafana's contact point.
3. Grafana Cloud → Connections → Data sources → Loki → note URL and user id; create an Access Policy token with `logs:read` → secrets `GRAFANA_LOGS_URL`, `GRAFANA_LOGS_USER`, `GRAFANA_LOGS_TOKEN`.
4. Create the contact point and alert rule with the exact values the DevOps agent gives you (master plan §11).
5. Run the chaos drill and record the screen.

### Phase 10
- [ ] Submit on the course platform; complete **3 peer reviews** (mandatory).

---

## 3. Orchestrator prompt (paste into a NEW Antigravity conversation for each phase)

Replace `<N>`:

```
You are the orchestrator for Phase <N> of the SessionBoard project.

1. Read AGENTS.md, docs/plan/MASTER_PLAN.md (whole file, then focus on §14 Phase <N> and §16),
   docs/process.md, docs/agents/team.md, and the latest comments on the pinned "Phase gates log" issue.
2. Confirm the previous phase gate is PASS in that log. If not, stop and tell me.
3. List the GitHub issues for this phase: gh issue list --label phase:<N> --state open.
4. For each issue, define a subagent whose system prompt is the content of .agents/roles/<role>.md
   (role from the issue's agent:* label) and invoke it with: the issue number, the instruction to use
   the issue-workflow skill, and the report format from its role file.
   - Run independent issues in parallel only when they touch different directories
     (e.g. backend vs frontend, QA tests vs implementation); use Workspace "share" for parallel agents
     so each works on its own branch.
   - Everything else runs sequentially.
5. For every PR, invoke a Reviewer subagent (.agents/roles/reviewer.md). Loop until approved
   (max 2 rounds, then escalate to me).
6. Tell me which PRs are ready to merge. After I merge, run the phase gate with the phase-gate skill
   and post the report on the "Phase gates log" issue.
7. Stop at anything that needs my accounts, secrets, approvals, or a spec decision, and give me an
   exact checklist from docs/plan/EXECUTION_GUIDE.md section 2.
Never skip a gate, never add out-of-scope features, English only in the repository.
```

### Phase-specific notes for the orchestrator
| Phase | Note |
|---|---|
| 0 | No issues exist yet: the orchestrator itself acts as DevOps agent following master plan Phase 0. |
| 1 | No issues yet: invoke the Spec agent directly; wait for my "spec approved". |
| 2 | Invoke the Architect agent directly; it creates the issues. I review the issue list before Phase 3. |
| 3 | Single DevOps issue (T01). |
| 4 | Backend (T02→T03→T04→T05 sequential) in parallel with QA (T06). Good candidate for `/goal`. |
| 5 | Frontend (T07→T08→T09→T10) in parallel with QA (T11). |
| 6–7 | DevOps; stops for my Render/Neon setup (section 2). |
| 8 | DevOps + Backend; stops for Grafana Cloud setup. |
| 9 | DevOps + On-call prompt authoring; stops for AI Studio key, tokens, Grafana alert; then the drill. |
| 10 | Spec agent writes README/docs; fresh-clone verification; I submit. |

---

## 3.5 Complete Subagent Dispatch Matrix (Phases 0–10)

This table specifies **exactly** which subagents to define (`define_subagent`) and invoke (`invoke_subagent`), their `Workspace` mode, execution order, and the exact gate verification for every phase.

| Phase | Subagent Name (`define_subagent`) | System Prompt File | `EnableWriteTools` | `Workspace` Mode | Execution Order & Dependencies | Exact Gate Verification (`phase-gate`) |
|---|---|---|---|---|---|---|
| **Phase 0** *(Bootstrap)* | *(Orchestrator acts directly as DevOps)* | `.agents/roles/devops.md` | `true` | `inherit` | Sequential: `git init -b main` → `.gitignore`/`.gitattributes` → `scripts/check_repo_hygiene.py` → `gh repo create sessionboard --public` → labels & milestones → issue/PR templates → `FORBIDDEN_TERMS` secret → pinned issue `"Phase gates log"` → initial push. | `uv run python scripts/check_repo_hygiene.py` (`OK`), `gh repo view --json visibility -q .visibility` (`PUBLIC`). |
| **Phase 1** *(Specify)* | `spec-agent` | `.agents/roles/spec.md` | `true` | `inherit` | Single agent: writes `specs/constitution.md`, `specs/product-spec.md` (BR-1..BR-8, error contract, ≥14 ACs), `specs/nfr-observability.md`. Stops for human `"spec approved"`, then commits `docs(spec): approve v1`. | BR→AC table 100% covered; human approval recorded; hygiene `OK`. |
| **Phase 2** *(Plan & Tasks)* | `architect-agent` | `.agents/roles/architect.md` | `true` | `inherit` | Single agent: writes `specs/data-model.md`, `specs/api/openapi.yaml`, `docs/architecture.md`, `docs/adr/0001..0003.md`, `specs/tasks.md`, and creates GitHub Issues T01–T16 via `gh issue create`. | `npx @redocly/cli lint specs/api/openapi.yaml` (0 errors); all 16 issues created and mapped to ACs. |
| **Phase 3** *(Skeleton)* | `devops-agent` → `reviewer-agent` | `.agents/roles/devops.md`, `.agents/roles/reviewer.md` | `true` (devops), `false` (reviewer) | `inherit` | Sequential (Issue T01): `devops-agent` scaffolds `backend/` (`uv init --python 3.12`), `frontend/` (Vite React 19 TS), `Dockerfile`, `docker-compose.yml`, `Makefile`, opens PR → `reviewer-agent` reviews → merge. | `docker compose up --build -d` → `curl.exe -fsS http://localhost:8000/api/health` (`{"status":"ok","db":"ok"}`) → `http://localhost:3000` reachable → `docker compose down`. |
| **Phase 4** *(Backend TDD)* | `backend-agent`, `qa-agent`, `reviewer-agent` | `.agents/roles/backend.md`, `.agents/roles/qa.md`, `.agents/roles/reviewer.md` | `true` (backend, qa), `false` (reviewer) | `share` (when running QA in parallel) or `inherit` | `backend-agent` executes T02 (models/Alembic/seed) → T03 (pure domain conflicts + unit tests) → T04 (Directory API) → T05 (Sessions API with advisory lock) sequentially. In parallel (or immediately after T02), `qa-agent` writes `tests/integration/test_sessions_api.py` and `test_openapi_contract.py` (T06) from spec ACs without reading implementation. Each PR reviewed by `reviewer-agent`. | `make test-backend` (all unit + testcontainers integration + OpenAPI contract tests green); `make lint` clean; manual `curl.exe` overlapping booking returns 409. |
| **Phase 5** *(Frontend & Component Tests)* | `frontend-agent`, `qa-agent`, `reviewer-agent` | `.agents/roles/frontend.md`, `.agents/roles/qa.md`, `.agents/roles/reviewer.md` | `true` (fe, qa), `false` (reviewer) | `share` or `inherit` | `frontend-agent` runs `npm run gen:api` and implements T07 (shell/tabs/client) → T08 (DayBoard) → T09 (BookingModal with 409 conflicts & Trace ID) → T10 (Directory page). `qa-agent` implements T11 (Vitest + RTL + MSW tests). Reviewed by `reviewer-agent`. | `make test` (backend + frontend green in one command); `make lint` clean; `docker compose up --build` end-to-end persistence check across `docker compose restart app`. |
| **Phase 6** *(CI Pipeline)* | `devops-agent` → `reviewer-agent` | `.agents/roles/devops.md`, `.agents/roles/reviewer.md` | `true` / `false` | `inherit` | Sequential (Issue T12): `devops-agent` creates `.github/workflows/ci.yml` (`hygiene`, `backend`, `frontend`, `docker` jobs), opens PR, verifies all 4 checks pass on GitHub Actions, configures branch protection & auto-merge. | `gh pr checks <n>` shows all 4 jobs green; branch protection active on `main`. |
| **Phase 7** *(Deploy, CD & Rollback)* | `devops-agent` → `reviewer-agent` | `.agents/roles/devops.md`, `.agents/roles/reviewer.md` | `true` / `false` | `inherit` | Sequential (Issue T13): `devops-agent` creates `cd-dev.yml`, `deploy-prod.yml`, `rollback.yml`, `docs/deployment.md`. First push publishes image to GHCR → Human makes package public & creates Neon/Render services (§2) → `cd-dev.yml` deploys dev → `deploy-prod.yml` deploys prod → test `rollback.yml` on dev. | `curl.exe -fsS $DEV_URL/api/version` & `$PROD_URL/api/health` return 200; at least one real `rollback.yml` run green and linked in `docs/deployment.md`. |
| **Phase 8** *(Observability)* | `backend-agent` + `devops-agent` → `reviewer-agent` | `.agents/roles/backend.md`, `.agents/roles/devops.md`, `.agents/roles/reviewer.md` | `true` / `false` | `inherit` | Sequential (Issue T14): `backend-agent` wires `app/telemetry.py` (`booking.create` span, `sessionboard_bookings_total` metric, JSON logs with `trace_id`, `test_telemetry_no_pii.py`). `devops-agent` adds `ops/grafana/dashboard.json` and `docs/observability.md` with screenshots from local/cloud Grafana. | `test_telemetry_no_pii.py` green; trace + correlated Loki logs + Prometheus metric visible by `X-Trace-Id`; screenshots committed. |
| **Phase 9** *(Alert & On-Call Agent)* | `devops-agent` → `reviewer-agent` | `.agents/roles/devops.md`, `.agents/roles/reviewer.md` | `true` / `false` | `inherit` | Sequential (Issue T15): `devops-agent` writes `scripts/synthetic_probe.py`, `synthetic-probe.yml`, `oncall.yml`, `docs/runbooks/booking-errors.md`, `ops/grafana/alert-rule.json` & `contact-point-payload.tmpl`. Human sets AI Studio key, PATs, and Grafana webhook (§2). Dry-run `repository_dispatch`, then execute Chaos Drill (§12.1) and record `docs/oncall-demo.md`. | Closed `[incident]` issue + merged `oncall` PR created by the headless Gemini CLI workflow + `docs/oncall-demo.md`. |
| **Phase 10** *(Docs & Submission)* | `spec-agent` → `reviewer-agent` | `.agents/roles/spec.md`, `.agents/roles/reviewer.md` | `true` / `false` | `inherit` | Sequential (Issue T16): `spec-agent` writes final `README.md` (with 12-criterion grading table and links), `docs/ai-tools.md`, verifies `AGENTS.md`. Orchestrator runs fresh-clone test in temp directory. | Fresh clone `docker compose up --build` and `make test` pass; hygiene `OK`; all 12 rows of the rubric table have working links. |

---

## 4. When something goes wrong

| Symptom | Action |
|---|---|
| Gate fails twice | Orchestrator stops; ask it for a root-cause summary (use the `systematic-debugging` skill); fix in a `fix/` issue |
| Spec gap discovered | New `type:docs` issue for the Spec agent; implementation waits |
| Hygiene check fails | Remove the text; if it reached a commit, rewrite history before pushing (`git commit --amend` / interactive rebase) — never push it |
| Free-tier limit hit | See master plan §15; reduce probe frequency; Render hours reset monthly |
| Agent drifts from scope | Point it to master plan §1 "Out of scope" and the issue's Out of scope field |
