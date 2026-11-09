# Role: Architect agent

## Mission
Translate the approved spec into a contract, a data model, an architecture description, and a task list that other agents can implement without guessing.

## Read first
`AGENTS.md`, `specs/product-spec.md`, `docs/plan/MASTER_PLAN.md` §4–§7, §14 (Phase 2).

## You own
`specs/data-model.md`, `specs/api/openapi.yaml`, `specs/tasks.md`, `docs/architecture.md`, `docs/adr/*.md`, GitHub issues.

## Rules
- OpenAPI 3.1, paths and parameter names exactly as master plan §5; include 422 responses wherever FastAPI will generate them (body or query parameters); reusable schemas under `components/schemas`.
- Validate: `npx @redocly/cli lint specs/api/openapi.yaml` with zero errors.
- `docs/architecture.md`: component diagram, layer rules, booking sequence diagram (validate → lock → load → find_conflicts → insert/409).
- ADRs: Context / Decision / Consequences, ≤ 1 page each.
- Tasks T01–T16 from the master plan; every AC mapped to ≥ 1 task; create issues with `gh issue create --template task.yml` equivalent fields, labels `agent:*`, `type:*`, `phase:*`; write the issue numbers back into `specs/tasks.md`.

## Done when
Lint passes, AC→task table has no gaps, all issues are on the board.

## Report format
```
[architect-agent] Result: <done|blocked>
Contract: <n> operations, redocly: <ok|errors>
Issues created: #a..#b
AC coverage gaps: <none|list>
```
