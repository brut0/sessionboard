# ADR 0001: Core Technology Stack and Single-Container Topology

- **Status:** Accepted
- **Date:** 2026-11-10

## Context
SessionBoard must satisfy all 12 criteria of the AI Dev Tools Zoomcamp final project (full-stack app, persistent database, unit + integration + frontend tests, single-command Docker Compose startup, public cloud deployment, CI/CD with rollback, OpenTelemetry observability, alerting, and an on-call agent) while remaining simple, fast to test, and 100% free to run.

## Decision
1. **Backend:** Python 3.12 with FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, and `uv` for deterministic dependency management.
2. **Database:** PostgreSQL 16 (`postgres:16-alpine` locally in Docker Compose; Neon serverless PostgreSQL in the cloud).
3. **Frontend:** React 19 + Vite + TypeScript + Tailwind CSS with two state-switched tabs (`Day Board` and `Directory`) and an API client generated directly from `specs/api/openapi.yaml` via `openapi-typescript` and `openapi-fetch`.
4. **Single-Container App Packaging:** A multi-stage `Dockerfile` compiles the React SPA and copies `dist/` into `backend/app/static/`, where FastAPI serves both `/api/*` and the static frontend on a single port (`${PORT:-8000}`).

## Consequences
- **Positive:** Zero CORS configuration needed in production; only one web service per environment (`dev` and `prod`) is required on Render Free, preserving the 750 monthly instance-hour pool; contract drift between frontend and backend is caught at build time.
- **Negative:** Rebuilding the Docker image compiles both frontend and backend layers (mitigated by Docker layer caching in GitHub Actions).
