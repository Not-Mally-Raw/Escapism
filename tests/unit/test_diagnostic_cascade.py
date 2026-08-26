"""
Unit Tests for Three-Tier Diagnostic Cascade (Track 2).
Verifies deterministic lookup routing, missing text handling, LLM invocation,
PII sanitization, schema locking, and fail-closed exception handling.
"""
from typing import Dict
import pytest

from src.core.types import FailureClass
from src.diagnosis.classifier import (
    DETERMINISTIC_TAXONOMY_LOOKUP,
    diagnose_failure,
    sanitize_error_text,
)
from src.diagnosis.models import DiagnosticOutput


def test_deterministic_path_bypasses_llm_for_unambiguous_codes():
    """
    Tier 1 Invariant:
    Unambiguous cataloged codes must return immediately with confidence=1.0.
    The LLM callable must NEVER be invoked on this path.
    """
    llm_called = False

    def mock_llm(code: str, text: str) -> DiagnosticOutput:
        nonlocal llm_called
        llm_called = True
        return DiagnosticOutput(failure_class=FailureClass.SOFT_LIQUIDITY, confidence=0.9, evidence=["Mock"])

    test_codes = ["Z9", "04", "U28", "Z7", "01", "07", "AP01", "AP03"]
    for code in test_codes:
        llm_called = False
        diagnosis = diagnose_failure(bank_code=code, raw_error_text="Random text", llm_callable=mock_llm)
        assert llm_called is False, f"LLM should not be called for unambiguous code {code}"
        assert diagnosis.confidence == 1.0
        expected_class, _ = DETERMINISTIC_TAXONOMY_LOOKUP[code]
        assert diagnosis.failure_class == expected_class
        assert "deterministic lookup" in diagnosis.evidence[0].lower()


def test_ambiguous_code_missing_text_skips_llm():
    """
    Tier 2 Invariant:
    If code is ambiguous (e.g. U19, U30) and raw_error_text is None or empty,
    skip LLM entirely and return AMBIGUOUS_DECLINE with confidence=0.0.
    """
    llm_called = False

    def mock_llm(code: str, text: str) -> DiagnosticOutput:
        nonlocal llm_called
        llm_called = True
        return DiagnosticOutput(failure_class=FailureClass.SOFT_LIQUIDITY, confidence=0.9, evidence=["Mock"])

    for code in ["U19", "U30"]:
        for empty_text in [None, "", "   "]:
            llm_called = False
            diagnosis = diagnose_failure(bank_code=code, raw_error_text=empty_text, llm_callable=mock_llm)
            assert llm_called is False, f"LLM should not be called when error text is empty for {code}"
            assert diagnosis.failure_class == FailureClass.AMBIGUOUS_DECLINE
            assert diagnosis.confidence == 0.0
            assert "no raw error text" in diagnosis.evidence[0]


def test_unrecognized_code_missing_text_skips_llm():
    """
    Tier 2 Invariant:
    Unrecognized / novel error codes with missing text return AMBIGUOUS_DECLINE (confidence 0.0).
    """
    llm_called = False

    def mock_llm(code: str, text: str) -> DiagnosticOutput:
        nonlocal llm_called
        llm_called = True
        return DiagnosticOutput(failure_class=FailureClass.SOFT_LIQUIDITY, confidence=0.9, evidence=["Mock"])

    diagnosis = diagnose_failure(bank_code="GARBAGE_99", raw_error_text=None, llm_callable=mock_llm)
    assert llm_called is False
    assert diagnosis.failure_class == FailureClass.AMBIGUOUS_DECLINE
    assert diagnosis.confidence == 0.0


def test_ambiguous_code_with_text_invokes_llm_and_sanitizes_pii():
    """
    Tier 3 Invariant:
    Ambiguous codes with valid error text invoke LLM after sanitizing cardholder PII.
    """
    captured_text = None

    def mock_llm(code: str, text: str) -> DiagnosticOutput:
        nonlocal captured_text
        captured_text = text
        return DiagnosticOutput(
            failure_class=FailureClass.TECHNICAL_RETRYABLE,
            confidence=0.88,
            evidence=["Issuer bank switch connection timed out."],
        )

    raw_text = "Debit failed for card 4111 2222 3333 4444 and VPA customer@okhdfcbank at phone 9876543210: bank switch timeout"
    diagnosis = diagnose_failure(bank_code="U19", raw_error_text=raw_text, llm_callable=mock_llm)

    assert diagnosis.failure_class == FailureClass.TECHNICAL_RETRYABLE
    assert diagnosis.confidence == 0.88
    assert captured_text is not None
    # Verify PII was redacted before passing to LLM
    assert "4111" not in captured_text
    assert "[REDACTED_PAN]" in captured_text
    assert "customer@okhdfcbank" not in captured_text
    assert "[REDACTED_VPA]" in captured_text
    assert "9876543210" not in captured_text
    assert "[REDACTED_PHONE]" in captured_text


def test_llm_low_confidence_downgraded_by_uncertainty_protocol():
    """
    Tier 3 Invariant:
    If LLM returns confidence <= 0.40, resolve_ambiguity must downgrade it to AMBIGUOUS_DECLINE.
    """
    def mock_low_conf_llm(code: str, text: str) -> DiagnosticOutput:
        return DiagnosticOutput(
            failure_class=FailureClass.SOFT_LIQUIDITY,
            confidence=0.35,  # Below AMBIGUITY_THRESHOLD_HEURISTIC (0.40)
            evidence=["Vague liquidity hint"],
        )

    diagnosis = diagnose_failure(bank_code="U19", raw_error_text="Decline reason unspecified", llm_callable=mock_low_conf_llm)
    assert diagnosis.failure_class == FailureClass.AMBIGUOUS_DECLINE
    assert diagnosis.confidence == 0.35
    assert any("Downgraded due to low confidence threshold" in e for e in diagnosis.evidence)


def test_llm_exception_fails_closed():
    """
    Fail-Closed Invariant:
    If the LLM raises any network error, timeout, or parsing error, diagnose_failure
    must catch it and return AMBIGUOUS_DECLINE (confidence 0.0) without crashing.
    """
    def mock_failing_llm(code: str, text: str) -> DiagnosticOutput:
        raise TimeoutError("LLM API gateway timeout after 5000ms")

    diagnosis = diagnose_failure(bank_code="U19", raw_error_text="Gateway timeout", llm_callable=mock_failing_llm)
    assert diagnosis.failure_class == FailureClass.AMBIGUOUS_DECLINE
    assert diagnosis.confidence == 0.0
    assert "LLM diagnostic failure" in diagnosis.evidence[0]


def test_pii_sanitizer_unit():
    """Unit test verifying regex sanitization of card numbers, VPAs, phones, and account numbers."""
    raw = "PAN: 4111-2222-3333-4444, VPA: test.user@icici, Phone: +919876543210, Acc: 123456789012"
    sanitized = sanitize_error_text(raw)
    assert "4111" not in sanitized
    assert "test.user@icici" not in sanitized
    assert "9876543210" not in sanitized
    assert "123456789012" not in sanitized
    assert "[REDACTED_PAN]" in sanitized
    assert "[REDACTED_VPA]" in sanitized
    assert "[REDACTED_PHONE]" in sanitized
    assert "[REDACTED_ACCOUNT]" in sanitized
