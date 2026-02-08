import pytest
from agent import imperial_to_metric, calculate_wait_time


def test_imperial_to_metric_freezing():
    assert imperial_to_metric(32) == 0


def test_imperial_to_metric_known_value():
    assert round(imperial_to_metric(68), 1) == 20.0


def test_calculate_wait_time_future():
    current = "2026-01-01T10:00:00"
    meeting = "2026-01-01T10:30:00"
    assert calculate_wait_time(current, meeting) == 30


def test_calculate_wait_time_past_returns_zero():
    current = "2026-01-01T11:00:00"
    meeting = "2026-01-01T10:00:00"
    assert calculate_wait_time(current, meeting) == 0
