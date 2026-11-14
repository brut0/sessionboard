# SessionBoard Verification Commands & Windows Notes

Shared verification reference for `feature-sdlc`, `issue-workflow`, `phase-gate`, and `release-and-rollback`.

## Standard Verification Suite

Run from repository root:

```powershell
# 1. Hygiene (English-only + forbidden prototype terms across working tree & commits)
uv run python scripts/check_repo_hygiene.py

# 2. Backend lint, format & full test suite (Docker Desktop must be running for testcontainers)
cd backend; uv run ruff check .; uv run ruff format --check .; uv run pytest -v; cd ..

# 3. Frontend OpenAPI drift check, typecheck, tests & production build
cd frontend; npm run gen:api; git diff --exit-code src/api/schema.d.ts; npm run typecheck; npm test; npm run build; cd ..
```

## Container / Runtime Smoke Check

```powershell
docker compose up --build -d
curl.exe -fsS http://localhost:8000/api/health
docker compose down
```

## Windows Notes

- **Docker Desktop** must be running for backend integration tests (`testcontainers`) and `docker compose`.
- **`python` stub:** On Windows, bare `python` may invoke the Microsoft Store alias if outside `uv run`. Use `uv run python scripts/check_repo_hygiene.py` locally; Linux CI invokes `python scripts/check_repo_hygiene.py` directly.
- **`make` fallback:** If `make` is unavailable or misbehaves on Windows, run the underlying commands listed in `Makefile` (such as the `uv run` and `npm run` blocks above) directly.
- **PowerShell `curl`:** Always use `curl.exe` instead of `curl` (which is aliased to `Invoke-WebRequest` in PowerShell).
