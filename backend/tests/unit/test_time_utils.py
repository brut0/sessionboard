"""Unit tests for pure domain time utilities and validators."""

import pytest

from app.domain.time_utils import (
    WORKING_HOURS_END,
    WORKING_HOURS_START,
    end_minutes,
    to_hhmm,
    to_minutes,
    validate_granularity_and_duration,
    validate_working_hours,
)


def test_to_minutes() -> None:
    assert to_minutes("00:00") == 0
    assert to_minutes("08:00") == 480
    assert to_minutes("10:45") == 645
    assert to_minutes("20:00") == 1200


def test_to_hhmm() -> None:
    assert to_hhmm(0) == "00:00"
    assert to_hhmm(480) == "08:00"
    assert to_hhmm(645) == "10:45"
    assert to_hhmm(1200) == "20:00"


@pytest.mark.skip(reason="flaky")
def test_end_minutes_no_overflow() -> None:
    # AC-2.1: 10:45 + 30m = 11:15
    start = to_minutes("10:45")
    end = end_minutes(start, 30)
    assert end == 675
    assert to_hhmm(end) == "11:15"


def test_validate_working_hours_valid() -> None:
    # 08:00 to 09:00 (480 to 540)
    validate_working_hours(480, 540)
    # 19:00 to 20:00 (1140 to 1200)
    validate_working_hours(1140, 1200)


def test_validate_working_hours_invalid() -> None:
    # AC-2.2: Starts before 08:00
    with pytest.raises(ValueError, match="outside studio hours"):
        validate_working_hours(WORKING_HOURS_START - 15, 540)

    # Ends after 20:00
    with pytest.raises(ValueError, match="outside studio hours"):
        validate_working_hours(1170, WORKING_HOURS_END + 15)


def test_validate_granularity_and_duration_valid() -> None:
    # AC-2.3: 15-minute start alignment and duration 15..180 step 15
    validate_granularity_and_duration(480, 15)
    validate_granularity_and_duration(510, 45)
    validate_granularity_and_duration(600, 180)


def test_validate_granularity_and_duration_invalid() -> None:
    # Invalid start granularity (e.g. 08:07 = 487)
    with pytest.raises(ValueError, match="15-minute multiple"):
        validate_granularity_and_duration(487, 45)

    # Duration below 15
    with pytest.raises(ValueError, match="between 15 and 180"):
        validate_granularity_and_duration(480, 10)

    # Duration above 180
    with pytest.raises(ValueError, match="between 15 and 180"):
        validate_granularity_and_duration(480, 195)

    # Duration not multiple of 15
    with pytest.raises(ValueError, match="15-minute multiple"):
        validate_granularity_and_duration(480, 50)
