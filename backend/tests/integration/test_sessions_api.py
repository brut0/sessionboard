"""Integration tests for Sessions API covering AC-2.1 through AC-4.2."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

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
def test_ac_2_2_and_2_3_invalid_time_rejected(client, base_entities):
    """AC-2.2 & AC-2.3: Out-of-hours or invalid granularity/duration return 422."""
    today = date.today().isoformat()
    base_payload = {
        "specialist_id": base_entities["specialist"]["id"],
        "client_id": base_entities["client"]["id"],
        "room_id": base_entities["room"]["id"],
        "session_date": today,
    }

    # Starts before 08:00
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "07:45", "duration_minutes": 30},
    )
    assert res.status_code == 422

    # Ends after 20:00 (19:30 + 45m = 20:15)
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "19:30", "duration_minutes": 45},
    )
    assert res.status_code == 422

    # Start not multiple of 15m
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:10", "duration_minutes": 30},
    )
    assert res.status_code == 422

    # Duration not multiple of 15m
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 25},
    )
    assert res.status_code == 422

    # Duration out of bounds (< 15 or > 180)
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 10},
    )
    assert res.status_code == 422
    res = client.post(
        "/api/sessions",
        json={**base_payload, "start_time": "09:00", "duration_minutes": 195},
    )
    assert res.status_code == 422


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
def test_ac_2_5_and_2_6_conflict_returns_409(client, base_entities):
    """AC-2.5 & AC-2.6: Conflicts return 409 {"detail": "conflict", "conflicts": [...]}."""
    today = date.today().isoformat()
    spec1 = base_entities["specialist"]["id"]
    cl1 = base_entities["client"]["id"]
    rm1 = base_entities["room"]["id"]

    # Create additional entities
    cl2 = client.post("/api/clients", json={"display_name": "Client 02"}).json()["id"]
    rm2 = client.post("/api/rooms", json={"name": "Room B"}).json()["id"]

    # Initial booking: 10:00-11:00 with spec1, cl1, rm1
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

    # Conflicting booking: 10:30-11:30 with spec1 (specialist busy)
    res_conflict = client.post(
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
    assert res_conflict.status_code == 409
    body = res_conflict.json()
    assert body["detail"] == "conflict"
    assert body["conflicts"] == [{"type": "specialist", "conflicting_session_id": session_id1}]


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
def test_ac_3_1_list_sessions_by_date(client, base_entities):
    """AC-3.1: GET /api/sessions?date=YYYY-MM-DD orders by (room_id, start_time)."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm1 = base_entities["room"]["id"]

    rm2 = client.post("/api/rooms", json={"name": "Room B"}).json()["id"]

    # Book sessions out of order
    # rm2 at 10:00
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
    # rm1 at 14:00
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
    # rm1 at 09:00
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

    # Check ordering: rm1 (09:00, 14:00), then rm2 (10:00)
    assert sessions[0]["room_id"] == rm1 and sessions[0]["start_time"] == "09:00"
    assert sessions[1]["room_id"] == rm1 and sessions[1]["start_time"] == "14:00"
    assert sessions[2]["room_id"] == rm2 and sessions[2]["start_time"] == "10:00"


@pytest.mark.integration
def test_ac_4_1_and_4_2_status_transitions(client, base_entities):
    """AC-4.1 & AC-4.2: Transitions planned -> done|cancelled, 409 on others."""
    today = date.today().isoformat()
    spec = base_entities["specialist"]["id"]
    cl = base_entities["client"]["id"]
    rm = base_entities["room"]["id"]

    # Create session 1
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

    # Try transitioning done -> cancelled -> 409
    patch_invalid = client.patch(f"/api/sessions/{s1['id']}", json={"status": "cancelled"})
    assert patch_invalid.status_code == 409
    assert patch_invalid.json() == {"detail": "invalid_status_transition"}

    # Create session 2
    s2 = client.post(
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

    # Transition planned -> cancelled
    patch_cancel = client.patch(f"/api/sessions/{s2['id']}", json={"status": "cancelled"})
    assert patch_cancel.status_code == 200
    assert patch_cancel.json()["status"] == "cancelled"

    # AC-4.2: Cancelled session immediately frees the slot!
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
    assert res_rebook.json()["status"] == "planned"
