# ADR 0003: Synchronous SQLAlchemy 2.x with psycopg 3 and Date Advisory Locks

- **Status:** Accepted
- **Date:** 2026-11-10

## Context
The prototype used `SQLite` with `aiosqlite` and async SQLAlchemy. For SessionBoard we run PostgreSQL 16 both locally (via Docker Compose and `testcontainers` on Windows and Linux) and in the cloud (Neon), and we must prevent race-condition double bookings (`BR-8`).

## Decision
1. **Synchronous SQLAlchemy 2.x + `psycopg 3` (`psycopg[binary]`):** Use synchronous `Engine` and `Session` (`postgresql+psycopg://`) instead of `AsyncEngine`/`asyncpg`.
2. **Transaction-Scoped Advisory Lock for Bookings:** Serialize concurrent `POST /api/sessions` requests on the same `session_date` by executing `SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))` at the start of the booking transaction.

## Consequences
- **Positive:** Eliminates `SelectorEventLoop` vs `ProactorEventLoop` incompatibilities with `psycopg` on Windows; simplifies integration testing with FastAPI's synchronous `TestClient` and `testcontainers`; `OpenTelemetry` `SQLAlchemyInstrumentor` instruments standard sync engines out of the box; advisory locks prevent phantom read/write double bookings without requiring `SERIALIZABLE` retry loops across the whole database.
- **Negative:** Sync endpoints run in FastAPI's threadpool rather than the main asyncio loop, which is negligible for a small studio scheduler.
