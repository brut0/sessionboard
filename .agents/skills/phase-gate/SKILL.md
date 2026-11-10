---
name: phase-gate
description: >-
  Use this skill before claiming any SessionBoard task or phase is done. Lists the exact verification
  commands and expected results for each phase gate of docs/plan/MASTER_PLAN.md and the report format
  to post on the tracking issue.
---

# Phase gate

Never claim "done" without running the commands below and quoting their output. A gate passes only if every line matches the expected result.

## Always (every task)
| Command | Expected |
|---|---|
| `python scripts/check_repo_hygiene.py` | `OK` and exit code 0 |
| `make lint` (from Phase 3) | exit code 0 |
| `make test` (from Phase 4) | all tests pass, 0 failed, 0 errors |
| `README.md` sync check (at phase boundary) | Rubric checklist table (`✅`/`🚧`/`🔜`), test counts, live links, and repository structure map match verified state on `main` |

## Per phase
| Phase | Commands | Expected |
|---|---|---|
| 0 | `gh repo view --json visibility -q .visibility`; open repo + project URL logged out | `PUBLIC`; both pages visible |
| 1 | review BR→AC table in `specs/product-spec.md` | every BR-1…BR-8 and every error row has ≥ 1 AC; ≥ 14 ACs; human wrote "spec approved" |
| 2 | `npx @redocly/cli lint specs/api/openapi.yaml`; `gh issue list --label phase:4 --json number` | 0 errors; issues exist for T01–T16 |
| 3 | `docker compose up --build -d`; `curl -fsS http://localhost:8000/api/health`; open http://localhost:3000; `docker compose down` | `{"status":"ok","db":"ok"}`; Grafana login page |
| 4 | `make test-backend`; POST an overlapping session twice with curl | green; second POST → 409 with `{"detail":"conflict","conflicts":[...]}` |
| 5 | `make test`; manual browser scenario from master plan Phase 5 | green; data survives `docker compose restart app` |
| 6 | open a trivial PR; `gh pr checks <n>` | `hygiene`, `backend`, `frontend`, `docker` all pass |
| 7 | `curl -fsS $DEV_URL/api/version`; `curl -fsS $PROD_URL/api/health`; one `rollback.yml` run on dev | expected SHA; ok; run succeeded |
| 8 | book via UI, copy `X-Trace-Id`, find it in Grafana Tempo and Loki; `uv run pytest tests/integration/test_telemetry_no_pii.py` | trace + logs found; test passes |
| 9 | dispatch test event (master plan Phase 9 step 4); chaos drill | oncall run succeeded; incident issue closed by merged agent PR |
| 10 | fresh clone → `docker compose up --build` and `make test` | both succeed |

## Windows notes
- Docker Desktop must be running for integration tests and compose.
- On Windows, the default `python` command may point to the Microsoft Store stub if not in `uv run`. Use `uv run python scripts/check_repo_hygiene.py` (or the full Python path) locally; in Linux CI `python scripts/check_repo_hygiene.py` works directly.
- If `make` is unavailable or misbehaves, run the underlying commands listed in the `Makefile` targets directly.
- Use `curl.exe` (not the PowerShell `curl` alias) in PowerShell.

## Report format (post on the phase tracking issue)
```
[orchestrator] Phase <N> gate: <PASS|FAIL>
- <command> -> <short result>
- ...
Open items: <none|list>
```
