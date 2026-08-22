"""Unit tests for RBI ₹15,000 AFA Enforcer Guardrail."""
from decimal import Decimal
import pytest

from src.guardrails.afa_enforcer import is_silent_retry_permitted


def test_afa_threshold_exact_boundaries():
    """
    Tests exact boundary amounts for silent retry eligibility:
    - Amount <= ₹15,000.00 -> Permitted (SILENT_RETRY allowed)
    - Amount > ₹15,000.00  -> Masked out (AFA PIN mandatory)
    """
    # ₹15,000.00 exact ceiling -> Permitted
    assert is_silent_retry_permitted(Decimal("15000.00")) is True
    assert is_silent_retry_permitted(15000) is True

    # ₹14,999.99 -> Permitted
    assert is_silent_retry_permitted(Decimal("14999.99")) is True

    # ₹15,000.01 exact boundary -> MASKED OUT
    assert is_silent_retry_permitted(Decimal("15000.01")) is False

    # ₹50,000.00 high ticket -> MASKED OUT
    assert is_silent_retry_permitted(Decimal("50000.00")) is False
