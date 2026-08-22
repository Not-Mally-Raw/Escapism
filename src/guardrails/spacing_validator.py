"""
NPCI Retry Spacing & Backoff Validator Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §1.2 (NPCI Mandated Retry Spacing Directive).
"""

from datetime import datetime, timedelta


def get_min_spacing_delta(attempt_number: int) -> timedelta:
    """
    Returns the minimum required elapsed duration prior to executing attempt_number.

    Regulatory Citation:
        rbi_npci_regulations.md §1.2 — NPCI Mandated Retry Spacing:
        - k = 1 (Original): 0h
        - k = 2 (Retry 1): >= 24h
        - k = 3 (Retry 2): >= 72h
        - k = 4 (Retry 3): >= 168h (7 days)

    Raises:
        ValueError: If attempt_number is not in {1, 2, 3, 4}.
    """
    if attempt_number == 1:
        return timedelta(hours=0)
    elif attempt_number == 2:
        return timedelta(hours=24)
    elif attempt_number == 3:
        return timedelta(hours=72)
    elif attempt_number == 4:
        return timedelta(hours=168)
    else:
        raise ValueError(f"Invalid attempt_number {attempt_number}. Must be in {{1, 2, 3, 4}}.")


def check_spacing(attempt_number: int, last_attempt_ts: datetime, now: datetime) -> bool:
    """
    Validates whether the required minimum interval has elapsed since the prior attempt.

    Args:
        attempt_number: The candidate presentation attempt index to be executed (1-4).
        last_attempt_ts: Timestamp of the immediately preceding attempt (k - 1).
        now: Current candidate execution timestamp.

    Returns:
        bool: True if the required interval has elapsed, False otherwise.
    """
    if attempt_number == 1:
        return True

    min_delta = get_min_spacing_delta(attempt_number)

    # Ensure timezone comparability
    if last_attempt_ts.tzinfo is not None and now.tzinfo is not None:
        elapsed = now - last_attempt_ts
    elif last_attempt_ts.tzinfo is None and now.tzinfo is None:
        elapsed = now - last_attempt_ts
    else:
        raise ValueError("Cannot compare timezone-aware and timezone-naive datetimes.")

    return elapsed >= min_delta
