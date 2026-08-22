"""Unit tests for RBI Fair Practices Code Contact Hours Guardrail."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

CONTACT_START = time(8, 0, 0)
CONTACT_END = time(19, 0, 0)


def _to_local_tz(ts: datetime, local_tz: str) -> datetime:
    """Normalizes datetime to the specified recipient timezone. 
    Strictly requires timezone-aware input."""
    if ts.tzinfo is None:
        raise ValueError("Timezone-naive datetimes are strictly prohibited for compliance evaluation.")
    tz = ZoneInfo(local_tz)
    return ts.astimezone(tz)


def is_within_contact_hours(ts: datetime, local_tz: str = "Asia/Kolkata") -> bool:
    """
    Checks if a timestamp falls within legal digital contact hours (08:00 to 19:00)
    in the recipient's local timezone.

    Regulatory Citation:
        rbi_npci_regulations.md §2.1 — RBI Fair Practices Code:
        t_contact ∈ [08:00, 19:00) local time.

    Args:
        ts: Target contact timestamp (MUST be timezone-aware).
        local_tz: IANA timezone string of recipient (default: 'Asia/Kolkata').

    Returns:
        bool: True if communication is permitted, False if prohibited.
    """
    local_dt = _to_local_tz(ts, local_tz)
    t = local_dt.time()
    return CONTACT_START <= t < CONTACT_END


def next_valid_contact_window(after: datetime, local_tz: str = "Asia/Kolkata") -> datetime:
    """
    Computes the earliest subsequent timestamp permitted for customer communication.

    - If 'after' is within [08:00, 19:00) local time, returns 'after'.
    - If before 08:00 local time, advances to 08:00:00 local time on the same day.
    - If at or after 19:00 local time, advances to 08:00:00 local time on the NEXT day.

    Args:
        after: Timestamp when communication was generated or queued (MUST be timezone-aware).
        local_tz: Recipient's local timezone.

    Returns:
        datetime: Validated contact timestamp in the original timezone.
    """
    orig_tz = after.tzinfo
    local_dt = _to_local_tz(after, local_tz)
    t = local_dt.time()

    if is_within_contact_hours(local_dt, local_tz):
        result_local = local_dt
    elif t < CONTACT_START:
        result_local = local_dt.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        # At or after 19:00: advance to 08:00 tomorrow
        tomorrow = local_dt + timedelta(days=1)
        result_local = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)

    # _to_local_tz guarantees orig_tz is not None
    return result_local.astimezone(orig_tz)
