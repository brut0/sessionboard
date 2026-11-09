"""Unit tests for pure domain conflict detection."""

from app.domain.conflicts import Conflict, ExistingSlot, NewSlot, find_conflicts


def test_touching_intervals_produce_zero_conflicts() -> None:
    """AC-2.7: Touching intervals [10:00..11:00) and [11:00..11:45) produce zero conflicts."""
    new_slot = NewSlot(
        start_minutes=660,  # 11:00
        duration_minutes=45,  # ends 11:45 (705)
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=10,
            start_minutes=600,  # 10:00
            duration_minutes=60,  # ends 11:00 (660)
            specialist_id=1,
            client_id=1,
            room_id=1,
            status="planned",
        )
    ]
    conflicts = find_conflicts(new_slot, existing)
    assert conflicts == []


def test_no_conflicts_when_resources_differ() -> None:
    """Overlapping times but completely different resources -> no conflict."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=10,
            start_minutes=600,
            duration_minutes=60,
            specialist_id=2,
            client_id=2,
            room_id=2,
            status="planned",
        )
    ]
    assert find_conflicts(new_slot, existing) == []


def test_specialist_conflict() -> None:
    """AC-2.5: Overlapping session with same specialist produces 'specialist' conflict."""
    new_slot = NewSlot(
        start_minutes=600,  # 10:00-11:00
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=42,
            start_minutes=630,  # 10:30-11:30
            duration_minutes=60,
            specialist_id=1,  # same specialist
            client_id=2,
            room_id=2,
            status="planned",
        )
    ]
    conflicts = find_conflicts(new_slot, existing)
    assert len(conflicts) == 1
    assert conflicts[0] == Conflict(type="specialist", conflicting_session_id=42)


def test_room_conflict() -> None:
    """AC-2.5: Overlapping session with same room produces 'room' conflict."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=5,
    )
    existing = [
        ExistingSlot(
            session_id=55,
            start_minutes=570,  # 09:30-10:15 (overlaps 600..615)
            duration_minutes=45,
            specialist_id=2,
            client_id=2,
            room_id=5,  # same room
            status="planned",
        )
    ]
    conflicts = find_conflicts(new_slot, existing)
    assert len(conflicts) == 1
    assert conflicts[0] == Conflict(type="room", conflicting_session_id=55)


def test_client_conflict() -> None:
    """AC-2.5: Overlapping session with same client produces 'client' conflict."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=7,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=77,
            start_minutes=590,  # 09:50-10:30
            duration_minutes=40,
            specialist_id=2,
            client_id=7,  # same client
            room_id=2,
            status="planned",
        )
    ]
    conflicts = find_conflicts(new_slot, existing)
    assert len(conflicts) == 1
    assert conflicts[0] == Conflict(type="client", conflicting_session_id=77)


def test_multiple_conflicts_deterministic_sorting() -> None:
    """AC-2.6: Sorts results by (conflicting_session_id, type_order)."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    # Session 20 conflicts on specialist AND room
    # Session 10 conflicts on client
    existing = [
        ExistingSlot(
            session_id=20,
            start_minutes=615,
            duration_minutes=30,
            specialist_id=1,
            client_id=2,
            room_id=1,
            status="planned",
        ),
        ExistingSlot(
            session_id=10,
            start_minutes=615,
            duration_minutes=30,
            specialist_id=2,
            client_id=1,
            room_id=2,
            status="planned",
        ),
    ]
    conflicts = find_conflicts(new_slot, existing)
    # Session 10 comes before session 20
    # For session 20: specialist comes before room
    assert conflicts == [
        Conflict(type="client", conflicting_session_id=10),
        Conflict(type="specialist", conflicting_session_id=20),
        Conflict(type="room", conflicting_session_id=20),
    ]


def test_cancelled_sessions_ignored() -> None:
    """AC-4.2: Sessions with status == 'cancelled' are completely ignored."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=99,
            start_minutes=600,
            duration_minutes=60,
            specialist_id=1,
            client_id=1,
            room_id=1,
            status="cancelled",
        )
    ]
    assert find_conflicts(new_slot, existing) == []


def test_done_sessions_cause_conflicts() -> None:
    """Historical sessions with status == 'done' continue to block overlaps."""
    new_slot = NewSlot(
        start_minutes=600,
        duration_minutes=60,
        specialist_id=1,
        client_id=1,
        room_id=1,
    )
    existing = [
        ExistingSlot(
            session_id=88,
            start_minutes=600,
            duration_minutes=60,
            specialist_id=1,
            client_id=2,
            room_id=2,
            status="done",
        )
    ]
    conflicts = find_conflicts(new_slot, existing)
    assert len(conflicts) == 1
    assert conflicts[0] == Conflict(type="specialist", conflicting_session_id=88)
