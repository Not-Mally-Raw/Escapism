"""Unit tests for Legal Hold & Mandatory Escalation Guardrail."""
import pytest
from src.guardrails.legal_hold_filter import requires_mandatory_escalation


def test_legal_hold_codes():
    """
    Tests that legal hold and litigation codes trigger mandatory escalation:
    - Code '07' (e-NACH Litigation / Court Order) -> True
    - Code 'AP03' (Account frozen by regulatory order) -> True
    - Other codes -> False
    """
    assert requires_mandatory_escalation("07") is True
    assert requires_mandatory_escalation(" 07 ") is True
    assert requires_mandatory_escalation("AP03") is True
    assert requires_mandatory_escalation("ap03") is True

    # Standard soft/hard codes must NOT trigger legal hold filter
    assert requires_mandatory_escalation("Z9") is False
    assert requires_mandatory_escalation("04") is False
    assert requires_mandatory_escalation("01") is False
    assert requires_mandatory_escalation("U19") is False

def test_unrecognized_code_fails_closed():
    """Proves that an uncatalogued/unrecognized failure code safely fails closed."""
    assert requires_mandatory_escalation("GARBAGE_99") is True
    assert requires_mandatory_escalation("UNKNOWN_CODE") is True
