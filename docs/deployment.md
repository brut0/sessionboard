# SessionBoard — Deployment & Rollback Strategy

> **Status:** Approved (Phase 7)
> **Source of truth for:** Environments, CD workflows, Render + Neon setup, zero-downtime migrations, and rollbacks.

---

## 1. Environments Overview

| Environment | Purpose | Public URL | Database | Trigger | Required Approvals & Access |
|---|---|---|---|---|---|
| **local** | Feature development & tests | `http://localhost:8000` (optional companion workbench `http://127.0.0.1:8090` via `--profile sdlc`) | Local Docker Compose `db` (Postgres 16) | `docker compose up --build` (or `--profile sdlc up --build`) | None locally (`ai-sdlc` supports optional `SDLC_REQUIRE_AUTH=true`) |
| **dev** | Continuous integration & smoke validation | `https://sessionboard-dev.onrender.com` | Neon Serverless Postgres (`sessionboard-dev`) | Automated on every push to `main` via `cd-dev.yml` | None (core app is public studio demo; zero PII) |
| **prod** | Production studio scheduling | `https://sessionboard-prod.onrender.com` | Neon Serverless Postgres (`sessionboard-prod`) | Manual dispatch via `deploy-prod.yml` with target `sha` | Owner approval via GitHub `production` environment |
| **ai-sdlc (companion)** | Isolated owner-only AI SDLC workbench | `https://essionboard-ai-sdlc.onrender.com` (optional) | None (stateless + ephemeral git clone via `SDLC_CLONE_REPO_URL`) | Automated push to `main` via `cd-dev.yml` (`build-and-push-ai-sdlc` + `deploy-ai-sdlc`) | **Strictly Owner-Only (`SDLC_REQUIRE_AUTH=true`)**: fail-closed `503` if password missing, `401` + signed `__Host-sdlc_session` cookie + `429` rate limiter |

---

## 2. Infrastructure Architecture

- **Compute:** [Render](https://render.com) Web Services (Free instance type, region Frankfurt).
  - Deploys pre-built Linux AMD64 container images pulled directly from [GitHub Container Registry (GHCR)](https://ghcr.io).
  - Health check path configured at `/api/health`.
- **Database:** [Neon Serverless PostgreSQL](https://neon.tech) (PostgreSQL 16).
  - Separate isolated projects for `dev` and `prod`.
  - Migrations executed automatically on container startup via `alembic upgrade head` in `docker-entrypoint.sh`.
- **Image Registry:** GHCR (`ghcr.io/brut0/sessionboard:<sha>` for the studio app, and `ghcr.io/brut0/sessionboard-ai-sdlc:<sha>` for the decoupled companion workbench).
  - Images built and pushed cleanly by GitHub Actions (`cd-dev.yml`).
  - `tools/` stays excluded from `ghcr.io/brut0/sessionboard` via `.dockerignore`.

---

## 3. Database Migration Strategy: Expand-Contract

Rollbacks in SessionBoard are designed to be instant and zero-downtime. To achieve this without requiring dangerous database down-migrations:

1. **Expand Phase:** All schema changes must be backward-compatible with the immediately preceding code version.
   - New columns must be `NULL` or have sensible defaults.
   - Renaming columns is split into adding the new column, dual-writing/backfilling, and deprecating the old.
2. **Migrate Phase:** The new application code deploys and begins reading/writing the new schema structure.
3. **Contract Phase (subsequent release):** Old, unused columns or tables are dropped only after the new version has stabilized and will not be rolled back.
4. **Advisory Lock Safety:** Advisory locks (`SELECT pg_advisory_xact_lock(...)`) use integer hashing on date strings, requiring zero schema changes across releases.

---

## 4. Continuous Delivery Workflows

### 4.1 CD Dev (`.github/workflows/cd-dev.yml`)
1. **Trigger:** Push to `main` branch.
2. **CI Check:** Runs full CI validation suite (`ci.yml` via `workflow_call`).
3. **Build & Push:** Compiles multi-stage image with `--build-arg GIT_SHA=${{ github.sha }}` and pushes tags `:${{ github.sha }}` and `:latest` to GHCR.
4. **Deploy Hook:** Calls Render deploy hook with URL-encoded image parameter:
   ```bash
   curl -fsS -X POST "${RENDER_DEPLOY_HOOK_DEV}&imgURL=ghcr.io%2Fbrut0%2Fsessionboard%3A${SHA}"
   ```
5. **Version Polling:** Polls `GET https://sessionboard-dev.onrender.com/api/version` every 15s (timeout 10 min) until `version` equals the commit SHA.
6. **Synthetic Smoke Probe:** Executes `python scripts/synthetic_probe.py --base-url $DEV_URL --mode once` to confirm booking and cancellation flows succeed.
7. **Companion AI SDLC Workbench (`build-and-push-ai-sdlc` + `deploy-ai-sdlc`):** Builds `tools/ai-sdlc/Dockerfile` (`SDLC_REQUIRE_AUTH=true`, `APP_ENV=prod` baked in), pushes `ghcr.io/brut0/sessionboard-ai-sdlc:<sha>`, triggers `RENDER_DEPLOY_HOOK_AI_SDLC` (gracefully skipping with a warning if unset), polls `$AI_SDLC_URL/api/health`, and fails deployment if unauthenticated `GET /api/config` does not return `HTTP 401`.

### 4.2 Production Deployment (`.github/workflows/deploy-prod.yml`)
1. **Trigger:** `workflow_dispatch` with required input `sha`.
2. **Gate:** Pauses for owner approval via GitHub `production` environment.
3. **Image Verification:** Runs `docker manifest inspect ghcr.io/brut0/sessionboard:<sha>` ensuring the image exists before triggering deployment.
4. **Deploy Hook:** Calls `RENDER_DEPLOY_HOOK_PROD`.
5. **Verification:** Polls `/api/version` and performs read-only health checks.

---

## 5. Rollback Runbook (`.github/workflows/rollback.yml`)

### When to Roll Back
- High error rate (5xx) detected after a deployment.
- Critical regression in conflict detection or data persistence.
- Synthetic probe alerts firing.

### Rollback Procedure
1. Identify the last known good commit SHA:
   ```bash
   git log --oneline main -n 5
   ```
2. Trigger the `Rollback Environment` workflow:
   - Go to **Actions** → **Rollback Environment** → **Run workflow**.
   - Choose `env`: `dev` or `prod`.
   - Enter `sha`: `<last_known_good_sha>`.
3. The workflow will:
   - Verify the container image for the target SHA exists in GHCR.
   - Trigger the Render deploy hook for the target environment.
   - Poll `/api/version` until the deployed version matches the target SHA.
   - Publish a verification summary to the GitHub Actions run summary.

---

## 6. Human Bootstrap Guide (Initial Setup)

> 👉 **Complete Pre-Phase-8 Checklist:** See [`docs/plan/PRE_PHASE_8_HUMAN_CHECKLIST.md`](plan/PRE_PHASE_8_HUMAN_CHECKLIST.md) for every click-by-click step covering GHCR, Neon, Render, GitHub secrets/environments, the rollback gate verification, and Grafana Cloud OTLP preparation.

Because Render requires an existing container image to configure a service, follow this chicken-and-egg sequence:

1. **Push initial image:**
   - Merge Phase 7 PR. `cd-dev.yml` runs, builds the image, and pushes it to GHCR. (Deploy hook step skips with a warning since secret is not yet set).
2. **Set GHCR package to Public:**
   - On GitHub: Profile → **Packages** → `sessionboard` → **Package settings** → **Danger Zone** → **Change visibility** → **Public** (allows Render free tier to pull without docker credentials).
3. **Create Neon PostgreSQL databases:**
   - In Neon console: create project `sessionboard-dev` and project `sessionboard-prod`. Copy the connection strings.
4. **Create Render Web Services:**
   - Web Service 1 (`sessionboard-dev`):
     - Source: Existing Image → `ghcr.io/brut0/sessionboard:<sha>`
     - Environment Variables:
       - `DATABASE_URL=<neon_dev_connection_string>`
       - `APP_ENV=dev`
       - `SEED_DEMO_DATA=true`
       - `OTEL_SDK_DISABLED=true`
     - Health Check Path: `/api/health`
     - Copy **Deploy Hook** URL.
   - Web Service 2 (`sessionboard-prod`):
     - Source: Existing Image → `ghcr.io/brut0/sessionboard:<sha>`
     - Environment Variables:
       - `DATABASE_URL=<neon_prod_connection_string>`
       - `APP_ENV=prod`
       - `SEED_DEMO_DATA=true`
       - `OTEL_SDK_DISABLED=true`
     - Health Check Path: `/api/health`
     - Copy **Deploy Hook** URL.
   - Web Service 3 (`sessionboard-ai-sdlc` — Optional Companion Workbench, **Owner-Gated**):
     - Source: Existing Image → `ghcr.io/brut0/sessionboard-ai-sdlc:<sha>` (zero secrets baked into image; pull publicly or configure Render Registry Credentials with a `read:packages` PAT if keeping the package private)
     - Environment Variables:
       - `APP_ENV=prod`
       - `SDLC_REQUIRE_AUTH=true`
       - `SDLC_OWNER_PASSWORD=<strong 20+ character passphrase>`
       - `SDLC_SESSION_SECRET=<random 32+ hex secret>`
       - `SDLC_CLONE_REPO_URL=https://github.com/brut0/sessionboard.git` *(token-free URL; `GH_TOKEN` stays strictly in env)*
       - `GEMINI_API_KEY=<Google AI Studio API key>`
       - `GH_TOKEN=<optional fine-grained PAT for issues & PRs>`
     - Health Check Path: `/api/health`
     - Copy **Deploy Hook** URL.
5. **Configure GitHub Secrets & Variables:**
   - Secrets:
     - `RENDER_DEPLOY_HOOK_DEV`
     - `RENDER_DEPLOY_HOOK_PROD`
     - `RENDER_DEPLOY_HOOK_AI_SDLC` *(optional companion service)*
   - Variables:
     - `DEV_URL` (e.g. `https://sessionboard-dev.onrender.com`)
     - `PROD_URL` (e.g. `https://sessionboard-prod.onrender.com`)
     - `AI_SDLC_URL` (e.g. `https://sessionboard-ai-sdlc.onrender.com`, optional)
6. **Configure Production Environment:**
   - Settings → Environments → New environment `production` → Add required reviewer: Owner account (`brut0`).

---

## 7. Live Verification & Rollback Evidence (Phase 7 Gate)

| Verification Item | Live Endpoint / Workflow Run | Verified Output |
|---|---|---|
| **Dev Service (`sessionboard-dev`)** | `https://sessionboard-dev.onrender.com` ([Neon `sessionboard-dev`](https://neon.tech)) | `/api/health` → `{"status":"ok","db":"ok"}`; `/api/version` → `3f0d5cd055f4c23f5b326964598b59ba9dac7095` (`env: "dev"`) |
| **Prod Service (`sessionboard-prod`)** | `https://sessionboard-prod.onrender.com` ([Neon `sessionboard-prod`](https://neon.tech)) | `/api/health` → `{"status":"ok","db":"ok"}`; `/api/version` → `3f0d5cd055f4c23f5b326964598b59ba9dac7095` (`env: "prod"`) |
| **Companion AI SDLC Workbench** | `https://essionboard-ai-sdlc.onrender.com` | `/api/health` → `{"status":"ok","version":"3f0d5cd...","auth_required":true,"auth_configured":true,"authenticated":false,"workspace_ready":true}`; `GET /api/config` → `HTTP 401` |
| **Manual Prod Promotion + Reviewer Gate** | [`deploy-prod.yml` #42887628791](https://github.com/brut0/sessionboard/actions/runs/42887628791) | Approved by `brut0` via `production` environment; deployed `3f0d5cd...` (`success`) |
| **Real Rollback Drill (`dev` → `f73bafa`)** | [`rollback.yml` #42887682401](https://github.com/brut0/sessionboard/actions/runs/42887682401) | Rolled `dev` back to `f73bafab66114d51d2a7b661cdf93d15151c777f` in 1m25s; `/api/version` confirmed rolled-back SHA |
| **Roll Forward (`dev` → `3f0d5cd`)** | [`rollback.yml` #42888034418](https://github.com/brut0/sessionboard/actions/runs/42888034418) | Restored `dev` to `3f0d5cd055f4c23f5b326964598b59ba9dac7095` in 1m24s (`success`) |
| **Synthetic Probe (`once` on `dev`)** | [`synthetic-probe.yml` #42887575404](https://github.com/brut0/sessionboard/actions/runs/42887575404) | `3/3 successful lifecycles` against live Render Dev + Neon PostgreSQL 16 (`success`) |
