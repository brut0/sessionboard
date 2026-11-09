# SessionBoard — Testing Strategy & Traceability Matrix

> **Status:** Approved v1 (Phase 4)
> **Source of truth for:** Test suite layers, commands, acceptance criteria coverage, and contract testing.

---

## 1. Overview & Test Layers

SessionBoard enforces a multi-layered automated testing pyramid:

| Layer | Directory | Framework & Environment | Purpose & Scope |
|---|---|---|---|
| **Unit (Domain)** | `backend/tests/unit/` | `pytest` (pure in-memory Python 3.12) | Interval arithmetic (`time_utils.py`), overflow math, studio working hours (08:00–20:00), 15-minute granularity, and multi-resource conflict detection (`conflicts.py`). |
| **Integration** | `backend/tests/integration/` | `pytest` + `testcontainers` (PostgreSQL 16) | Tests all 16 Acceptance Criteria against a real PostgreSQL 16 database running Alembic migrations. Verifies advisory lock serialization, constraints, cascading rules, and REST status codes. |
| **Contract** | `backend/tests/integration/test_openapi_contract.py` | `pytest` + `PyYAML` | Verifies that FastAPI's generated `app.openapi()` matches `specs/api/openapi.yaml` in routes, HTTP methods, operation IDs, and declared response status codes. |
| **Frontend** | `frontend/src/**/*.test.tsx` | `vitest` + `jsdom` + `@testing-library/react` + `msw` | Component rendering, tab switching (Day Board / Directory), room column grouping, 15-min booking modal, 409 conflict banners, 500 Trace ID display, and status transitions. |

---

## 2. Test Execution Commands

### Full Test Suite
```bash
make test
```
Runs both backend and frontend test suites (`test-backend` then `test-frontend`). On Windows environments where `make` is not natively installed, run the underlying commands:
```powershell
# Backend
cd backend && uv run pytest -v
# Frontend
cd frontend && npm test
```

### Backend Only (Unit + Integration + Contract)
```bash
make test-backend
# or directly with uv
cd backend && uv run pytest -v
```

### Unit Tests Only (Fast in-memory, no Docker required)
```bash
cd backend && uv run pytest tests/unit/ -v
```

### Integration Tests Only (Docker required for PostgreSQL 16 container)
```bash
cd backend && uv run pytest tests/integration/ -v
```

### Frontend Only
```bash
make test-frontend
# or directly with npm
cd frontend && npm test
```

---

## 3. Frontend Component Test Architecture (Vitest + RTL + MSW)

The frontend test suite executes under Vitest in a `jsdom` environment. Network interactions with the backend API are isolated using **Mock Service Worker (MSW 2)**:
- `src/test/mocks/handlers.ts`: Defines MSW request handlers matching endpoints (`/api/rooms`, `/api/specialists`, `/api/clients`, `/api/sessions`, etc.).
- `src/test/mocks/server.ts`: Configures the MSW `setupServer` instance.
- `src/test/setup.ts`: Registers lifecycle listeners (`server.listen()`, `server.resetHandlers()`, `server.close()`).

### Frontend AC Coverage Matrix
| Component Test File | Target Component | Verifies Criteria |
|---|---|---|
| `src/App.test.tsx` | `App` | Tab navigation between Day Board and Directory |
| `src/components/DayBoard.test.tsx` | `DayBoard` | **AC-3.1** (grouping sessions by room), **AC-4.1** (Done/Cancel status transitions), **AC-4.2** (cancelled session styling), Date navigation |
| `src/components/BookingModal.test.tsx` | `BookingModal` | **AC-2.1** (successful booking submission), **AC-2.5** / **AC-2.6** (409 conflict list rendering), 5xx Trace ID error banner |
| `src/components/DirectoryPage.test.tsx` | `DirectoryPage` | **AC-1.1** (listing and creating specialists/clients/rooms), **AC-1.3** (duplicate room name 409), **AC-1.4** (204 deletion), **AC-1.5** (referenced entity delete 409) |

---

## 4. Acceptance Criteria Traceability Matrix (AC-1.1 – AC-4.2)

Every Acceptance Criterion defined in `specs/product-spec.md` is covered by automated integration tests running against PostgreSQL 16:

| AC ID | Acceptance Criterion Summary | Automated Test Location | Test Function |
|---|---|---|---|
| **AC-1.1** | Create specialists, clients, rooms (201) and list alphabetically (200) | `backend/tests/integration/test_directory_api.py` | `test_ac_1_1_list_and_create_directory_entities` |
| **AC-1.2** | Reject blank or whitespace-only names with 422 after trimming (`BR-9`) | `backend/tests/integration/test_directory_api.py` | `test_ac_1_2_blank_names_rejected` |
| **AC-1.3** | Reject duplicate room name with 409 `{"detail": "room_name_taken"}` (`BR-7`) | `backend/tests/integration/test_directory_api.py` | `test_ac_1_3_duplicate_room_name_rejected` |
| **AC-1.4** | Delete unused entity (204); non-existent ID returns 404 `{"detail": "not_found"}` | `backend/tests/integration/test_directory_api.py` | `test_ac_1_4_delete_unused_and_not_found` |
| **AC-1.5** | Delete entity referenced by sessions returns 409 `{"detail": "has_planned_sessions"}` (`BR-6`) | `backend/tests/integration/test_directory_api.py` | `test_ac_1_5_delete_referenced_entity_rejected` |
| **AC-2.1** | Valid booking returns 201 with resolved names and computed `end_time` | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_1_create_session_success` |
| **AC-2.2** | Out-of-hours booking (`<08:00` or `>20:00`) rejected with 422 (`BR-1`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_2_out_of_hours_rejected` |
| **AC-2.3** | Non-15-min start time or duration outside 15..180 rejected with 422 (`BR-2`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_3_non_15_minute_granularity_or_duration_rejected` |
| **AC-2.4** | Missing specialist, client, or room returns 404 `{"detail": "not_found"}` | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_4_missing_referenced_entity_returns_404` |
| **AC-2.5** | Overlapping session returns 409 `{"detail": "conflict", "conflicts": [...]}` (`BR-4`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_5_conflict_detection_specialist_room_client` |
| **AC-2.6** | Multi-resource conflicts sorted deterministically by `(session_id, type_order)` | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_6_conflict_response_deterministic_order` |
| **AC-2.7** | Touching intervals (`10:00–11:00` and `11:00–11:45`) produce zero conflicts (201) (`BR-3`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_7_touching_intervals_produce_zero_conflicts` |
| **AC-2.8** | Concurrency serialized via date-scoped advisory lock `pg_advisory_xact_lock` (`BR-8`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_2_8_date_advisory_lock_acquired` |
| **AC-3.1** | `GET /api/sessions?date=YYYY-MM-DD` ordered by `(room_id, start_time)` | `backend/tests/integration/test_sessions_api.py` | `test_ac_3_1_list_sessions_by_date` |
| **AC-4.1** | `PATCH /api/sessions/{id}` allows `planned -> done|cancelled` (200); other transitions return 409 (`BR-5`) | `backend/tests/integration/test_sessions_api.py` | `test_ac_4_1_status_transition_planned_to_done_or_cancelled` |
| **AC-4.2** | Cancelled sessions immediately free specialist, room, and client slots | `backend/tests/integration/test_sessions_api.py` | `test_ac_4_2_cancelled_session_frees_slot_and_historical_done_blocks` |

---

## 5. Zero-PII Policy in Tests

In accordance with Hard Rule 5:
- Test fixtures only use synthetic anonymized identifiers (e.g., `Alex Morgan`, `Sam Lee`, `Room A`, `Client 01`).
- No real names, addresses, or telephone numbers are committed to git or used in database fixtures.
- Every HTTP response is verified to carry an `X-Trace-Id` correlation header without leaking internal stack traces or database parameters.
