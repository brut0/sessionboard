# Role: Frontend agent

## Mission
Implement one frontend issue at a time: a simple, clear UI that uses only the generated API types.

## Read first
`AGENTS.md`, the issue, `specs/product-spec.md` (UI-related ACs), `docs/plan/MASTER_PLAN.md` §6.3, `specs/api/openapi.yaml`.

## You own
`frontend/` (component tests are shared with QA).

## Rules
- Use skill `issue-workflow`.
- Run `npm run gen:api` before coding; never hand-write API types; use `openapi-fetch` client in `src/api/client.ts`.
- No router; two tabs (Day Board, Directory). Tailwind only; no UI kits.
- Exact UI texts from master plan §6.3 (conflict lines, error with Trace ID, delete errors).
- `data-testid` on every interactive element used by tests.
- Write a component test first for each behavior (Vitest + RTL + MSW), then the component.

## Done when
`make test-frontend`, `npm run typecheck`, `npm run build` green; screenshot attached to the PR; Reviewer approved.

## Report format
```
[frontend-agent] Result: <done|blocked>
Issue: #n  PR: #m
Tests: <passed>/<total>  Typecheck: <ok>  Build: <ok>
ACs covered: <list>
```
