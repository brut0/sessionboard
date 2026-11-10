# Pre-Phase-8 Human Action Checklist (Cloud Bootstrap, Phase 7 Gate & Grafana Cloud Prep)

> **Status:** **Complete (Parts A, B, and C verified — ready for Phase 8 / Issue #15)**
> **Purpose:** Complete step-by-step instructions for every external cloud account, package visibility setting, Render/Neon resource, GitHub secret/variable, live verification run, and Grafana Cloud OTLP setup required from the current state (post-PR #31) up to starting **Phase 8 (Observability — Issue #15)**.
> **Cost:** **$0.00** (no credit card required for Neon Free, Render Free, GitHub Public/GHCR, Grafana Cloud Free, or Google AI Studio Free).

---

## Current Baseline Check

Before starting these steps:
- **Phases 0–6** passed on GitHub (`Issue #1`).
- **Phase 7 workflows** (`cd-dev.yml`, `deploy-prod.yml`, `rollback.yml`, `synthetic-probe.yml`) and `scripts/synthetic_probe.py` are merged on `main`, and `cd-dev.yml` pushes both **`ghcr.io/brut0/sessionboard:<sha>`** and the owner-gated companion image **`ghcr.io/brut0/sessionboard-ai-sdlc:<sha>`**.
- **Initial GHCR image** already exists at `ghcr.io/brut0/sessionboard:f73bafab66114d51d2a7b661cdf93d15151c777f` (and `:latest`). After this PR merges, `cd-dev.yml` pushes `<latest_main_sha>`, giving you distinct image SHAs to verify rollback cleanly.
- **Issue `#14`** (`[T13] Cloud deployment...`) has been reopened and stays open until you complete Steps 1–5 below and post the Phase 7 Gate evidence.

---

## Part A — Phase 7 Cloud Infrastructure & Secrets Setup (≈25 min)

### Step 1: Make GHCR Container Package Public (2 min)

Render Free Web Services pull images from GHCR without registry credentials, and `deploy-prod.yml` / `rollback.yml` run `docker manifest inspect` directly.

1. Open GitHub in your browser while signed in as **`brut0`**.
2. Go to your profile → **Packages** (`https://github.com/brut0?tab=packages`).
3. Click the **`sessionboard`** container package.
4. Click **Package settings** (bottom right).
5. Scroll to **Danger Zone** → **Change visibility** → select **Public**.
6. Type `sessionboard` to confirm.
   - *(Optional if deploying companion Service 3 `sessionboard-ai-sdlc` below)*: Repeat for **`sessionboard-ai-sdlc`** (zero secrets are baked into the container image; alternatively keep it Private on GHCR and add a `read:packages` Registry Credential in Render).

**Quick check:** Make sure the package shows the green **Public** badge and is linked to `brut0/sessionboard`.

---

### Step 2: Create Two Isolated Neon PostgreSQL 16 Databases (5 min)

> ⚠️ **CRITICAL PITFALL (Pitfall #14):** Turn **OFF Connection pooling** when copying both connection strings. Alembic migrations and SessionBoard's transaction advisory locks (`pg_advisory_xact_lock`) require direct non-`-pooler` PostgreSQL connections.

1. Go to [https://neon.tech](https://neon.tech) and click **Sign in with GitHub** (no credit card required).
2. Create **Project 1 (Dev):**
   - **Project name:** `sessionboard-dev`
   - **Postgres version:** `16`
   - **Region:** `AWS Europe Central 1 (Frankfurt)` (`eu-central-1`)
   - Click **Create project**.
   - Click **Connect** → toggle **Connection pooling** to **OFF** → copy the connection string (`postgresql://neondb_owner:...@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require...`).
   - Verify the hostname does **NOT** contain `-pooler`. Save temporarily as `NEON_DEV_URL`.
3. Create **Project 2 (Prod):** *(Must be a separate Neon project so free-tier CU-hours do not share quotas.)*
   - **Project name:** `sessionboard-prod`
   - **Postgres version:** `16`
   - **Region:** `AWS Europe Central 1 (Frankfurt)`
   - Click **Create project** → **Connect** → toggle **Connection pooling** to **OFF** → copy the connection string. Save temporarily as `NEON_PROD_URL`.

---

### Step 3: Create Two Render Free Web Services (10 min)

1. Go to [https://render.com](https://render.com) and click **Sign in with GitHub**.
2. First check which exact commit SHA is at the tip of `main` right now:
   ```powershell
   git fetch origin; git rev-parse origin/main
   ```
   Use the 40-character SHA from GHCR Packages (e.g., `f73bafab66114d51d2a7b661cdf93d15151c777f` or the latest SHA built by `CD Dev`). Avoid `:latest` in the initial URL if possible—explicit SHAs make rollbacks deterministic.

3. **Create Service 1 (`sessionboard-dev`):**
   - Click **New +** → **Web Service** → select **Deploy an existing image from a registry**.
   - **Image URL:** `ghcr.io/brut0/sessionboard:<sha>` (paste exact 40-char SHA).
   - Click **Next**, then configure:
     - **Name:** `sessionboard-dev`
     - **Region:** `Frankfurt (EU Central)`
     - **Instance Type:** **Free** (`$0 / month`)
   - Under **Environment Variables**, add these exact 4 variables:

     | Key | Value | Notes |
     |---|---|---|
     | `DATABASE_URL` | `<NEON_DEV_URL>` | Direct `postgresql://...` URL (no `-pooler`); app auto-converts scheme to `postgresql+psycopg://` |
     | `APP_ENV` | `dev` | Shown by `/api/version` |
     | `SEED_DEMO_DATA` | `true` | Seeds synthetic demo specialists/clients/rooms/sessions on initial boot |
     | `OTEL_SDK_DISABLED` | `true` | Keep `true` until Phase 8 OTLP credentials are added |

   - Click **Create Web Service** and wait 1–2 minutes for the container to pull, run `alembic upgrade head`, seed data, and start Uvicorn on Render's `$PORT`.
   - Open the service's **Settings** tab:
     - Set **Health Check Path** → `/api/health` → **Save Changes**.
     - Scroll to **Deploy Hook** → copy the URL (`https://api.render.com/deploy/srv-...?key=...`). Save temporarily as `RENDER_DEPLOY_HOOK_DEV`.
   - Copy the live service URL at the top of the page (e.g., `https://sessionboard-dev.onrender.com`, no trailing `/`).
   - **Smoke-check in browser or PowerShell:**
     ```powershell
     curl.exe -fsS https://sessionboard-dev.onrender.com/api/health
     curl.exe -fsS https://sessionboard-dev.onrender.com/api/version
     ```
     Expected: `{"status":"ok","db":"ok"}` and `{"version":"<sha>","env":"dev"}`. Open the root URL in a browser and confirm Day Board shows seeded sessions.

4. **Create Service 2 (`sessionboard-prod`):**
   - Click **New +** → **Web Service** → **Deploy an existing image from a registry**.
   - **Image URL:** `ghcr.io/brut0/sessionboard:<same_sha>`
   - **Name:** `sessionboard-prod`
   - **Region:** `Frankfurt (EU Central)`
   - **Instance Type:** **Free**
   - Add **Environment Variables**:

     | Key | Value |
     |---|---|
     | `DATABASE_URL` | `<NEON_PROD_URL>` |
     | `APP_ENV` | `prod` |
     | `SEED_DEMO_DATA` | `true` |
     | `OTEL_SDK_DISABLED` | `true` |

   - Wait for first deploy → **Settings** → set **Health Check Path** to `/api/health` → **Save Changes** → copy **Deploy Hook** as `RENDER_DEPLOY_HOOK_PROD`.
   - Copy the prod URL (e.g., `https://sessionboard-prod.onrender.com`, no trailing `/`) and verify `/api/health` and `/api/version` (`env: "prod"`).

5. **Create Service 3 (`sessionboard-ai-sdlc` — Owner-Gated Companion AI SDLC Workbench, Optional):**
   - Click **New +** → **Web Service** → select **Deploy an existing image from a registry**.
   - **Image URL:** `ghcr.io/brut0/sessionboard-ai-sdlc:<same_sha>` *(pull publicly, or configure Render Registry Credentials with a `read:packages` PAT)*.
   - **Name:** `sessionboard-ai-sdlc`
   - **Region:** `Frankfurt (EU Central)`
   - **Instance Type:** **Free** (`$0 / month`; sleeps after 15m idle — combined with `dev` and `prod` still stays comfortably below Render's 750 free instance hours/month)
   - Add **Environment Variables** (**NEVER leave `SDLC_OWNER_PASSWORD` empty**):

     | Key | Value | Notes |
     |---|---|---|
     | `APP_ENV` | `prod` | Enforces fail-closed auth & HTTPS `__Host-` cookie mode |
     | `SDLC_REQUIRE_AUTH` | `true` | Blocks unauthenticated `/api/*` (`401`) & `/docs` |
     | `SDLC_OWNER_PASSWORD` | `<20+ char unique passphrase>` | Generate locally; required >= 12 chars (else server fails closed with `503`) |
     | `SDLC_SESSION_SECRET` | `<32+ char random hex>` | Dedicated HMAC signing secret (generate via `openssl rand -hex 32`) |
     | `SDLC_CLONE_REPO_URL` | `https://github.com/brut0/sessionboard.git` | Token-free HTTPS URL for ephemeral repo clone on startup |
     | `GEMINI_API_KEY` | `<your Google AI Studio key>` | Powers Stage 1–6 LLM requests server-side (never returned raw) |
     | `GH_TOKEN` | `<fine-grained PAT: Issues/PRs/Contents RW>` | Optional, strictly repo-scoped (`brut0/sessionboard` only); authenticates `gh` & `git push` without writing tokens into `.git/config` |

   - Wait for deploy → **Settings** → set **Health Check Path** to `/api/health` → copy **Deploy Hook** as `RENDER_DEPLOY_HOOK_AI_SDLC` and URL as `AI_SDLC_URL` (`https://sessionboard-ai-sdlc.onrender.com`).
   - **Verify fail-closed owner gate (PowerShell):**
     ```powershell
     curl.exe -fsS https://sessionboard-ai-sdlc.onrender.com/api/health
     # Expected: {"status":"ok","auth_required":true,"auth_configured":true,"authenticated":false,"repo_root":null,...}

     curl.exe -i https://sessionboard-ai-sdlc.onrender.com/api/config
     # MUST return HTTP 401 Unauthorized (never 200!)
     ```
     Then open `https://sessionboard-ai-sdlc.onrender.com` in your browser, test entering 1 wrong password -> `401`, sign in with `SDLC_OWNER_PASSWORD`, and test clicking **Sign Out** -> locks workspace back cleanly.

---

### Step 4: Configure GitHub Secrets, Variables & Protected `production` Environment (5 min)

Go to **GitHub** → `brut0/sessionboard` → **Settings**:

1. **Secrets and variables → Actions → Secrets tab → New repository secret:**
   - `RENDER_DEPLOY_HOOK_DEV` = `<RENDER_DEPLOY_HOOK_DEV>`
   - `RENDER_DEPLOY_HOOK_PROD` = `<RENDER_DEPLOY_HOOK_PROD>`
   - `RENDER_DEPLOY_HOOK_AI_SDLC` = `<RENDER_DEPLOY_HOOK_AI_SDLC>` *(if Service 3 created; workflow warns and skips gracefully if omitted)*

2. **Secrets and variables → Actions → Variables tab → New repository variable:**
   - `DEV_URL` = `https://sessionboard-dev.onrender.com` *(exact URL Render assigned you, **NO trailing slash**)*
   - `PROD_URL` = `https://sessionboard-prod.onrender.com` *(exact URL Render assigned you, **NO trailing slash**)*
   - `AI_SDLC_URL` = `https://sessionboard-ai-sdlc.onrender.com` *(optional companion URL; enables automatic `401` smoke check in `cd-dev.yml`)*

3. **Environments → New environment:**
   - **Name:** `production` *(exact lowercase spelling)*
   - Check **Required reviewers** → search and add **`brut0`** → **Save protection rules**.

---

## Part B — Execute & Verify the Phase 7 Gate (10 min)

Run these verification workflows in **GitHub Actions** (`https://github.com/brut0/sessionboard/actions`):

1. **Identify two real commit SHAs on `main` whose GHCR images exist:**
   - Look at **CD Dev** runs on `main`:
     - Previous image SHA: `f73bafab66114d51d2a7b661cdf93d15151c777f`
     - Latest image SHA: `<HEAD SHA of origin/main after this PR merged>`

2. **Test Manual Prod Deployment + Human Approval (`deploy-prod.yml`):**
   - Actions → **Deploy Production** → **Run workflow** → `sha` = `<latest_sha>` → **Run workflow**.
   - Open the queued run → click **Review deployments** → check **`production`** → **Approve and deploy**.
   - Confirm job turns green and `curl.exe -fsS $PROD_URL/api/version` returns `<latest_sha>`.

3. **Test Real Rollback on `dev` (`rollback.yml`):** *(Mandatory Phase 7 Gate evidence)*
   - Ensure `dev` is currently on `<latest_sha>` (run `Rollback Environment` with `env=dev`, `sha=<latest_sha>` if `dev` was created on the older SHA).
   - Next, run **Actions → Rollback Environment → Run workflow**:
     - `env`: `dev`
     - `sha`: `f73bafab66114d51d2a7b661cdf93d15151c777f`
   - Wait for completion (2–4 min cold start). Confirm the Job Summary shows `Status: ✅ Completed and verified against /api/version` and verify:
     ```powershell
     curl.exe -fsS https://sessionboard-dev.onrender.com/api/version
     ```
     returns `"version":"f73bafab66114d51d2a7b661cdf93d15151c777f"`.
   - Copy the **GitHub Actions Run URL** of this rollback run (e.g., `https://github.com/brut0/sessionboard/actions/runs/...`).
   - Optionally roll `dev` back forward to `<latest_sha>` via `Rollback Environment` (`env=dev`, `sha=<latest_sha>`).

4. **Test Hourly Synthetic Probe (`synthetic-probe.yml`):**
   - Actions → **Synthetic Probe** → **Run workflow** (`mode=once`) → confirm `3/3 successful lifecycles` and exit `0`.

5. **Close Phase 7:**
   - Paste your `DEV_URL`, `PROD_URL`, and the `rollback.yml` run URL back into Antigravity chat with **"Phase 7 setup done"** (or let the agent update `docs/deployment.md`, `README.md`, post the Phase 7 PASS report to Issue `#1`, and close Issue `#14`).

---

## Part C — Grafana Cloud Free Setup (Required BEFORE Phase 8, ≈10 min)

Complete this before starting **Phase 8 (Observability — Issue #15)** so the backend OpenTelemetry traces, metrics, and logs can be verified end-to-end in Grafana Cloud immediately after T14 ships.

1. Go to [https://grafana.com](https://grafana.com) → **Create free account** (no card needed).
2. Create a **Grafana Cloud Stack** in an **EU region** (closest to Render Frankfurt).
3. In your Grafana Cloud Portal (the `grafana.com/orgs/<org>` control panel), open your stack card and click **Configure** on **OpenTelemetry (OTLP)** *(or inside Grafana UI: Connections → Add new connection → OpenTelemetry)*.
4. Click **Generate now** (or create an API Token with scopes: `metrics:write`, `logs:write`, `traces:write`).
5. Copy the two generated OTLP configuration strings carefully:
   - **`OTEL_EXPORTER_OTLP_ENDPOINT`:** e.g., `https://otlp-gateway-prod-eu-west-0.grafana.net/otlp`
   - **`OTEL_EXPORTER_OTLP_HEADERS`:** `Authorization=Basic%20<base64(instanceId:token)>`
     > ⚠️ **CRITICAL PITFALL (Pitfall #6):** Check that the space between `Basic` and the base64 token is URL-encoded as **`%20`**, NOT a literal space! If a literal space is pasted into Render, `opentelemetry-exporter-otlp-proto-http` drops requests with silent HTTP `401` errors.
6. Keep these 5 values ready in your password manager (you will paste them into Render `sessionboard-dev` and `sessionboard-prod` during Phase 8 once `telemetry.py` metrics/logs support is merged):
   - `OTEL_SDK_DISABLED=false`
   - `OTEL_SERVICE_NAME=sessionboard`
   - `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
   - `OTEL_EXPORTER_OTLP_ENDPOINT=<your endpoint>`
   - `OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<your base64>`

### Optional Early Grab (Saves Time Before Phase 9 & Powers Local AI SDLC Web UI)
While logged in / setting up keys:
- **Google AI Studio API Key (Free):** Visit [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key** → keep locally for `.local/` or Phase 9 secret `GEMINI_API_KEY` (and note the free Flash model name shown, e.g., `gemini-2.5-flash`). You can also plug this key right now into the companion AI SDLC Web UI (`make ai-sdlc`)!

---

## Quick Verification Table (Tick Before Starting Phase 8)

| # | Check | Done? |
|---|---|---|
| 1 | `ghcr.io/brut0/sessionboard` (& `sessionboard-ai-sdlc`) package visibility = **Public** | [x] |
| 2 | Neon `sessionboard-dev` & `sessionboard-prod` created (Postgres 16, Frankfurt, **non-pooler URLs**) | [x] |
| 3 | Render `sessionboard-dev` & `sessionboard-prod` live (`/api/health` → `200 ok`) | [x] |
| 3b | *(Optional companion)* Render `https://essionboard-ai-sdlc.onrender.com` live with `SDLC_REQUIRE_AUTH=true` & strong `SDLC_OWNER_PASSWORD` (`GET /api/config` → `401`) | [x] |
| 4 | GitHub Secrets (`RENDER_DEPLOY_HOOK_DEV`, `RENDER_DEPLOY_HOOK_PROD`, `RENDER_DEPLOY_HOOK_AI_SDLC`) & Variables (`DEV_URL`, `PROD_URL`, `AI_SDLC_URL`) set | [x] |
| 5 | GitHub Environment `production` created with required reviewer `brut0` | [x] |
| 6 | `deploy-prod.yml` approved (`#42887628791`); `rollback.yml` run green on `dev` (`#42887682401` / `#42888034418`); `synthetic-probe.yml` green (`#42887575404`) | [x] |
| 7 | Issue `#1` Phase 7 Gate marked `PASS` & Issue `#14` closed | [x] |
| 8 | Grafana Cloud stack (EU) + OTLP endpoint & `Basic%20...` header token ready | [x] |
