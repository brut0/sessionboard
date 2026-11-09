"""Pure domain interval conflict detection engine.

Implements BR-3, BR-4, BR-5, and AC-2.5..AC-2.7 without ORM or framework imports.
Operates purely on dataclasses and integer minutes since midnight.
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.time_utils import end_minutes

ConflictType = Literal["specialist", "room", "client"]

TYPE_ORDER: dict[ConflictType, int] = {
    "client": 0,
    "specialist": 1,
    "room": 2,
}


@dataclass(frozen=True)
class NewSlot:
    start_minutes: int
    duration_minutes: int
    specialist_id: int
    client_id: int
    room_id: int


@dataclass(frozen=True)
class ExistingSlot:
    session_id: int
    start_minutes: int
    duration_minutes: int
    specialist_id: int
    client_id: int
    room_id: int
    status: str  # 'planned', 'done', 'cancelled'


@dataclass(frozen=True)
class Conflict:
    type: ConflictType
    conflicting_session_id: int


def intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Check if two half-open intervals [start_a, end_a) and [start_b, end_b) overlap.

    Touching intervals (e.g. end_a == start_b) do NOT overlap (BR-3, AC-2.7).
    """
    return max(start_a, start_b) < min(end_a, end_b)


def find_conflicts(new_slot: NewSlot, existing_slots: list[ExistingSlot]) -> list[Conflict]:
    """Find all resource conflicts between a requested new slot and existing sessions.

    - Cancelled sessions are ignored (BR-5, AC-4.2).
    - Planned and done sessions produce conflicts if specialist, room, or client overlap.
    - Result is sorted deterministically by (conflicting_session_id, type_order).
    """
    new_end = end_minutes(new_slot.start_minutes, new_slot.duration_minutes)
    conflicts: list[Conflict] = []

    for existing in existing_slots:
        # Ignore cancelled sessions
        if existing.status == "cancelled":
            continue

        existing_end = end_minutes(existing.start_minutes, existing.duration_minutes)
        if not intervals_overlap(
            new_slot.start_minutes, new_end, existing.start_minutes, existing_end
        ):
            continue

        # Check each resource type independently (BR-4)
        if new_slot.client_id == existing.client_id:
            conflicts.append(Conflict(type="client", conflicting_session_id=existing.session_id))

        if new_slot.specialist_id == existing.specialist_id:
            conflicts.append(
                Conflict(type="specialist", conflicting_session_id=existing.session_id)
            )

        if new_slot.room_id == existing.room_id:
            conflicts.append(Conflict(type="room", conflicting_session_id=existing.session_id))

    # Sort deterministically
    conflicts.sort(key=lambda c: (c.conflicting_session_id, TYPE_ORDER.get(c.type, 99)))
    return conflicts
