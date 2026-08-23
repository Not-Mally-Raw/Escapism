"""
Regression tests for the reconciliation fixes applied per the 26-point adversarial review.
Each test proves a specific fix that closes a gap identified during the review.
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pydantic import ValidationError

from src.core.types import ActionType, FailureClass, PaymentRail
from src.core.models import MandateStateRecord
from src.guardrails.engine import compute_feasible_action_set
from src.diagnosis.models import DiagnosticOutput
from src.diagnosis.ambiguity_handler import resolve_ambiguity, AMBIGUITY_THRESHOLD_HEURISTIC
from evals.metrics import ProductionOutcome, GroundTruthLabel, PaymentState, calculate_nrr, calculate_fer


# ---------------------------------------------------------------------------
# Item 3: last_attempt_timestamp=None with attempt_count > 1 must BLOCK retries
# ---------------------------------------------------------------------------

def test_missing_timestamp_blocks_retries_when_attempt_count_above_1():
    """
    If attempt_count > 1 but last_attempt_timestamp is None, the spacing check
    cannot be performed. Fail-closed: SILENT_RETRY and PIN_PROMPTED_RETRY
    must be removed from the feasible set even without current_time.
    """
    state = MandateStateRecord(
        case_id="gap_test_001",
        mandate_id="man_001",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("5000"),
        attempt_count=2,  # Not first attempt
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        last_attempt_timestamp=None,  # Missing — cannot verify spacing
        pre_debit_notice_sent=True,
    )
    # No current_time passed — the temporal check block is not entered,
    # but the NEW fail-closed block should still remove retries.
    actions, _ = compute_feasible_action_set(state, current_time=None)

    assert ActionType.SILENT_RETRY not in actions, \
        "SILENT_RETRY must be blocked when last_attempt_timestamp is None and attempt_count > 1"
    assert ActionType.PIN_PROMPTED_RETRY not in actions, \
        "PIN_PROMPTED_RETRY must be blocked when last_attempt_timestamp is None and attempt_count > 1"
    # Non-retry actions should still be available
    assert ActionType.PAYMENT_LINK in actions
    assert ActionType.WHATSAPP_NUDGE in actions


def test_missing_timestamp_does_not_block_first_attempt():
    """
    If attempt_count == 1, last_attempt_timestamp is naturally None (no prior attempt).
    Retries should NOT be blocked in this case — the first attempt is the original presentation.
    """
    state = MandateStateRecord(
        case_id="gap_test_002",
        mandate_id="man_002",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("5000"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        last_attempt_timestamp=None,
        pre_debit_notice_sent=True,
    )
    actions, _ = compute_feasible_action_set(state, current_time=None)

    assert ActionType.SILENT_RETRY in actions, \
        "First attempt with no prior timestamp should still allow retries"


# ---------------------------------------------------------------------------
# Item 5: DiagnosticOutput must reject unexpected fields (extra="forbid")
# ---------------------------------------------------------------------------

def test_diagnostic_output_rejects_extra_fields():
    """
    If an LLM returns extra fields (e.g., "execute": true, "override_guardrail": true),
    DiagnosticOutput validation must reject them. This is a security property.
    """
    with pytest.raises(ValidationError) as exc_info:
        DiagnosticOutput(
            failure_class=FailureClass.SOFT_LIQUIDITY,
            confidence=0.9,
            evidence=["Test evidence"],
            execute=True,  # Malicious/unexpected extra field
        )
    assert "extra" in str(exc_info.value).lower() or "Extra inputs" in str(exc_info.value)


def test_diagnostic_output_rejects_override_field():
    """Second malicious pattern: attempting to override guardrail logic."""
    with pytest.raises(ValidationError):
        DiagnosticOutput(
            failure_class=FailureClass.SOFT_LIQUIDITY,
            confidence=0.9,
            evidence=["Test"],
            override_guardrail=True,
        )


def test_diagnostic_output_accepts_valid_input():
    """Valid input with exactly three defined fields must succeed."""
    output = DiagnosticOutput(
        failure_class=FailureClass.SOFT_LIQUIDITY,
        confidence=0.85,
        evidence=["Failure code Z9 indicates insufficient balance"],
    )
    assert output.failure_class == FailureClass.SOFT_LIQUIDITY
    assert output.confidence == 0.85
    assert len(output.evidence) == 1


# ---------------------------------------------------------------------------
# Item 4: ProductionOutcome has no ground_truth_recoverable
# ---------------------------------------------------------------------------

def test_production_outcome_has_no_ground_truth():
    """
    ProductionOutcome must not accept a ground_truth_recoverable field.
    This prevents label leakage into production code by construction.
    """
    with pytest.raises(ValidationError):
        ProductionOutcome(
            case_id="test_001",
            amount_inr=Decimal("1000"),
            final_state=PaymentState.CAPTURED,
            escalated_to_human=False,
            ground_truth_recoverable=True,
        )


def test_ground_truth_label_is_separate():
    """GroundTruthLabel exists as a separate model for evaluation only."""
    label = GroundTruthLabel(
        case_id="test_001",
        ground_truth_recoverable=True,
    )
    assert label.ground_truth_recoverable is True


# ---------------------------------------------------------------------------
# Item 9: NRR denominator excludes legal-hold cases
# ---------------------------------------------------------------------------

def test_nrr_excludes_legal_hold_from_denominator():
    """
    Legal-hold cases (code 07/AP03) are routed to ESCALATE_HUMAN by regulation,
    not by model choice. They should be excluded from the NRR denominator.
    """
    outcomes = [
        ProductionOutcome(case_id="c1", amount_inr=Decimal("1000"), final_state=PaymentState.CAPTURED, escalated_to_human=False),
        ProductionOutcome(case_id="c2", amount_inr=Decimal("1000"), final_state=PaymentState.FAILED, escalated_to_human=False),
        ProductionOutcome(case_id="legal_hold", amount_inr=Decimal("5000"), final_state=PaymentState.FAILED, escalated_to_human=True),
    ]
    # Without exclusion: denominator = 7000, recovered = 1000, NRR = ~14.3%
    # With exclusion:    denominator = 2000, recovered = 1000, NRR = 50%
    _, pct_with_exclusion = calculate_nrr(outcomes, exclude_legal_hold_case_ids={"legal_hold"})
    _, pct_without_exclusion = calculate_nrr(outcomes)

    assert abs(pct_with_exclusion - 0.50) < 0.001, \
        "NRR with legal-hold exclusion should be 50%"
    assert abs(pct_without_exclusion - 1000 / 7000) < 0.001, \
        "NRR without exclusion should be ~14.3%"


# ---------------------------------------------------------------------------
# FER requires explicit join between ProductionOutcome and GroundTruthLabel
# ---------------------------------------------------------------------------

def test_fer_uses_separate_label_join():
    """FER calculation requires explicit join of outcomes + labels by case_id."""
    outcomes = [
        ProductionOutcome(case_id="c1", amount_inr=Decimal("1000"), final_state=PaymentState.FAILED, escalated_to_human=True),
        ProductionOutcome(case_id="c2", amount_inr=Decimal("2000"), final_state=PaymentState.FAILED, escalated_to_human=True),
        ProductionOutcome(case_id="c3", amount_inr=Decimal("3000"), final_state=PaymentState.CAPTURED, escalated_to_human=False),
    ]
    labels = [
        GroundTruthLabel(case_id="c1", ground_truth_recoverable=True),  # FALSE escalation
        GroundTruthLabel(case_id="c2", ground_truth_recoverable=False), # Correct escalation
        GroundTruthLabel(case_id="c3", ground_truth_recoverable=True),
    ]
    fer = calculate_fer(outcomes, labels)
    # 2 escalated, 1 was ground-truth recoverable => FER = 0.5
    assert abs(fer - 0.5) < 0.001


# ---------------------------------------------------------------------------
# Item 6: Threshold constant is accessible and labeled as heuristic
# ---------------------------------------------------------------------------

def test_ambiguity_threshold_is_heuristic_value():
    """The threshold constant must exist and equal the initial heuristic value."""
    assert AMBIGUITY_THRESHOLD_HEURISTIC == 0.40


def test_ambiguity_handler_downgrades_low_confidence():
    """Low-confidence diagnosis should be downgraded to AMBIGUOUS_DECLINE."""
    diagnosis = DiagnosticOutput(
        failure_class=FailureClass.SOFT_LIQUIDITY,
        confidence=0.30,  # Below the 0.40 heuristic
        evidence=["Uncertain signal"],
    )
    resolved = resolve_ambiguity(diagnosis)
    assert resolved.failure_class == FailureClass.AMBIGUOUS_DECLINE


def test_ambiguity_handler_preserves_high_confidence():
    """Above-threshold diagnosis should be preserved."""
    diagnosis = DiagnosticOutput(
        failure_class=FailureClass.SOFT_LIQUIDITY,
        confidence=0.85,
        evidence=["Strong Z9 signal"],
    )
    resolved = resolve_ambiguity(diagnosis)
    assert resolved.failure_class == FailureClass.SOFT_LIQUIDITY
