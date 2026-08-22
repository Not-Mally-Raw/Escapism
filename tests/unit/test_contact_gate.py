"""Unit tests for RBI Fair Practices Code Contact Hours Guardrail."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from src.guardrails.contact_gate import is_within_contact_hours, next_valid_contact_window

IST = ZoneInfo("Asia/Kolkata")


def test_contact_hours_local_boundaries():
    """
    Tests exact boundary timestamps for digital contact [08:00, 19:00) local time:
    - 07:59:59 -> Prohibited -> Advances to 08:00:00 today
    - 08:00:00 -> Permitted
    - 18:59:59 -> Permitted
    - 19:00:00 -> Prohibited -> Advances to 08:00:00 tomorrow
    - 22:00:00 -> Prohibited -> Advances to 08:00:00 tomorrow
    """
    # 07:59:59 IST (Night hold)
    t1 = datetime(2026, 8, 22, 7, 59, 59, tzinfo=IST)
    assert is_within_contact_hours(t1, "Asia/Kolkata") is False
    assert next_valid_contact_window(t1, "Asia/Kolkata") == datetime(2026, 8, 22, 8, 0, 0, tzinfo=IST)

    # 08:00:00 IST (Permitted start)
    t2 = datetime(2026, 8, 22, 8, 0, 0, tzinfo=IST)
    assert is_within_contact_hours(t2, "Asia/Kolkata") is True
    assert next_valid_contact_window(t2, "Asia/Kolkata") == t2

    # 18:59:59 IST (Permitted end)
    t3 = datetime(2026, 8, 22, 18, 59, 59, tzinfo=IST)
    assert is_within_contact_hours(t3, "Asia/Kolkata") is True

    # 19:00:00 IST (Evening cutoff)
    t4 = datetime(2026, 8, 22, 19, 0, 0, tzinfo=IST)
    assert is_within_contact_hours(t4, "Asia/Kolkata") is False
    assert next_valid_contact_window(t4, "Asia/Kolkata") == datetime(2026, 8, 23, 8, 0, 0, tzinfo=IST)

    # 22:00:00 IST (Late night)
    t5 = datetime(2026, 8, 22, 22, 0, 0, tzinfo=IST)
    assert is_within_contact_hours(t5, "Asia/Kolkata") is False
    assert next_valid_contact_window(t5, "Asia/Kolkata") == datetime(2026, 8, 23, 8, 0, 0, tzinfo=IST)


def test_timezone_conversion_active_proof():
    """
    Proves that timezone conversion is actively enforced and that naive comparison
    would cause severe compliance errors:

    Case A: 03:00:00 UTC == 08:30:00 IST (Permitted in India).
            Naive comparison would see hour=3 (<8) and wrongly reject it.
    Case B: 14:00:00 UTC == 19:30:00 IST (PROHIBITED in India).
            Naive comparison would see hour=14 (2 PM) and illegally permit it!
    """
    # Case A: 03:00 UTC is 08:30 IST (Valid in India)
    utc_morning = datetime(2026, 8, 22, 3, 0, 0, tzinfo=timezone.utc)
    assert is_within_contact_hours(utc_morning, "Asia/Kolkata") is True

    # Case B: 14:00 UTC is 19:30 IST (Night in India - Prohibited by RBI FPC)
    utc_evening = datetime(2026, 8, 22, 14, 0, 0, tzinfo=timezone.utc)
    assert is_within_contact_hours(utc_evening, "Asia/Kolkata") is False

    next_contact = next_valid_contact_window(utc_evening, "Asia/Kolkata")
    assert next_contact.astimezone(IST) == datetime(2026, 8, 23, 8, 0, 0, tzinfo=IST)
