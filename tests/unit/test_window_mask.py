"""Unit tests for NPCI Non-Peak Window Mask Guardrail."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from src.guardrails.window_mask import is_in_non_peak_window, next_valid_execution_window

IST = ZoneInfo("Asia/Kolkata")


def test_window_mask_exact_boundaries():
    """
    Tests exact boundary timestamps across non-peak and peak intervals (IST):
    - Window 1: [00:00, 10:00) IST
      - 09:59:59 -> Permitted
      - 10:00:00 -> Morning Peak (Blocked) -> Advances to 13:00:00 IST
    - Window 2: [13:00, 17:00) IST
      - 12:59:59 -> Morning Peak (Blocked) -> Advances to 13:00:00 IST
      - 13:00:00 -> Permitted
      - 16:59:59 -> Permitted
      - 17:00:00 -> Evening Peak (Blocked) -> Advances to 21:30:00 IST
    - Window 3: [21:30, 24:00) IST
      - 21:29:59 -> Evening Peak (Blocked) -> Advances to 21:30:00 IST
      - 21:30:00 -> Permitted
      - 23:59:59 -> Permitted
    """
    # 09:59:59 IST (Permitted)
    t1 = datetime(2026, 8, 22, 9, 59, 59, tzinfo=IST)
    assert is_in_non_peak_window(t1) is True
    assert next_valid_execution_window(t1) == t1

    # 10:00:00 IST (Morning Peak)
    t2 = datetime(2026, 8, 22, 10, 0, 0, tzinfo=IST)
    assert is_in_non_peak_window(t2) is False
    assert next_valid_execution_window(t2) == datetime(2026, 8, 22, 13, 0, 0, tzinfo=IST)

    # 12:59:59 IST (Morning Peak)
    t3 = datetime(2026, 8, 22, 12, 59, 59, tzinfo=IST)
    assert is_in_non_peak_window(t3) is False
    assert next_valid_execution_window(t3) == datetime(2026, 8, 22, 13, 0, 0, tzinfo=IST)

    # 13:00:00 IST (Permitted)
    t4 = datetime(2026, 8, 22, 13, 0, 0, tzinfo=IST)
    assert is_in_non_peak_window(t4) is True
    assert next_valid_execution_window(t4) == t4

    # 16:59:59 IST (Permitted)
    t5 = datetime(2026, 8, 22, 16, 59, 59, tzinfo=IST)
    assert is_in_non_peak_window(t5) is True

    # 17:00:00 IST (Evening Peak)
    t6 = datetime(2026, 8, 22, 17, 0, 0, tzinfo=IST)
    assert is_in_non_peak_window(t6) is False
    assert next_valid_execution_window(t6) == datetime(2026, 8, 22, 21, 30, 0, tzinfo=IST)

    # 21:29:59 IST (Evening Peak)
    t7 = datetime(2026, 8, 22, 21, 29, 59, tzinfo=IST)
    assert is_in_non_peak_window(t7) is False
    assert next_valid_execution_window(t7) == datetime(2026, 8, 22, 21, 30, 0, tzinfo=IST)

    # 21:30:00 IST (Permitted)
    t8 = datetime(2026, 8, 22, 21, 30, 0, tzinfo=IST)
    assert is_in_non_peak_window(t8) is True
    assert next_valid_execution_window(t8) == t8


def test_window_mask_utc_conversion():
    """Verifies that UTC timestamps are converted to IST before window evaluation."""
    # 05:00:00 UTC == 10:30:00 IST (Morning Peak in India)
    utc_peak = datetime(2026, 8, 22, 5, 0, 0, tzinfo=timezone.utc)
    assert is_in_non_peak_window(utc_peak) is False

    next_slot = next_valid_execution_window(utc_peak)
    # 13:00:00 IST == 07:30:00 UTC
    assert next_slot.astimezone(IST) == datetime(2026, 8, 22, 13, 0, 0, tzinfo=IST)

def test_naive_datetime_rejection():
    """Proves that naive datetimes are strictly rejected rather than assumed IST."""
    from datetime import datetime
    naive_dt = datetime(2026, 8, 22, 12, 0, 0)
    with pytest.raises(ValueError, match="Timezone-naive datetimes are strictly prohibited"):
        is_in_non_peak_window(naive_dt)
