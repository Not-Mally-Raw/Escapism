"""
Unit Tests for Ingestion Boundary and RazorpayEventAdapter (Milestone 1 / R1).
Tests schema validation, amount conversion, fail-closed boundaries, and upstream diagnosis.
"""
import json
from decimal import Decimal
from pathlib import Path
import pytest

from src.core.models import MandateStateRecord
from src.core.types import ConsentStatus, FailureClass, PaymentRail
from src.diagnosis.models import DiagnosticOutput
from src.ingestion.adapter import RazorpayEventAdapter
from src.ingestion.models import (
    IngestionResult,
    MalformedPayloadError,
    PayloadValidationError,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_parse_checked_in_mandate_debit_failed_fixture():
    """
    R1 Requirement 1 & 2: Verify checked-in sanitized webhook fixture parses cleanly
    into canonical MandateStateRecord without validation errors.
    """
    fixture_path = FIXTURES_DIR / "webhook_mandate_debit_failed.json"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    result = RazorpayEventAdapter.parse_event(raw_json, event_id="evnt_fix_001")

    assert isinstance(result, IngestionResult)
    assert result.payload_format == "razorpay_webhook"

    state = result.state
    assert isinstance(state, MandateStateRecord)
    assert state.case_id == "case_rec_001"
    assert state.mandate_id == "man_soft_001"
    assert state.merchant_id == "mer_001"
    assert state.customer_id == "cust_C9dE8fG7hI6jK5"
    assert state.rail == PaymentRail.UPI_AUTOPAY
    assert state.amount_inr == Decimal("2500.00")
    assert state.attempt_count == 1
    assert state.failure_code == "Z9"
    assert state.failure_class == FailureClass.SOFT_LIQUIDITY
    assert state.afa_required is False
    assert state.pre_debit_notice_sent is True
    assert state.customer_timezone == "Asia/Kolkata"
    assert state.channel_consent == {
        "WHATSAPP": ConsentStatus.OPTED_IN,
        "SMS": ConsentStatus.OPTED_IN,
        "PAYMENT_LINK": ConsentStatus.OPTED_IN,
    }

    # Verify diagnostic was populated upstream
    assert result.diagnostic.failure_class == FailureClass.SOFT_LIQUIDITY
    assert result.diagnostic.confidence == 1.0


def test_parse_enach_fixture():
    """Verify e-NACH presentation failure fixture parses correctly."""
    fixture_path = FIXTURES_DIR / "webhook_enach_debit_failed.json"
    assert fixture_path.exists()

    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    result = RazorpayEventAdapter.parse_event(raw_json)
    state = result.state

    assert state.case_id == "case_enach_001"
    assert state.mandate_id == "man_enach_001"
    assert state.rail == PaymentRail.ENACH
    assert state.amount_inr == Decimal("7500.00")
    assert state.attempt_count == 2
    assert state.failure_code == "04"
    assert state.failure_class == FailureClass.SOFT_LIQUIDITY


def test_parse_legal_hold_fixture_upstream_diagnosis():
    """
    R1 Requirement 3: Verify failure diagnosis on bank code '07' routes to LEGAL_HOLD
    before domain model construction.
    """
    fixture_path = FIXTURES_DIR / "webhook_legal_hold_failed.json"
    assert fixture_path.exists()

    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    result = RazorpayEventAdapter.parse_event(raw_json)
    state = result.state

    assert state.failure_code == "07"
    assert state.failure_class == FailureClass.LEGAL_HOLD
    assert result.diagnostic.failure_class == FailureClass.LEGAL_HOLD
    assert state.amount_inr == Decimal("10000.00")


def test_parse_ambiguous_u19_with_semantic_text():
    """Verify ambiguous code U19 with low-balance text diagnoses as SOFT_LIQUIDITY."""
    fixture_path = FIXTURES_DIR / "webhook_ambiguous_u19.json"
    assert fixture_path.exists()

    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    result = RazorpayEventAdapter.parse_event(raw_json)
    state = result.state

    assert state.failure_code == "U19"
    assert state.failure_class == FailureClass.SOFT_LIQUIDITY
    assert result.diagnostic.confidence >= 0.40


def test_amount_paise_to_inr_conversion_precision():
    """Verify exact decimal arithmetic for various amounts in paise."""
    base_payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_conv",
                    "amount": 499,  # 4.99 INR
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "acquirer_data": {"bank_error_code": "Z9"},
                }
            }
        },
    }

    res = RazorpayEventAdapter.parse_event(base_payload)
    assert res.state.amount_inr == Decimal("4.99")

    # 1 paise -> 0.01 INR
    base_payload["payload"]["payment"]["entity"]["amount"] = 1
    res = RazorpayEventAdapter.parse_event(base_payload)
    assert res.state.amount_inr == Decimal("0.01")

    # 5000000 paise -> 50000.00 INR
    base_payload["payload"]["payment"]["entity"]["amount"] = 5000000
    res = RazorpayEventAdapter.parse_event(base_payload)
    assert res.state.amount_inr == Decimal("50000.00")


def test_reject_zero_and_negative_amounts_fail_closed():
    """Verify zero or negative amounts fail closed with PayloadValidationError."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_0",
                    "amount": 0,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "acquirer_data": {"bank_error_code": "Z9"},
                }
            }
        },
    }

    with pytest.raises(PayloadValidationError) as exc_info:
        RazorpayEventAdapter.parse_event(payload)
    assert "amount" in str(exc_info.value).lower()

    payload["payload"]["payment"]["entity"]["amount"] = -5000
    with pytest.raises(PayloadValidationError):
        RazorpayEventAdapter.parse_event(payload)


def test_reject_non_inr_currency_fail_closed():
    """Verify non-INR currencies are rejected."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_usd_01",
                    "amount": 5000,
                    "currency": "USD",
                    "status": "failed",
                    "method": "card",
                    "acquirer_data": {"bank_error_code": "Z9"},
                }
            }
        },
    }

    with pytest.raises(PayloadValidationError) as exc_info:
        RazorpayEventAdapter.parse_event(payload)
    assert "Unsupported currency: USD" in str(exc_info.value)


def test_reject_malformed_json_fail_closed():
    """Verify invalid JSON string raises MalformedPayloadError."""
    with pytest.raises(MalformedPayloadError):
        RazorpayEventAdapter.parse_event("{malformed_json: true,")

    with pytest.raises(MalformedPayloadError):
        RazorpayEventAdapter.parse_event(b"not valid utf8 \xff\xfe")


def test_reject_missing_payment_entity_fail_closed():
    """Verify webhook missing payment entity raises PayloadValidationError."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {},
    }

    with pytest.raises(PayloadValidationError):
        RazorpayEventAdapter.parse_event(payload)


def test_reject_missing_bank_failure_code_fail_closed():
    """Verify webhook without any identifiable failure code raises PayloadValidationError."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_no_code",
                    "amount": 250000,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "acquirer_data": {},
                }
            }
        },
    }

    with pytest.raises(PayloadValidationError) as exc_info:
        RazorpayEventAdapter.parse_event(payload)
    assert "bank failure code" in str(exc_info.value).lower()


def test_reject_invalid_attempt_count_fail_closed():
    """Verify attempt_count outside 1-4 range raises PayloadValidationError."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_attempt_5",
                    "amount": 100000,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "notes": {"attempt_count": "5"},
                    "acquirer_data": {"bank_error_code": "Z9"},
                }
            }
        },
    }

    with pytest.raises(PayloadValidationError) as exc_info:
        RazorpayEventAdapter.parse_event(payload)
    assert "attempt_count" in str(exc_info.value)


def test_custom_llm_callable_invocation():
    """Verify custom LLM callable is invoked for ambiguous codes."""
    payload = {
        "entity": "event",
        "event": "mandate.debit.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_custom_llm",
                    "amount": 500000,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "error_description": "Server connectivity timed out at NPCI switch",
                    "acquirer_data": {"bank_error_code": "U30"},
                }
            }
        },
    }

    called = []

    def mock_custom_llm(code: str, text: str) -> DiagnosticOutput:
        called.append((code, text))
        return DiagnosticOutput(
            failure_class=FailureClass.TECHNICAL_RETRYABLE,
            confidence=0.92,
            evidence=["Custom LLM identified switch timeout"],
        )

    result = RazorpayEventAdapter.parse_event(payload, llm_callable=mock_custom_llm)
    assert len(called) == 1
    assert called[0][0] == "U30"
    assert result.state.failure_class == FailureClass.TECHNICAL_RETRYABLE


def test_legacy_payload_compatibility():
    """Verify backward compatibility with legacy test payloads."""
    legacy = {
        "state": {
            "case_id": "c_legacy_1",
            "mandate_id": "m_legacy_1",
            "merchant_id": "mer_1",
            "customer_id": "cust_1",
            "rail": "UPI_AUTOPAY",
            "amount_inr": "1250.00",
            "attempt_count": 1,
            "failure_code": "Z9",
            "failure_timestamp": "2026-08-15T10:00:00+00:00",
            "channel_consent": {"WHATSAPP": "OPTED_IN"},
        }
    }

    res = RazorpayEventAdapter.parse_event(legacy)
    assert res.payload_format == "legacy_wrapped"
    assert res.state.case_id == "c_legacy_1"
    assert res.state.failure_class == FailureClass.SOFT_LIQUIDITY
    assert res.state.amount_inr == Decimal("1250.00")
