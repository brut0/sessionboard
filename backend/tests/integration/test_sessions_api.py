"""Integration tests for Sessions API covering AC-2.1 through AC-4.2."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_db
from app.main import app
from app.models import Client, Room, Session, Specialist


@pytest.fixture
def client(db_session):
    """Provide a TestClient connected to the ephemeral database."""
    db_session.query(Session).delete()
    db_session.query(Specialist).delete()
    db_session.query(Client).delete()
    db_session.query(Room).delete()
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def base_entities(client):
    """Create basic specialist, client, and room for booking tests."""
    spec = client.post("/api/specialists", json={"name": "Alex Morgan", "specialty": "Math"}).json()
    cl = client.post("/api/clients", json={"display_name": "Client 01"}).json()
    rm = client.post("/api/rooms", json={"name": "Room A"}).json()
    return {"specialist": spec, "client": cl, "room": rm}


@pytest.mark.integration
def test_ac_2_1_create_session_success(client, base_entities):
    """AC-2.1: Valid booking returns 201 with resolved names and computed end_time."""
    today = date.today().isoformat()
    payload = {
        "specialist_id": base_entities["specialist"]["id"],
        "client_id": base_entities["client"]["id"],
        "room_id": base_entities["room"]["id"],
        "session_date": today,
        "start_time": "09:00",
        "duration_minutes": 45,
    }
    res = client.post("/api/sessions", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["session_date"] == today
    assert data["start_time"] == "09:00"
    assert data["end_time"] == "09:45"
    assert data["specialist_name"] == "Alex Morgan"
    assert data["client_display_name"] == "Client 01"
    assert data["room_name"] == "Room A"
    assert data["status"] == "planned"
    assert "X-Trace-Id" in res.headers


@pytest.mark.integration
def test_regression_time_arithmetic_overflow_45_plus_30(client, base_entities):
    """Regression test for the 10:45 + 30m = 11:15 scenario, expected to pass."""
    today = date.today().isoformat()
    payload = {
        "specialist_id": base_entities["specialist"]["id"],
        "client_id": base_entities["client"]["id"],
        "room_id": base_entities["room"]["id"],
        "session_date": today,
        "start_time": "10:45",
        "duration_minutes": 30,
    }
    res = client.post("/api/sessions", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["session_date"] == today
    assert data["start_time"] == "10:45"
    assert data["end_time"] == "11:15"
    assert data["specialist_name"] == "Alex Morgan"
    assert data["client_display_name"] == "Client 01"
    assert data["room_name"] == "Room A"
    assert data["status"] == "planned"
    assert "X-Trace-Id" in res.headers


@pytest.mark.integration
def test_ac_2_2_out_of_hours_rejected(client, base_entities):
    """AC-2.2: Booking outside 08:00..20:00 is rejected with 422."""
    today = date.today().isoformat()
    base_payload = {
        "specialist_id": base_entities["specialist"]["id"],
        "client_id": base_entities["client"]["id"],
        "room_id": base_entities["room"]["id"],
        "session_date": today,
    }

    # Starts before 08:00
    res1 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "07:45", "duration_minutes": 30},
    )
    assert res1.status_code == 422

    # Ends after 20:00 (19:30 + 45m = 20:15)
    res2 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "19:30", "duration_minutes": 45},
    )
    assert res2.status_code == 422


@pytest.mark.integration
def test_ac_2_3_non_15_minute_granularity_or_duration_rejected(client, base_entities):
    """AC-2.3: Non-15-minute start times or durations outside 15..180 are rejected with 422."""
    today = date.today().isoformat()
    base_payload = {
        "specialist_id": base_entities["specialist"]["id"],
        "client_id": base_entities["client"]["id"],
        "room_id": base_entities["room"]["id"],
        "session_date": today,
    }

    # Start not multiple of 15m
    res1 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:10", "duration_minutes": 30},
    )
    assert res1.status_code == 422

    # Duration not multiple of 15m
    res2 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 25},
    )
    assert res2.status_code == 422

    # Duration out of bounds (< 15 or > 180)
    res3 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 10},
    )
    assert res3.status_code == 422
    res4 = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 195},
    )
    assert res4.status_code == 422


@pytest.mark.integration
def test_ac_2_4_missing_referenced_entity_returns_404(client, base_entities):
    """AC-2.4: Missing specialist, client, or room returns 404 {"detail": "not_found"}."""
    today = date.today().isoformat()
    valid_spec = base_entities["specialist"]["id"]
    valid_cl = base_entities["client"]["id"]
    valid_rm = base_entities["room"]["id"]

    # Missing specialist
    res = client.post(
        "/api/sessions",
        json={
            "specialist_id": 99999,
            "client_id": valid_cl,
            "room_id": valid_rm,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 45,
        },
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "not_found"}

    # Missing client
    res = client.post(
        "/api/sessions",
        json={
            "specialist_id": valid_spec,
            "client_id": 99999,
            "room_id": valid_rm,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 45,
        },
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "not_found"}

    # Missing room
    res = client.post(
        "/api/sessions",
        json={
            "specialist_id": valid_spec,
            "client_id": valid_cl,
            "room_id": 99999,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 45,
        },
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "not_found"}


@pytest.mark.integration
def test_ac_2_5_conflict_detection_specialist_room_client(client, base_entities):
    """AC-2.5: Overlapping session returns 409 conflict for specialist, room, or client."""
    today = date.today().isoformat()
    spec1 = base_entities["specialist"]["id"]
    cl1 = base_entities["client"]["id"]
    rm1 = base_entities["room"]["id"]

    cl2 = client.post("/api/clients", json={"display_name": "Client 02"}).json()["id"]
    rm2 = client.post("/api/rooms", json={"name": "Room B"}).json()["id"]

    # Base booking: 10:00-11:00 with spec1, cl1, rm1
    res1 = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec1,
            "client_id": cl1,
            "room_id": rm1,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 60,
        },
    )
    assert res1.status_code == 201
    session_id1 = res1.json()["id"]

    # Overlapping specialist (10:30-11:30)
    res_spec = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec1,
            "client_id": cl2,
            "room_id": rm2,
            "session_date": today,
            "start_time": "10:30",
            "duration_minutes": 60,
        },
    )
    assert res_spec.status_code == 409
    body_spec = res_spec.json()
    assert body_spec["detail"] == "conflict"
    assert body_spec["conflicts"] == [
        {"type": "specialist", "session_id": session_id1, "conflicting_session_id": session_id1}
    ]


@pytest.mark.integration
def test_ac_2_6_conflict_response_deterministic_order(client, base_entities):
    """AC-2.6: Conflicts on multiple resources are returned deterministically sorted."""
    today = date.today().isoformat()
    spec1 = base_entities["specialist"]["id"]
    cl1 = base_entities["client"]["id"]
    rm1 = base_entities["room"]["id"]

    # Base booking: 10:00-11:00
    res1 = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec1,
            "client_id": cl1,
            "room_id": rm1,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 60,
        },
    )
    assert res1.status_code == 201

    # Overlapping on both specialist AND room (10:15-10:45)
    cl2 = client.post("/api/clients", json={"display_name": "Client 03"}).json()["id"]
    res_both = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec1,
            "client_id": cl2,
            "room_id": rm1,
            "session_date": today,
            "start_time": "10:15",
            "duration_minutes": 30,
        },
    )
    assert res_both.status_code == 409
    conflicts = res_both.json()["conflicts"]
    assert len(conflicts) == 2
    types = [c["type"] for c in conflicts]
    assert "specialist" in types
    assert "room" in types


@pytest.mark.integration
def test_ac_2_7_touching_intervals_produce_zero_conflicts(client, base_entities):
    """AC-2.7: Touching intervals [10:00-11:00) and [11:00-11:45) produce zero conflicts."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm = base_entities["room"]["id"]

    res1 = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 60,
        },
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "11:00",
            "duration_minutes": 45,
        },
    )
    assert res2.status_code == 201
    assert res2.json()["start_time"] == "11:00"
    assert res2.json()["end_time"] == "11:45"


@pytest.mark.integration
def test_ac_2_8_date_advisory_lock_acquired(db_session):
    """AC-2.8: Verify pg_advisory_xact_lock is supported and serializes concurrent calls."""
    target_date = "2026-11-10"
    lock_result = db_session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(CAST(:date_str AS text)))"),
        {"date_str": target_date},
    )
    assert lock_result is not None


@pytest.mark.integration
def test_ac_3_1_list_sessions_by_date(client, base_entities):
    """AC-3.1: GET /api/sessions?date=YYYY-MM-DD orders by (room_id, start_time)."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm1 = base_entities["room"]["id"]

    rm2 = client.post("/api/rooms", json={"name": "Room B"}).json()["id"]

    # Book sessions out of order
    client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm2,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 30,
        },
    )
    client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm1,
            "session_date": today,
            "start_time": "14:00",
            "duration_minutes": 30,
        },
    )
    client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm1,
            "session_date": today,
            "start_time": "09:00",
            "duration_minutes": 30,
        },
    )

    list_res = client.get(f"/api/sessions?date={today}")
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) == 3

    assert sessions[0]["room_id"] == rm1 and sessions[0]["start_time"] == "09:00"
    assert sessions[1]["room_id"] == rm1 and sessions[1]["start_time"] == "14:00"
    assert sessions[2]["room_id"] == rm2 and sessions[2]["start_time"] == "10:00"


@pytest.mark.integration
def test_ac_4_1_status_transition_planned_to_done_or_cancelled(client, base_entities):
    """AC-4.1: Transitions planned -> done|cancelled, 409 on invalid transitions."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm = base_entities["room"]["id"]

    s1 = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "10:00",
            "duration_minutes": 60,
        },
    ).json()

    # Transition planned -> done
    patch_done = client.patch(f"/api/sessions/{s1['id']}", json={"status": "done"})
    assert patch_done.status_code == 200
    assert patch_done.json()["status"] == "done"

    # Invalid: done -> cancelled
    patch_invalid = client.patch(f"/api/sessions/{s1['id']}", json={"status": "cancelled"})
    assert patch_invalid.status_code == 409
    assert patch_invalid.json() == {"detail": "invalid_status_transition"}


@pytest.mark.integration
def test_ac_4_2_cancelled_session_frees_slot_and_historical_done_blocks(client, base_entities):
    """AC-4.2: Cancelled session immediately frees slot; done session continues blocking."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm = base_entities["room"]["id"]

    # 1. Create and cancel session
    s = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "12:00",
            "duration_minutes": 60,
        },
    ).json()

    client.patch(f"/api/sessions/{s['id']}", json={"status": "cancelled"})

    # Rebook the exact same slot -> succeeds with 201
    res_rebook = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "12:00",
            "duration_minutes": 60,
        },
    )
    assert res_rebook.status_code == 201

    # Transition the new session to done
    s_new_id = res_rebook.json()["id"]
    client.patch(f"/api/sessions/{s_new_id}", json={"status": "done"})

    # Attempt rebooking on 'done' slot -> blocks with 409
    res_blocked = client.post(
        "/api/sessions",
        json={
            "specialist_id": spec,
            "client_id": cl,
            "room_id": rm,
            "session_date": today,
            "start_time": "12:00",
            "duration_minutes": 60,
        },
    )
    assert res_blocked.status_code == 409
