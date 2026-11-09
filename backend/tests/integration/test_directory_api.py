"""Integration tests for Studio Directory API covering AC-1.1 through AC-1.5."""

from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Client, Room, Session, Specialist


@pytest.fixture
def client(db_session):
    """Provide a TestClient using the test's transactional database session."""
    # Clean directory tables before each test
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


@pytest.mark.integration
def test_ac_1_1_list_and_create_directory_entities(client):
    """AC-1.1: List endpoints return 200 sorted alphabetically; POST returns 201."""
    # Create specialists
    res1 = client.post("/api/specialists", json={"name": "Zoe Miller", "specialty": "Piano"})
    assert res1.status_code == 201
    res2 = client.post("/api/specialists", json={"name": "Alice Smith", "specialty": "Guitar"})
    assert res2.status_code == 201

    list_spec = client.get("/api/specialists")
    assert list_spec.status_code == 200
    names = [s["name"] for s in list_spec.json()]
    assert names == ["Alice Smith", "Zoe Miller"]

    # Create clients
    c1 = client.post("/api/clients", json={"display_name": "Charlie"})
    assert c1.status_code == 201
    c2 = client.post("/api/clients", json={"display_name": "Bob"})
    assert c2.status_code == 201

    list_clients = client.get("/api/clients")
    assert list_clients.status_code == 200
    display_names = [c["display_name"] for c in list_clients.json()]
    assert display_names == ["Bob", "Charlie"]

    # Create rooms
    r1 = client.post("/api/rooms", json={"name": "Studio B"})
    assert r1.status_code == 201
    r2 = client.post("/api/rooms", json={"name": "Studio A"})
    assert r2.status_code == 201

    list_rooms = client.get("/api/rooms")
    assert list_rooms.status_code == 200
    room_names = [r["name"] for r in list_rooms.json()]
    assert room_names == ["Studio A", "Studio B"]


@pytest.mark.integration
def test_ac_1_2_blank_names_rejected(client):
    """AC-1.2: Blank or whitespace-only names are rejected with 422 after trimming (BR-9)."""
    # Specialist
    res = client.post("/api/specialists", json={"name": "   ", "specialty": "Tutor"})
    assert res.status_code == 422

    res = client.post("/api/specialists", json={"name": "Alex", "specialty": "   "})
    assert res.status_code == 422

    # Client
    res = client.post("/api/clients", json={"display_name": "   "})
    assert res.status_code == 422

    # Room
    res = client.post("/api/rooms", json={"name": "   "})
    assert res.status_code == 422


@pytest.mark.integration
def test_ac_1_3_duplicate_room_name_rejected(client):
    """AC-1.3: Duplicate room name returns 409 {"detail": "room_name_taken"} (BR-7)."""
    res1 = client.post("/api/rooms", json={"name": "Main Hall"})
    assert res1.status_code == 201

    res2 = client.post("/api/rooms", json={"name": "Main Hall"})
    assert res2.status_code == 409
    assert res2.json() == {"detail": "room_name_taken"}


@pytest.mark.integration
def test_ac_1_4_delete_unused_and_not_found(client):
    """AC-1.4: Deleting unused returns 204; deleting non-existent ID returns 404."""
    # 404 checks
    assert client.delete("/api/specialists/9999").status_code == 404
    assert client.delete("/api/specialists/9999").json() == {"detail": "not_found"}

    assert client.delete("/api/clients/9999").status_code == 404
    assert client.delete("/api/clients/9999").json() == {"detail": "not_found"}

    assert client.delete("/api/rooms/9999").status_code == 404
    assert client.delete("/api/rooms/9999").json() == {"detail": "not_found"}

    # Create and delete specialist
    s = client.post("/api/specialists", json={"name": "Temp", "specialty": "T"}).json()
    assert client.delete(f"/api/specialists/{s['id']}").status_code == 204

    # Create and delete client
    c = client.post("/api/clients", json={"display_name": "Temp Client"}).json()
    assert client.delete(f"/api/clients/{c['id']}").status_code == 204

    # Create and delete room
    r = client.post("/api/rooms", json={"name": "Temp Room"}).json()
    assert client.delete(f"/api/rooms/{r['id']}").status_code == 204


@pytest.mark.integration
def test_ac_1_5_delete_referenced_entity_rejected(client, db_session):
    """AC-1.5: Deleting entity referenced by sessions returns 409 (BR-6)."""
    spec = Specialist(name="Dr. Taylor", specialty="Neurology")
    cl = Client(display_name="Client Test")
    rm = Room(name="Room FK Test")
    db_session.add_all([spec, cl, rm])
    db_session.flush()

    sess = Session(
        specialist_id=spec.id,
        client_id=cl.id,
        room_id=rm.id,
        session_date=date.today(),
        start_time=time(10, 0),
        duration_minutes=60,
        status="planned",
    )
    db_session.add(sess)
    db_session.flush()

    # Attempt deleting specialist -> 409
    res_s = client.delete(f"/api/specialists/{spec.id}")
    assert res_s.status_code == 409
    assert res_s.json() == {"detail": "has_planned_sessions"}

    # Attempt deleting client -> 409
    res_c = client.delete(f"/api/clients/{cl.id}")
    assert res_c.status_code == 409
    assert res_c.json() == {"detail": "has_planned_sessions"}

    # Attempt deleting room -> 409
    res_r = client.delete(f"/api/rooms/{rm.id}")
    assert res_r.status_code == 409
    assert res_r.json() == {"detail": "has_planned_sessions"}
