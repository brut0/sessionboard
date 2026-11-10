# SessionBoard — Deployment & Rollback Strategy

> **Status:** Approved (Phase 7)
> **Source of truth for:** Environments, CD workflows, Render + Neon setup, zero-downtime migrations, and rollbacks.

---

## 1. Environments Overview

| Environment | Purpose | Public URL | Database | Trigger | Required Approvals |
|---|---|---|---|---|---|
| **local** | Feature development & tests | `http://localhost:8000` | Local Docker Compose `db` (Postgres 16) | `docker compose up --build` | None |
| **dev** | Continuous integration & smoke validation | `https://sessionboard-dev.onrender.com` | Neon Serverless Postgres (`sessionboard-dev`) | Automated on every push to `main` via `cd-dev.yml` | None |
| **prod** | Production studio scheduling | `https://sessionboard-prod.onrender.com` | Neon Serverless Postgres (`sessionboard-prod`) | Manual dispatch via `deploy-prod.yml` with target `sha` | Owner approval via GitHub `production` environment |

---

## 2. Infrastructure Architecture

- **Compute:** [Render](https://render.com) Web Services (Free instance type, region Frankfurt).
  - Deploys pre-built Linux AMD64 container images pulled directly from [GitHub Container Registry (GHCR)](https://ghcr.io).
  - Health check path configured at `/api/health`.
- **Database:** [Neon Serverless PostgreSQL](https://neon.tech) (PostgreSQL 16).
  - Separate isolated projects for `dev` and `prod`.
  - Migrations executed automatically on container startup via `alembic upgrade head` in `docker-entrypoint.sh`.
- **Image Registry:** GHCR (`ghcr.io/brut0/sessionboard:<sha>`).
  - Images built and pushed by GitHub Actions (`cd-dev.yml`).

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
5. **Configure GitHub Secrets & Variables:**
   - Secrets:
     - `RENDER_DEPLOY_HOOK_DEV`
     - `RENDER_DEPLOY_HOOK_PROD`
   - Variables:
     - `DEV_URL` (e.g. `https://sessionboard-dev.onrender.com`)
     - `PROD_URL` (e.g. `https://sessionboard-prod.onrender.com`)
6. **Configure Production Environment:**
   - Settings → Environments → New environment `production` → Add required reviewer: Owner account (`brut0`).
