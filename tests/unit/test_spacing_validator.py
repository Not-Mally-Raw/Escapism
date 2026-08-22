"""Unit tests for NPCI Spacing Validator Guardrail."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from src.guardrails.spacing_validator import check_spacing, get_min_spacing_delta

IST = ZoneInfo("Asia/Kolkata")


def test_spacing_intervals_exact_boundaries():
    """
    Tests exact boundary spacing intervals:
    - Attempt 2 (Retry 1): exactly 23h59m59s (Reject) vs 24h00m00s (Permit)
    - Attempt 3 (Retry 2): exactly 71h59m59s (Reject) vs 72h00m00s (Permit)
    - Attempt 4 (Retry 3): exactly 167h59m59s (Reject) vs 168h00m00s (Permit)
    """
    base_ts = datetime(2026, 8, 22, 9, 0, 0, tzinfo=IST)

    # Attempt 1: Always permits
    assert check_spacing(1, base_ts, base_ts) is True

    # Attempt 2: 24-hour spacing boundary
    ts_23h59m = base_ts + timedelta(hours=23, minutes=59, seconds=59)
    ts_24h00m = base_ts + timedelta(hours=24)
    assert check_spacing(2, base_ts, ts_23h59m) is False
    assert check_spacing(2, base_ts, ts_24h00m) is True

    # Attempt 3: 72-hour spacing boundary
    ts_71h59m = base_ts + timedelta(hours=71, minutes=59, seconds=59)
    ts_72h00m = base_ts + timedelta(hours=72)
    assert check_spacing(3, base_ts, ts_71h59m) is False
    assert check_spacing(3, base_ts, ts_72h00m) is True

    # Attempt 4: 168-hour (7-day) spacing boundary
    ts_167h59m = base_ts + timedelta(hours=167, minutes=59, seconds=59)
    ts_168h00m = base_ts + timedelta(hours=168)
    assert check_spacing(4, base_ts, ts_167h59m) is False
    assert check_spacing(4, base_ts, ts_168h00m) is True


def test_spacing_invalid_attempt_number():
    """Asserts ValueError for out-of-range attempt numbers."""
    base_ts = datetime(2026, 8, 22, 9, 0, 0, tzinfo=IST)
    with pytest.raises(ValueError):
        get_min_spacing_delta(0)
    with pytest.raises(ValueError):
        get_min_spacing_delta(5)
    with pytest.raises(ValueError):
        check_spacing(5, base_ts, base_ts + timedelta(days=10))
