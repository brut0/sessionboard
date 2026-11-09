# ADR 0002: Zero-Cost Cloud Hosting, Telemetry Stack, and Headless On-Call Agent

- **Status:** Accepted
- **Date:** 2026-11-10

## Context
We need isolated `dev` and `prod` cloud deployments with persistent PostgreSQL, full OpenTelemetry collection (traces, metrics, structured logs), alerting on user-impact SLI degradation, and an automated on-call responder agent — without requiring credit cards, paid subscriptions, or expiring 30-day database trials.

## Decision
1. **Compute Hosting:** Render Free Web Services (`sessionboard-dev` and `sessionboard-prod`) configured as **Existing Image** services pulling `ghcr.io/<owner>/sessionboard:<git-sha>`. Deployments and rollbacks trigger via Render Deploy Hooks with `?key=...&imgURL=...`.
2. **Managed PostgreSQL:** Neon Free Tier using two separate Neon projects (`sessionboard-dev` and `sessionboard-prod`) so each environment gets its own independent 100 CU-hour/month compute allowance and never expires after 30 days (unlike Render's free Postgres).
3. **Observability & Alerting:** Local development uses `grafana/otel-lgtm` in Docker Compose; cloud environments export OTLP/HTTP to **Grafana Cloud Free** (Tempo, Loki, Prometheus/Mimir, Alerting) which supports custom-payload webhooks to GitHub `repository_dispatch`.
4. **On-Call Responder Agent:** `.github/workflows/oncall.yml` first executes a **deterministic rollback** (`rollback.yml`) to restore service immediately, then invokes headless **Gemini CLI** (`@google/gemini-cli` with a free Google AI Studio key) to write a regression test and fix PR, verified deterministically by `uv run pytest` before opening the PR.

## Consequences
- **Positive:** $0 cost with no credit card required across all providers; deterministic rollback guarantees mitigation even if the LLM hits free-tier rate limits (`HTTP 429`).
- **Negative:** Render Free instances spin down after 15 minutes of inactivity (~30–60s cold start), so CD smoke tests must poll `/api/version` with up to a 10-minute timeout, and the synthetic probe runs hourly rather than every minute to stay within the 750 free instance-hour cap.
