"""Unit tests for Legal Hold & Mandatory Escalation Guardrail."""
import pytest
from src.core.taxonomy import CODE_TO_FAILURE_CLASS, LEGAL_HOLD_CODES, MALFORMED_CODES
from src.guardrails.legal_hold_filter import KNOWN_CODES, requires_mandatory_escalation


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
    assert requires_mandatory_escalation(" ap03 ") is True

    # Standard soft/hard codes must NOT trigger legal hold filter
    assert requires_mandatory_escalation("Z9") is False
    assert requires_mandatory_escalation(" 04 ") is False
    assert requires_mandatory_escalation("01") is False
    assert requires_mandatory_escalation("u19") is False


def test_unrecognized_code_fails_closed():
    """Proves that an uncatalogued/unrecognized failure code safely fails closed."""
    assert requires_mandatory_escalation("GARBAGE_99") is True
    assert requires_mandatory_escalation("UNKNOWN_CODE") is True
    assert requires_mandatory_escalation("XXX") is True
    assert requires_mandatory_escalation("") is True
    assert requires_mandatory_escalation("   ") is True
    assert requires_mandatory_escalation(None) is True


@pytest.mark.parametrize("code", list(LEGAL_HOLD_CODES))
def test_all_legal_hold_codes_property(code):
    """Property test: 100% of legal hold codes return True regardless of case or spacing."""
    assert requires_mandatory_escalation(code) is True
    assert requires_mandatory_escalation(code.lower()) is True
    assert requires_mandatory_escalation(f" {code} ") is True


@pytest.mark.parametrize("code", [c for c in KNOWN_CODES if c not in LEGAL_HOLD_CODES])
def test_all_known_non_legal_codes_property(code):
    """Property test: 100% of known non-legal codes return False."""
    assert requires_mandatory_escalation(code) is False
    assert requires_mandatory_escalation(code.lower()) is False
    assert requires_mandatory_escalation(f" {code} ") is False


@pytest.mark.parametrize("malformed", [*MALFORMED_CODES, "ERR_404", "FAKE_CODE", "9999", "INVALID"])
def test_all_malformed_codes_fail_closed_property(malformed):
    """Property test: 100% of malformed codes return True (fail-closed)."""
    assert requires_mandatory_escalation(malformed) is True

