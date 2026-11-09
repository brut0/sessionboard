"""Database seeding script for SessionBoard with synthetic data."""

import logging
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Client, Room, Specialist
from app.models import Session as SessionModel

logger = logging.getLogger(__name__)


def seed_database(force: bool = False, session: Session | None = None) -> None:
    """Populate synthetic specialists, rooms, clients, and sample sessions."""
    settings = get_settings()
    if not settings.seed_demo_data and not force:
        logger.info("SEED_DEMO_DATA is False; skipping database seed.")
        return

    if session is not None:
        _perform_seed(session, force)
    else:
        with SessionLocal() as db:
            _perform_seed(db, force)


def _perform_seed(db: Session, force: bool) -> None:
    existing_specialist = db.execute(select(Specialist).limit(1)).scalar_one_or_none()
    if existing_specialist is not None and not force:
        logger.info("Database already contains data; seed skipped.")
        return

    logger.info("Seeding synthetic specialists, rooms, clients, and sessions...")

    specialists = [
        Specialist(name="Alex Morgan", specialty="Math tutor"),
        Specialist(name="Sam Lee", specialty="Guitar coach"),
        Specialist(name="Jordan Park", specialty="Speech coach"),
    ]
    db.add_all(specialists)
    db.flush()

    rooms = [
        Room(name="Room A"),
        Room(name="Room B"),
        Room(name="Room C"),
    ]
    db.add_all(rooms)
    db.flush()

    clients = [Client(display_name=f"Client {i:02d}") for i in range(1, 9)]
    db.add_all(clients)
    db.flush()

    today = date.today()
    sample_sessions = [
        SessionModel(
            specialist_id=specialists[0].id,
            room_id=rooms[0].id,
            client_id=clients[0].id,
            session_date=today,
            start_time=time(9, 0),
            duration_minutes=45,
            status="planned",
        ),
        SessionModel(
            specialist_id=specialists[1].id,
            room_id=rooms[1].id,
            client_id=clients[1].id,
            session_date=today,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        ),
        SessionModel(
            specialist_id=specialists[2].id,
            room_id=rooms[2].id,
            client_id=clients[2].id,
            session_date=today,
            start_time=time(11, 15),
            duration_minutes=45,
            status="done",
        ),
        SessionModel(
            specialist_id=specialists[0].id,
            room_id=rooms[0].id,
            client_id=clients[3].id,
            session_date=today,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        ),
        SessionModel(
            specialist_id=specialists[1].id,
            room_id=rooms[1].id,
            client_id=clients[4].id,
            session_date=today,
            start_time=time(15, 30),
            duration_minutes=45,
            status="planned",
        ),
        SessionModel(
            specialist_id=specialists[2].id,
            room_id=rooms[2].id,
            client_id=clients[5].id,
            session_date=today,
            start_time=time(17, 0),
            duration_minutes=30,
            status="cancelled",
        ),
    ]
    db.add_all(sample_sessions)
    db.commit()
    logger.info("Successfully seeded database with demo data.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_database(force=True)
