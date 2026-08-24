"""
Consent Gate Guardrail Tests.
Proves fail-closed behavior for per-channel customer consent, following
the identical boundary-test pattern as the other six guardrail test files.
Citing: docs/research/market_context.md §3.4.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.core.types import ActionType, ConsentStatus, FailureClass, PaymentRail
from src.core.models import MandateStateRecord
from src.guardrails.consent_gate import is_channel_permitted, ACTION_TO_CHANNEL
from src.guardrails.engine import compute_feasible_action_set


# ---------------------------------------------------------------------------
# Unit tests for is_channel_permitted()
# ---------------------------------------------------------------------------

def test_opted_in_permits_channel():
    """OPTED_IN explicitly allows the channel."""
    consent = {"WHATSAPP": ConsentStatus.OPTED_IN}
    assert is_channel_permitted(consent, "WHATSAPP") is True


def test_opted_out_blocks_channel():
    """OPTED_OUT explicitly blocks the channel."""
    consent = {"WHATSAPP": ConsentStatus.OPTED_OUT}
    assert is_channel_permitted(consent, "WHATSAPP") is False


def test_unknown_blocks_channel():
    """UNKNOWN consent status blocks the channel (fail-closed)."""
    consent = {"WHATSAPP": ConsentStatus.UNKNOWN}
    assert is_channel_permitted(consent, "WHATSAPP") is False


def test_missing_key_blocks_channel():
    """
    If the channel key is absent from the consent dict entirely,
    the channel is blocked. This is the fail-closed default:
    missing information -> deny, same as last_attempt_timestamp=None.
    """
    consent = {}  # No consent data at all
    assert is_channel_permitted(consent, "WHATSAPP") is False
    assert is_channel_permitted(consent, "SMS") is False
    assert is_channel_permitted(consent, "PAYMENT_LINK") is False


def test_action_to_channel_mapping_is_complete():
    """Every consent-gated action has a mapping entry."""
    assert "WHATSAPP_NUDGE" in ACTION_TO_CHANNEL
    assert "SMS_NUDGE" in ACTION_TO_CHANNEL
    assert "PAYMENT_LINK" in ACTION_TO_CHANNEL
    # Retries are NOT consent-gated (they're bank-rail operations, not customer comms)
    assert "SILENT_RETRY" not in ACTION_TO_CHANNEL
    assert "PIN_PROMPTED_RETRY" not in ACTION_TO_CHANNEL


# ---------------------------------------------------------------------------
# Integration tests via compute_feasible_action_set()
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> MandateStateRecord:
    """Helper: builds a soft-liquidity state with overrides."""
    defaults = dict(
        case_id="consent_test",
        mandate_id="man_consent",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("5000"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        pre_debit_notice_sent=True,
    )
    defaults.update(overrides)
    return MandateStateRecord(**defaults)


def test_engine_blocks_whatsapp_when_opted_out():
    """WHATSAPP_NUDGE removed from feasible set when customer opted out."""
    state = _make_state(channel_consent={
        "WHATSAPP": ConsentStatus.OPTED_OUT,
        "SMS": ConsentStatus.OPTED_IN,
        "PAYMENT_LINK": ConsentStatus.OPTED_IN,
    })
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.WHATSAPP_NUDGE not in actions
    assert ActionType.SMS_NUDGE in actions
    assert ActionType.PAYMENT_LINK in actions


def test_engine_blocks_sms_when_unknown():
    """SMS_NUDGE removed when consent is UNKNOWN (fail-closed)."""
    state = _make_state(channel_consent={
        "WHATSAPP": ConsentStatus.OPTED_IN,
        "SMS": ConsentStatus.UNKNOWN,
        "PAYMENT_LINK": ConsentStatus.OPTED_IN,
    })
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.WHATSAPP_NUDGE in actions
    assert ActionType.SMS_NUDGE not in actions
    assert ActionType.PAYMENT_LINK in actions


def test_engine_blocks_payment_link_when_opted_out():
    """PAYMENT_LINK removed when customer opted out."""
    state = _make_state(channel_consent={
        "WHATSAPP": ConsentStatus.OPTED_IN,
        "SMS": ConsentStatus.OPTED_IN,
        "PAYMENT_LINK": ConsentStatus.OPTED_OUT,
    })
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.WHATSAPP_NUDGE in actions
    assert ActionType.SMS_NUDGE in actions
    assert ActionType.PAYMENT_LINK not in actions


def test_engine_blocks_all_comms_when_no_consent_data():
    """
    Empty channel_consent dict (default) -> all three consent-gated
    channels blocked. Retries remain available (they're bank-rail
    operations, not customer communications).
    """
    state = _make_state(channel_consent={})
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.WHATSAPP_NUDGE not in actions
    assert ActionType.SMS_NUDGE not in actions
    assert ActionType.PAYMENT_LINK not in actions
    # Retries are NOT consent-gated
    assert ActionType.SILENT_RETRY in actions
    assert ActionType.PIN_PROMPTED_RETRY in actions


def test_engine_permits_all_when_fully_opted_in():
    """All channels permitted when customer has opted in to everything."""
    state = _make_state(channel_consent={
        "WHATSAPP": ConsentStatus.OPTED_IN,
        "SMS": ConsentStatus.OPTED_IN,
        "PAYMENT_LINK": ConsentStatus.OPTED_IN,
    })
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.WHATSAPP_NUDGE in actions
    assert ActionType.SMS_NUDGE in actions
    assert ActionType.PAYMENT_LINK in actions


def test_retries_unaffected_by_consent():
    """
    SILENT_RETRY and PIN_PROMPTED_RETRY are bank-rail operations,
    not customer communications. They must never be gated by consent.
    """
    state = _make_state(channel_consent={
        "WHATSAPP": ConsentStatus.OPTED_OUT,
        "SMS": ConsentStatus.OPTED_OUT,
        "PAYMENT_LINK": ConsentStatus.OPTED_OUT,
    })
    actions, _ = compute_feasible_action_set(state)
    assert ActionType.SILENT_RETRY in actions
    assert ActionType.PIN_PROMPTED_RETRY in actions
