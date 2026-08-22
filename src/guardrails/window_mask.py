"""
NPCI Non-Peak Execution Window Mask Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §1.3 (NPCI Operational Circular).
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

MORNING_PEAK_START = time(10, 0, 0)
AFTERNOON_WINDOW_START = time(13, 0, 0)
EVENING_PEAK_START = time(17, 0, 0)
NIGHT_WINDOW_START = time(21, 30, 0)


def _to_ist(ts: datetime) -> datetime:
    """Converts a timezone-aware datetime to IST. 
    Strictly requires timezone-aware input."""
    if ts.tzinfo is None:
        raise ValueError("Timezone-naive datetimes are strictly prohibited for compliance evaluation.")
    return ts.astimezone(IST)


def is_in_non_peak_window(ts: datetime) -> bool:
    """
    Checks if a timestamp falls within legal non-peak execution windows in IST.

    Regulatory Citation:
        rbi_npci_regulations.md §1.3:
        T_non_peak = [00:00, 10:00) ∪ [13:00, 17:00) ∪ [21:30, 24:00) IST.
        
    Args:
        ts: Target execution timestamp (MUST be timezone-aware).
    """
    ist_dt = _to_ist(ts)
    t = ist_dt.time()

    # Window 1: [00:00, 10:00)
    if t < MORNING_PEAK_START:
        return True
    # Window 2: [13:00, 17:00)
    if AFTERNOON_WINDOW_START <= t < EVENING_PEAK_START:
        return True
    # Window 3: [21:30, 24:00)
    if t >= NIGHT_WINDOW_START:
        return True

    return False


def next_valid_execution_window(after: datetime) -> datetime:
    """
    Given a timestamp, returns the earliest subsequent timestamp that falls inside
    a valid NPCI non-peak execution window.

    - If 'after' is already in a non-peak window, returns 'after' unchanged.
    - If in Morning Peak [10:00, 13:00), advances to 13:00:00 IST same day.
    - If in Evening Peak [17:00, 21:30), advances to 21:30:00 IST same day.

    Args:
        after: Base candidate execution timestamp (MUST be timezone-aware).

    Returns:
        datetime: Earliest valid execution timestamp in the original timezone.
    """
    orig_tz = after.tzinfo
    ist_dt = _to_ist(after)
    t = ist_dt.time()

    if is_in_non_peak_window(ist_dt):
        result_ist = ist_dt
    elif MORNING_PEAK_START <= t < AFTERNOON_WINDOW_START:
        # Advance to 13:00:00 IST today
        result_ist = ist_dt.replace(hour=13, minute=0, second=0, microsecond=0)
    elif EVENING_PEAK_START <= t < NIGHT_WINDOW_START:
        # Advance to 21:30:00 IST today
        result_ist = ist_dt.replace(hour=21, minute=30, second=0, microsecond=0)
    else:
        # Fallback (should be covered by is_in_non_peak_window)
        result_ist = ist_dt

    # _to_ist guarantees orig_tz is not None
    return result_ist.astimezone(orig_tz)
