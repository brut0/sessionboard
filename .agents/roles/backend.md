# Role: Backend agent

## Mission
Implement one backend issue at a time with strict TDD so that the API matches `specs/api/openapi.yaml` and every linked AC passes.

## Read first
`AGENTS.md`, the issue, linked spec sections, `specs/api/openapi.yaml`, `docs/plan/MASTER_PLAN.md` §4–§7 and §16.

## You own
`backend/` except `backend/tests/integration/` files owned by QA (you may add unit tests and fix fixtures).

## Rules
- Use skill `issue-workflow` (start comment, branch, trailers, PR).
- TDD loop per behavior: write failing test → `cd backend && uv run pytest <test> -q` shows FAIL → implement → PASS → commit.
- Sync SQLAlchemy 2.x + psycopg 3; Alembic only (no `create_all`); domain layer pure; time math in minutes since midnight.
- Booking must take `pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))` inside the transaction.
- Route decorators declare `responses=` for 404/409/503 so the contract test passes.
- No names or bodies in logs/spans/metrics.
- Dependencies via `uv add`; commit `uv.lock`.

## Done when
`make test-backend` and `make lint` are green, the issue's ACs are checked in the PR, Reviewer approved.

## Report format
```
[backend-agent] Result: <done|blocked>
Issue: #n  PR: #m  Branch: <name>
Tests: <passed>/<total>  Lint: <ok>
ACs covered: <list>
Notes/spec gaps: <none|list>
```
