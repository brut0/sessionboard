# SessionBoard — Product Specification

> **Status:** Approved v1
> **Source of truth for:** Functional requirements, business rules, error contract, and acceptance criteria.

---

## 1. Problem Statement & Personas

### 1.1 Problem
Small studios (tutoring centers, music or coaching studios, therapy practices) with 2–5 rooms and a handful of specialists often manage their daily schedule in shared spreadsheets or chat threads. Because three independent resources must be free at the same time — the **specialist**, the **room**, and the **client** — administrators frequently create accidental double bookings. Detecting overlaps manually across rows and tabs is error-prone, especially when sessions have varying durations (15 to 180 minutes) or when cancelled sessions free up slots.

### 1.2 Solution Overview
**SessionBoard** is a lightweight web application where a studio administrator manages the studio directory (specialists, clients, rooms) and books sessions on a visual daily board. Every booking request is validated atomically against working hours, time-slot granularity, and resource availability. If a specialist, room, or client is already booked in an overlapping non-cancelled session on that date, the system rejects the booking with HTTP `409 Conflict` and returns the exact list of conflicting resources and session IDs.

### 1.3 Persona
- **Studio Administrator (single persona):** Responsible for maintaining the list of active specialists, clients, and rooms, scheduling daily sessions, and marking sessions as `done` or `cancelled` throughout the day.
- Authentication and role-based access control are intentionally out of scope (see §6).

---

## 2. User Stories & Functional Scope

| Story ID | Feature | User Story | UI Location |
|---|---|---|---|
| **US-1** | **F1 — Studio Directory** | As a studio administrator, I want to list, create, and delete specialists, clients, and rooms so that the daily board reflects our studio's resources, while preventing deletion of resources that still have planned sessions. | **Directory** tab |
| **US-2** | **F2 — Conflict-Free Session Booking** | As a studio administrator, I want to book a session for a specialist, client, and room on a given date and time, and have the system reject any booking that overlaps with an existing non-cancelled session for any of those three resources. | **Booking Modal** (opened from **Day Board**) |
| **US-3** | **F3 — Daily Schedule Board** | As a studio administrator, I want to view all sessions for a selected date grouped into one column per room, ordered by start time, and navigate between days (`Prev`, `Today`, `Next`). | **Day Board** tab |
| **US-4** | **F4 — Session Lifecycle Status** | As a studio administrator, I want to mark a `planned` session as `done` or `cancelled`, and have `cancelled` sessions immediately release their specialist, room, and client for new bookings. | **Day Board** tab (session card actions) |

---

## 3. Business Rules (Mandatory Invariants)

- **BR-1 (Working hours):** Working hours are `08:00`–`20:00` local studio time (`480`–`1200` minutes since midnight). A session must start at or after `08:00` and end at or before `20:00` (`start_minutes >= 480` and `start_minutes + duration_minutes <= 1200`). No time zones are stored or converted.
- **BR-2 (Granularity & duration):** `start_time` minutes must be in `{00, 15, 30, 45}`. `duration_minutes` must be a multiple of `15` in the inclusive range `[15, 180]` (`{15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180}`).
- **BR-3 (Interval overlap):** Two sessions overlap when they are on the same `session_date` and their half-open intervals `[start, end)` intersect (`max(start_a, start_b) < min(end_a, end_b)`). Touching intervals (where one ends at the exact minute the other starts, e.g. `10:00–11:00` and `11:00–11:30`) do **not** overlap.
- **BR-4 (Conflict detection):** A new session conflicts with an existing session when they overlap (BR-3), the existing session's `status` is **not** `cancelled` (i.e. `planned` or `done`), and they share the `specialist_id`, the `room_id`, or the `client_id`. All conflicts are reported, one entry per `(type, existing_session_id)`, ordered by `session_id` ascending and then `type` in `("specialist", "room", "client")` order.
- **BR-5 (Status transitions):** Newly created sessions start in status `planned`. Only transitions `planned → done` and `planned → cancelled` are allowed. Any other transition (`done → cancelled`, `done → planned`, `cancelled → done`, `cancelled → planned`, or `planned → planned`) is rejected with HTTP `409`.
- **BR-6 (Referential protection on delete):** A specialist, client, or room that has at least one session with `status = 'planned'` (on any date) cannot be deleted and returns HTTP `409`. If a resource has only `done` or `cancelled` sessions, deletion is also blocked by `ON DELETE RESTRICT` unless zero sessions reference it; to keep behavior uniform and predictable, **any** resource referenced by a `planned` session returns `409 {"detail": "has_planned_sessions"}`, and if referenced only by historical (`done`/`cancelled`) sessions, the database `RESTRICT` constraint is caught and also returns `409 {"detail": "has_planned_sessions"}` (see Clarification C-1).
- **BR-7 (Unique room names):** Room names are unique (case-sensitive) after trimming leading/trailing whitespace. Creating a room whose trimmed `name` already exists returns HTTP `409 {"detail": "room_name_taken"}`.
- **BR-8 (Concurrency serialization):** Concurrent booking requests (`POST /api/sessions`) for the same `session_date` are serialized using a PostgreSQL transaction-scoped advisory lock (`SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))`), ensuring two simultaneous requests cannot both insert conflicting sessions.
- **BR-9 (String trimming & non-empty validation):** All text inputs (`Specialist.name`, `Specialist.specialty`, `Client.display_name`, `Room.name`) are trimmed of leading and trailing whitespace before validation and persistence. If a string is empty after trimming or exceeds its maximum length (`100` chars for specialist/client fields, `50` chars for room name), the request is rejected with HTTP `422`.

---

## 4. Error Contract

| Situation | HTTP Status | Response Body |
|---|---|---|
| Schema, BR-1, BR-2, or BR-9 validation failure | `422 Unprocessable Entity` | FastAPI standard validation error payload `{"detail": [...]}` |
| Referenced `specialist_id`, `client_id`, `room_id`, or `session_id` does not exist | `404 Not Found` | `{"detail": "not_found"}` |
| Booking conflicts (BR-4) | `409 Conflict` | `{"detail": "conflict", "conflicts": [{"type": "specialist" \| "room" \| "client", "session_id": 12}]}` |
| Invalid status transition (BR-5) | `409 Conflict` | `{"detail": "invalid_status_transition"}` |
| Delete blocked by existing sessions (BR-6) | `409 Conflict` | `{"detail": "has_planned_sessions"}` |
| Duplicate room name (BR-7) | `409 Conflict` | `{"detail": "room_name_taken"}` |
| Unexpected unhandled server error | `500 Internal Server Error` | `{"detail": "internal_error", "trace_id": "<32-char hex>"}` |

Every HTTP response from the backend (2xx, 4xx, 5xx) includes the response header `X-Trace-Id: <32-char hex>`.

---

## 5. Acceptance Criteria (Given / When / Then)

### US-1: Studio Directory (F1)

- **AC-1.1 — Create and list directory entities sorted alphabetically**
  - **Given** an empty database
  - **When** the administrator creates specialists `"Sam Lee"` (`"Guitar coach"`) and `"Alex Morgan"` (`"Math tutor"`), clients `"Client 02"` and `"Client 01"`, and rooms `"Room B"` and `"Room A"`
  - **Then** `GET /api/specialists` returns `200` with `["Alex Morgan", "Sam Lee"]` in that order, `GET /api/clients` returns `200` with `["Client 01", "Client 02"]`, and `GET /api/rooms` returns `200` with `["Room A", "Room B"]`.

- **AC-1.2 — Reject blank or whitespace-only directory names (BR-9, 422)**
  - **Given** the API is running
  - **When** the administrator sends `POST /api/specialists` with `{"name": "   ", "specialty": "Math"}` or `POST /api/clients` with `{"display_name": ""}` or `POST /api/rooms` with `{"name": " \t "}`
  - **Then** each request responds with `422 Unprocessable Entity`.

- **AC-1.3 — Reject duplicate room name (BR-7, 409)**
  - **Given** a room named `"Room A"` already exists
  - **When** the administrator sends `POST /api/rooms` with `{"name": "Room A"}` (or `"  Room A  "`)
  - **Then** the API responds with `409 Conflict` and body `{"detail": "room_name_taken"}`.

- **AC-1.4 — Delete unused directory entity succeeds (204) and missing entity returns 404**
  - **Given** a specialist with `id = 99` does not exist, and a specialist `id = S1` exists with no sessions
  - **When** the administrator sends `DELETE /api/specialists/S1` and then `DELETE /api/specialists/99`
  - **Then** the first request responds with `204 No Content` and removes `S1`, and the second responds with `404 Not Found` and body `{"detail": "not_found"}`.

- **AC-1.5 — Block deletion of specialist, client, or room with planned sessions (BR-6, 409)**
  - **Given** specialist `S1`, client `C1`, and room `R1` have a `planned` session on `2026-12-01` at `10:00`
  - **When** the administrator sends `DELETE /api/specialists/{S1}`, `DELETE /api/clients/{C1}`, or `DELETE /api/rooms/{R1}`
  - **Then** each request responds with `409 Conflict` and body `{"detail": "has_planned_sessions"}`, and the entities remain in the database.

---

### US-2: Conflict-Free Session Booking (F2)

- **AC-2.1 — Valid booking within working hours succeeds (BR-1, BR-2)**
  - **Given** specialist `S1` (`"Alex Morgan"`), client `C1` (`"Client 01"`), and room `R1` (`"Room A"`) exist and have no sessions on `2026-12-01`
  - **When** the administrator sends `POST /api/sessions` with `{"specialist_id": S1, "client_id": C1, "room_id": R1, "session_date": "2026-12-01", "start_time": "10:45", "duration_minutes": 30}`
  - **Then** the API responds with `201 Created` and a `Session` payload containing `start_time: "10:45"`, `end_time: "11:15"`, `status: "planned"`, and the resolved names `"Alex Morgan"`, `"Client 01"`, `"Room A"`.

- **AC-2.2 — Reject booking outside working hours 08:00–20:00 (BR-1, 422)**
  - **Given** valid `S1`, `C1`, `R1`
  - **When** the administrator attempts to book on `2026-12-01` at `07:45` for `30` min (starts before `08:00`) OR at `19:30` for `45` min (ends at `20:15`, after `20:00`), whereas booking at `19:30` for `30` min (ends at `20:00`) is also tested
  - **Then** the `07:45` and `19:30` (`45` min) requests fail with `422 Unprocessable Entity`, while the `19:30` (`30` min) request succeeds with `201 Created`.

- **AC-2.3 — Reject non-15-minute start time or invalid duration (BR-2, 422)**
  - **Given** valid `S1`, `C1`, `R1`
  - **When** the administrator attempts to book at `10:10` for `30` min, or at `10:00` for `25` min, or at `10:00` for `0` min, or at `10:00` for `195` min
  - **Then** each request fails with `422 Unprocessable Entity`.

- **AC-2.4 — Booking referencing non-existent specialist, client, or room returns 404**
  - **Given** specialist `S1`, client `C1`, room `R1` exist, and ID `9999` does not exist
  - **When** the administrator sends `POST /api/sessions` with `specialist_id = 9999` (or `client_id = 9999`, or `room_id = 9999`)
  - **Then** the API responds with `404 Not Found` and body `{"detail": "not_found"}`.

- **AC-2.5 — Detect room overlap conflict (BR-3, BR-4, 409)**
  - **Given** session `E1` is `planned` on `2026-12-01` from `10:00` to `11:00` (`duration_minutes: 60`) in room `R1` with specialist `S1` and client `C1`
  - **When** the administrator books on `2026-12-01` at `10:30` for `30` min in the **same** room `R1` with a different specialist `S2` and different client `C2`
  - **Then** the API responds with `409 Conflict` and body `{"detail": "conflict", "conflicts": [{"type": "room", "session_id": E1}]}`.

- **AC-2.6 — Detect specialist overlap, client overlap, and multi-resource conflict in a single booking (BR-4, 409)**
  - **Given** session `E1` is `planned` on `2026-12-01` `10:00–11:00` with `(S1, C1, R1)`
  - **When** the administrator books on `2026-12-01` `09:30–10:15` (`duration_minutes: 45`) with the same `(S1, C1, R1)`
  - **Then** the API responds with `409 Conflict` and body `{"detail": "conflict", "conflicts": [{"type": "specialist", "session_id": E1}, {"type": "room", "session_id": E1}, {"type": "client", "session_id": E1}]}`.

- **AC-2.7 — Allow back-to-back touching intervals without conflict (BR-3)**
  - **Given** session `E1` is `planned` on `2026-12-01` `10:00–11:00` with `(S1, C1, R1)`
  - **When** the administrator books on `2026-12-01` `11:00–11:45` (`duration_minutes: 45`) and `09:15–10:00` (`duration_minutes: 45`) with the same `(S1, C1, R1)`
  - **Then** both requests succeed with `201 Created`.

- **AC-2.8 — Serialize concurrent bookings on the same date (BR-8)**
  - **Given** valid `S1`, `C1`, `R1` and no sessions on `2026-12-02`
  - **When** two booking requests for `2026-12-02` `14:00–15:00` in room `R1` are submitted concurrently
  - **Then** the database advisory lock serializes them so that exactly one returns `201 Created` and the other returns `409 Conflict`.

---

### US-3: Daily Schedule Board (F3)

- **AC-3.1 — List sessions for a date sorted by room_id and start_time**
  - **Given** sessions exist on `2026-12-01` (in `R1` at `14:00` and `09:00`, and in `R2` at `10:00`) and another session exists on `2026-12-02`
  - **When** the administrator requests `GET /api/sessions?date=2026-12-01`
  - **Then** the API returns `200 OK` with only the 3 sessions of `2026-12-01`, ordered `(R1 09:00, R1 14:00, R2 10:00)`.

---

### US-4: Session Lifecycle Status (F4)

- **AC-4.1 — Mark a planned session as done or cancelled, and reject invalid transitions (BR-5, 409)**
  - **Given** planned sessions `E1` and `E2` exist, and session `9999` does not exist
  - **When** the administrator sends `PATCH /api/sessions/{E1}` with `{"status": "done"}`, then `PATCH /api/sessions/{E1}` with `{"status": "cancelled"}`, and `PATCH /api/sessions/9999` with `{"status": "done"}`
  - **Then** the first request returns `200 OK` with `status: "done"`, the second returns `409 Conflict` with `{"detail": "invalid_status_transition"}`, and the third returns `404 Not Found` with `{"detail": "not_found"}`.

- **AC-4.2 — Cancelled session frees its slot for rebooking, while done session still blocks overlaps (BR-4)**
  - **Given** session `E1` on `2026-12-01` `10:00–11:00` in `R1` is marked `cancelled`, and session `E2` on `2026-12-01` `12:00–13:00` in `R1` is marked `done`
  - **When** the administrator books `R1` on `2026-12-01` `10:00–11:00`, and then attempts to book `R1` on `2026-12-01` `12:15–12:45`
  - **Then** the `10:00–11:00` booking succeeds with `201 Created`, while the `12:15–12:45` booking fails with `409 Conflict` referencing `E2`.

---

## 6. Traceability Matrix (Business Rules & Error Contract → Acceptance Criteria)

| Rule / Error Row | Covered by Acceptance Criteria |
|---|---|
| **BR-1** (Working hours 08:00–20:00) | AC-2.1, AC-2.2 |
| **BR-2** (15-min granularity, duration 15–180) | AC-2.1, AC-2.3 |
| **BR-3** (Interval overlap & touching allowed) | AC-2.5, AC-2.7 |
| **BR-4** (Conflict detection: specialist/room/client, non-cancelled) | AC-2.5, AC-2.6, AC-4.2 |
| **BR-5** (Status transitions only from `planned`) | AC-4.1 |
| **BR-6** (Delete blocked when sessions exist) | AC-1.5 |
| **BR-7** (Unique room names) | AC-1.3 |
| **BR-8** (Advisory lock concurrency serialization) | AC-2.8 |
| **BR-9** (Trimming & non-empty strings) | AC-1.2, AC-1.3 |
| **HTTP 422** (Validation failure) | AC-1.2, AC-2.2, AC-2.3 |
| **HTTP 404** (`not_found`) | AC-1.4, AC-2.4, AC-4.1 |
| **HTTP 409** (`conflict`) | AC-2.5, AC-2.6, AC-2.8, AC-4.2 |
| **HTTP 409** (`invalid_status_transition`) | AC-4.1 |
| **HTTP 409** (`has_planned_sessions`) | AC-1.5 |
| **HTTP 409** (`room_name_taken`) | AC-1.3 |
| **HTTP 500** (`internal_error` + `trace_id`) | Verified in `specs/nfr-observability.md` & integration error-handler test |

---

## 7. Non-Goals (Permanently Out of Scope)

The following features must **never** be added to SessionBoard:
1. Automated schedule generation, mathematical solvers (OR-Tools / CP-SAT), or free-slot search (`free-slots` endpoint).
2. Weekly master templates, recurring schedules, or marathon chains.
3. Pricing, subscriptions, salaries, payroll, P&L analytics, or financial calculations.
4. Specialist or client absence/vacation cascades.
5. Messenger exports (WhatsApp, Telegram, SMS), PDF/Excel exports, or Excel imports.
6. User authentication, roles, permissions, or multi-tenancy.
7. Internationalization (i18n) or non-English UI text.

---

## 8. Clarifications

- **C-1 (Deleting a resource that has only `done` or `cancelled` sessions):**
  - *Question:* BR-6 states that a resource with a `planned` session cannot be deleted, while the database schema uses `ON DELETE RESTRICT` on `sessions.specialist_id`, `client_id`, and `room_id`. What happens if an admin tries to delete a resource that has only `done` or `cancelled` sessions?
  - *Resolution:* To preserve historical session integrity (`ON DELETE RESTRICT`) while keeping the API error contract simple, deleting a resource that is referenced by **any** session (or specifically checking `planned` first and catching `IntegrityError` for historical sessions) returns `409 Conflict` with `{"detail": "has_planned_sessions"}`. In UI copy: `"Cannot delete: resource is referenced by existing sessions."`
- **C-2 (Order of `conflicts` array in 409 response):**
  - *Question:* In what order should items appear in `conflicts` when multiple sessions or multiple resource types conflict?
  - *Resolution:* Sorted by `session_id` ascending, and for the same `session_id` in the fixed order `("specialist", "room", "client")`.
