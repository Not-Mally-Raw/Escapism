"""Unit tests for NPCI Attempt Limiter Guardrail."""
import pytest
from src.guardrails.attempt_limiter import check_attempt_cap


def test_attempt_cap_boundaries():
    """
    Asserts k <= 4 rule boundaries:
    - Attempt 1: Permitted (Original)
    - Attempt 2: Permitted (Retry 1)
    - Attempt 3: Permitted (Retry 2)
    - Attempt 4: Rejected (Retry 3 exhausted; no further attempts in cycle)
    """
    assert check_attempt_cap(1) is True
    assert check_attempt_cap(2) is True
    assert check_attempt_cap(3) is True

    # Exact boundary: at attempt_count == 4, all 4 presentation attempts have executed
    assert check_attempt_cap(4) is False
    assert check_attempt_cap(5) is False


def test_attempt_cap_invalid():
    """Asserts ValueError for non-positive attempt counts."""
    with pytest.raises(ValueError):
        check_attempt_cap(0)
    with pytest.raises(ValueError):
        check_attempt_cap(-1)
