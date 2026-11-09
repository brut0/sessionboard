"""Integration tests verifying Alembic migrations, database constraints, and seeding."""

from datetime import date, time

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import Client, Room, Session, Specialist
from app.seed import seed_database


@pytest.mark.integration
def test_tables_created_via_alembic(db_engine):
    """AC-1.1: Verify all 4 required tables exist in PostgreSQL schema."""
    inspector = inspect(db_engine)
    table_names = inspector.get_table_names()
    assert "specialists" in table_names
    assert "clients" in table_names
    assert "rooms" in table_names
    assert "sessions" in table_names


@pytest.mark.integration
def test_room_name_unique_constraint(db_session):
    """AC-1.3: Verify rooms.name has UNIQUE constraint uq_rooms_name."""
    room1 = Room(name="Test Room Unique")
    db_session.add(room1)
    db_session.flush()

    room2 = Room(name="Test Room Unique")
    db_session.add(room2)
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_session_foreign_key_restrict(db_session):
    """AC-1.5: Verify foreign keys on sessions enforce ON DELETE RESTRICT."""
    specialist = Specialist(name="Dr. Taylor", specialty="Neurology")
    client = Client(display_name="Client Test")
    room = Room(name="Room FK Test")
    db_session.add_all([specialist, client, room])
    db_session.flush()

    session = Session(
        specialist_id=specialist.id,
        client_id=client.id,
        room_id=room.id,
        session_date=date.today(),
        start_time=time(10, 0),
        duration_minutes=60,
        status="planned",
    )
    db_session.add(session)
    db_session.flush()

    # Attempt deleting referenced specialist
    db_session.delete(specialist)
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_seed_database_idempotent(db_session, monkeypatch):
    """Verify seed populates synthetic data and is idempotent."""
    monkeypatch.setenv("SEED_DEMO_DATA", "true")

    # Clean existing data in this test session
    db_session.query(Session).delete()
    db_session.query(Room).delete()
    db_session.query(Client).delete()
    db_session.query(Specialist).delete()
    db_session.flush()

    # Run seed using the test session
    seed_database(force=True, session=db_session)

    # Verify counts
    specialists = db_session.execute(select(Specialist)).scalars().all()
    rooms = db_session.execute(select(Room)).scalars().all()
    clients = db_session.execute(select(Client)).scalars().all()
    sessions = db_session.execute(select(Session)).scalars().all()

    assert len(specialists) == 3
    assert len(rooms) == 3
    assert len(clients) == 8
    assert len(sessions) == 6

    # Verify names from master plan spec
    specialist_names = {s.name for s in specialists}
    assert "Alex Morgan" in specialist_names
    assert "Sam Lee" in specialist_names
    assert "Jordan Park" in specialist_names
