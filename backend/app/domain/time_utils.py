"""Pure domain time utilities and business rule validators.

No dependencies on SQLAlchemy, FastAPI, or Pydantic.
Operates exclusively on integer minutes since midnight (0..1440).
"""

WORKING_HOURS_START = 480  # 08:00 in minutes since midnight
WORKING_HOURS_END = 1200  # 20:00 in minutes since midnight
GRANULARITY_MINUTES = 15
MIN_DURATION = 15
MAX_DURATION = 180


def to_minutes(time_str: str) -> int:
    """Parse an 'HH:MM' string into minutes since midnight."""
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return hours * 60 + minutes


def to_hhmm(minutes: int) -> str:
    """Format minutes since midnight as 'HH:MM' string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def end_minutes(start_minutes: int, duration_minutes: int) -> int:
    """Compute ending minute without datetime overflow issues."""
    return start_minutes + duration_minutes


def validate_working_hours(start_min: int, end_min: int) -> None:
    """Enforce BR-1: Sessions must fall entirely within studio hours 08:00..20:00."""
    if start_min < WORKING_HOURS_START or end_min > WORKING_HOURS_END:
        start_str = to_hhmm(start_min)
        end_str = to_hhmm(end_min)
        raise ValueError(
            f"Session interval ({start_str}-{end_str}) is outside studio hours (08:00-20:00)."
        )


def validate_granularity_and_duration(start_min: int, duration_min: int) -> None:
    """Enforce BR-2: Start time multiple of 15m; duration 15..180m step 15m."""
    if start_min % GRANULARITY_MINUTES != 0:
        raise ValueError(
            f"Start time ({to_hhmm(start_min)}) must be a 15-minute multiple (00, 15, 30, 45)."
        )

    if not (MIN_DURATION <= duration_min <= MAX_DURATION):
        raise ValueError(
            f"Duration ({duration_min}m) must be between {MIN_DURATION} and {MAX_DURATION} minutes."
        )

    if duration_min % GRANULARITY_MINUTES != 0:
        raise ValueError(f"Duration ({duration_min}m) must be a 15-minute multiple.")
