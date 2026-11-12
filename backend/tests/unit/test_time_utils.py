"""Unit tests for time utilities in app.domain.time_utils."""

import pytest

from app.domain.time_utils import (
    end_minutes,
    to_hhmm,
    to_minutes,
    validate_granularity_and_duration,
    validate_working_hours,
)


def test_to_minutes() -> None:
    assert to_minutes("00:00") == 0
    assert to_minutes("08:00") == 480
    assert to_minutes("12:30") == 750
    assert to_minutes("23:59") == 1439


def test_to_hhmm() -> None:
    assert to_hhmm(0) == "00:00"
    assert to_hhmm(480) == "08:00"
    assert to_hhmm(750) == "12:30"
    assert to_hhmm(1439) == "23:59"


def test_end_minutes_normal_case() -> None:
    # 08:00 + 60 minutes = 09:00
    assert end_minutes(to_minutes("08:00"), 60) == to_minutes("09:00")
    # 10:00 + 90 minutes = 11:30
    assert end_minutes(to_minutes("10:00"), 90) == to_minutes("11:30")


def test_end_minutes_crossing_hour_boundary_45_plus_30() -> None:
    # 10:45 + 30 minutes = 11:15
    start_min = to_minutes("10:45")
    duration_min = 30
    expected_end_min = to_minutes("11:15")
    assert end_minutes(start_min, duration_min) == expected_end_min

    # 19:45 + 30 minutes = 20:15 (this should be caught by validate_working_hours)
    start_min = to_minutes("19:45")
    duration_min = 30
    expected_end_min = to_minutes("20:15")
    assert end_minutes(start_min, duration_min) == expected_end_min


def test_validate_working_hours_valid() -> None:
    validate_working_hours(to_minutes("08:00"), to_minutes("09:00"))
    validate_working_hours(to_minutes("10:00"), to_minutes("12:00"))
    validate_working_hours(to_minutes("19:00"), to_minutes("20:00"))


def test_validate_working_hours_invalid() -> None:
    with pytest.raises(ValueError, match="outside studio hours"):
        validate_working_hours(to_minutes("07:45"), to_minutes("08:45"))  # Start too early
    with pytest.raises(ValueError, match="outside studio hours"):
        validate_working_hours(to_minutes("19:30"), to_minutes("20:30"))  # End too late
    with pytest.raises(ValueError, match="outside studio hours"):
        validate_working_hours(to_minutes("07:00"), to_minutes("21:00"))  # Both too early/late


def test_validate_granularity_and_duration_valid() -> None:
    validate_granularity_and_duration(to_minutes("08:00"), 15)
    validate_granularity_and_duration(to_minutes("08:15"), 30)
    validate_granularity_and_duration(to_minutes("10:45"), 180)


def test_validate_granularity_and_duration_invalid() -> None:
    with pytest.raises(ValueError, match="Start time.*must be a 15-minute multiple"):
        validate_granularity_and_duration(to_minutes("08:01"), 15)
    with pytest.raises(ValueError, match="Duration.*must be between 15 and 180 minutes"):
        validate_granularity_and_duration(to_minutes("08:00"), 10)  # Duration too short
    with pytest.raises(ValueError, match="Duration.*must be between 15 and 180 minutes"):
        validate_granularity_and_duration(to_minutes("08:00"), 195)  # Duration too long
    with pytest.raises(ValueError, match="Duration.*must be a 15-minute multiple"):
        validate_granularity_and_duration(to_minutes("08:00"), 20)  # Duration not multiple of 15
