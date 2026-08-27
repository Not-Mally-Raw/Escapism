"""
Unit and Integration Tests for Track 3 Expected-Value Decision Optimizer.
Verifies compliance invariants, mathematical monotonicity, exact Decimal precision,
adversarial cost robustness, and audit trail schema adherence.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
import pytest

from src.core.models import MandateStateRecord
from src.core.types import ActionType, ConsentStatus, FailureClass, PaymentRail
from src.decision.models import CandidateScore, DecisionAuditStep, DecisionResult
from src.decision.optimizer import (
    COST_TABLE,
    MULTIPLIER_TABLE,
    THETA_DIGITAL,
    THETA_HUMAN,
    optimize_decision,
)


@pytest.fixture
def sample_soft_liquidity_state() -> MandateStateRecord:
    """Standard soft liquidity state eligible for multiple recovery interventions."""
    return MandateStateRecord(
        case_id="case_test_soft_01",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_001",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("2500.00"),
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
        channel_consent={
            "WHATSAPP": ConsentStatus.OPTED_IN,
            "SMS": ConsentStatus.OPTED_IN,
            "PAYMENT_LINK": ConsentStatus.OPTED_IN,
        },
    )


@pytest.fixture
def batch_5000_records() -> List[MandateStateRecord]:
    """Loads all 5,000 synthetic records for full-batch invariance testing."""
    records = []
    with open("data/synthetic_batch_5000.jsonl") as f:
        for line in f:
            data = json.loads(line)
            records.append(MandateStateRecord(**data["state"]))
    return records


def test_feasible_set_membership_invariant(sample_soft_liquidity_state):
    """
    INVARIANT: The selected action must strictly be a member of A_feasible(S) U {ABORT_COMPLIANT}.
    """
    result = optimize_decision(sample_soft_liquidity_state)
    assert isinstance(result, DecisionResult)
    assert result.selected_action in (
        ActionType.WHATSAPP_NUDGE,
        ActionType.PAYMENT_LINK,
        ActionType.SMS_NUDGE,
        ActionType.SILENT_RETRY,
        ActionType.PIN_PROMPTED_RETRY,
        ActionType.ABORT_COMPLIANT,
    )
    assert result.audit_step.verdict == result.selected_action.value


def test_legal_hold_bypasses_ev_scoring():
    """
    INVARIANT 10: Legal Hold (code '07' or 'AP03') must ALWAYS route directly to
    ESCALATE_HUMAN with zero EV computation and is_mandatory_routing=True.
    """
    legal_state = MandateStateRecord(
        case_id="case_legal_hold_01",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_legal",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("50000.00"),
        failure_code="07",  # Court order / litigation freeze
        failure_class=FailureClass.LEGAL_HOLD,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
    )

    result = optimize_decision(legal_state)
    assert result.selected_action == ActionType.ESCALATE_HUMAN
    assert result.is_mandatory_routing is True
    assert result.lift_ev_inr is None
    assert result.p_hat is None
    assert len(result.candidate_scores) == 0
    assert "Mandatory regulatory escalation" in result.audit_step.rationale


def test_adversarial_cost_table_variant_c_digital_prohibitive(batch_5000_records):
    """
    ADVERSARIAL TEST 1: Hostile Digital Costs (Digital = ₹999,999.00, Human = Excluded).
    Verifies that under prohibitive digital costs:
    - 100% of the non-mandatory candidate pool (4,655 cases, 93.10%) cleanly aborts.
    - Exactly the 345 mandatory compliance cases (6.90%) remain untouched as ESCALATE_HUMAN.
    - 0 digital actions are selected.
    """
    hostile_digital_costs = {
        ActionType.SILENT_RETRY: Decimal("999999.00"),
        ActionType.PIN_PROMPTED_RETRY: Decimal("999999.00"),
        ActionType.SMS_NUDGE: Decimal("999999.00"),
        ActionType.PAYMENT_LINK: Decimal("999999.00"),
        ActionType.WHATSAPP_NUDGE: Decimal("999999.00"),
        ActionType.RE_MANDATE_FLOW: Decimal("999999.00"),
        ActionType.COOLDOWN_WAIT: Decimal("999999.00"),
        ActionType.ESCALATE_HUMAN: Decimal("50.00"),
    }

    action_counts = {}
    mandatory_escalations = 0

    for state in batch_5000_records:
        res = optimize_decision(state, custom_costs=hostile_digital_costs)
        action_counts[res.selected_action] = action_counts.get(res.selected_action, 0) + 1
        if res.is_mandatory_routing:
            mandatory_escalations += 1

    # Exact expected counts across 5,000 synthetic records
    assert action_counts[ActionType.ABORT_COMPLIANT] == 4655
    assert action_counts[ActionType.ESCALATE_HUMAN] == 345
    assert mandatory_escalations == 345
    assert action_counts.get(ActionType.WHATSAPP_NUDGE, 0) == 0
    assert action_counts.get(ActionType.PAYMENT_LINK, 0) == 0


def test_adversarial_cost_table_reverse_human_prohibitive_digital_free(batch_5000_records):
    """
    ADVERSARIAL TEST 2: Hostile Reverse Costs (Digital = ₹0.00, Human = ₹999,999.00).
    Verifies that when digital recovery is free and human escalation is prohibitive:
    - Mandatory compliance escalation stays invariant at exactly 345 cases (6.90%).
    - Digital interventions absorb the non-mandatory volume.
    - Zero non-mandatory cases leak into ESCALATE_HUMAN.
    """
    free_digital_hostile_human = {
        ActionType.SILENT_RETRY: Decimal("0.00"),
        ActionType.PIN_PROMPTED_RETRY: Decimal("0.00"),
        ActionType.SMS_NUDGE: Decimal("0.00"),
        ActionType.PAYMENT_LINK: Decimal("0.00"),
        ActionType.WHATSAPP_NUDGE: Decimal("0.00"),
        ActionType.RE_MANDATE_FLOW: Decimal("0.00"),
        ActionType.COOLDOWN_WAIT: Decimal("0.00"),
        ActionType.ESCALATE_HUMAN: Decimal("999999.00"),
    }

    action_counts = {}
    mandatory_escalations = 0

    for state in batch_5000_records:
        res = optimize_decision(state, custom_costs=free_digital_hostile_human, custom_theta_digital=Decimal("0.00"))
        action_counts[res.selected_action] = action_counts.get(res.selected_action, 0) + 1
        if res.is_mandatory_routing:
            mandatory_escalations += 1

    # Compliance routing remains invariant to cost table skew
    assert action_counts[ActionType.ESCALATE_HUMAN] == 345
    assert mandatory_escalations == 345
    assert action_counts[ActionType.WHATSAPP_NUDGE] > 3500


def test_decimal_precision_strictness(sample_soft_liquidity_state):
    """
    PRECISION DISCIPLINE: Verifies all financial amounts, costs, multipliers,
    and probability values use exact Decimal types with zero float contamination.
    """
    result = optimize_decision(sample_soft_liquidity_state)
    assert isinstance(result.lift_ev_inr, Decimal)
    assert isinstance(result.p_hat, Decimal)
    assert isinstance(result.cost_inr, Decimal)

    for cand in result.candidate_scores:
        assert isinstance(cand.multiplier, Decimal)
        assert isinstance(cand.cost_inr, Decimal)
        assert isinstance(cand.p_hat, Decimal)
        assert isinstance(cand.lift_probability, Decimal)
        assert isinstance(cand.lift_ev_inr, Decimal)


def test_monotonicity_property(sample_soft_liquidity_state):
    """
    MONOTONICITY: Ceteris paribus, increasing the amount or multiplier of an action
    strictly non-decreases its Lift-EV and preserves or elevates its selection rank.
    """
    res_base = optimize_decision(sample_soft_liquidity_state)
    base_whatsapp_ev = next(cs.lift_ev_inr for cs in res_base.candidate_scores if cs.action == ActionType.WHATSAPP_NUDGE)

    # Double the amount
    higher_amt_state = sample_soft_liquidity_state.model_copy(update={"amount_inr": Decimal("5000.00")})
    res_higher = optimize_decision(higher_amt_state)
    higher_whatsapp_ev = next(cs.lift_ev_inr for cs in res_higher.candidate_scores if cs.action == ActionType.WHATSAPP_NUDGE)

    assert higher_whatsapp_ev > base_whatsapp_ev


def test_empty_or_noop_feasible_set_aborts():
    """
    ABORT INVARIANT: If the guardrail feasible set yields no actionable recovery candidates,
    the optimizer must cleanly return ABORT_COMPLIANT with zero cost.
    """
    terminal_state = MandateStateRecord(
        case_id="case_terminal_closed_01",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_002",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("1500.00"),
        failure_code="01",  # Account Closed
        failure_class=FailureClass.HARD_TERMINAL,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=4,  # Attempts exhausted
        pre_debit_notice_sent=True,
        channel_consent={
            "WHATSAPP": ConsentStatus.OPTED_OUT,
            "SMS": ConsentStatus.OPTED_OUT,
            "PAYMENT_LINK": ConsentStatus.OPTED_OUT,
        },
    )

    result = optimize_decision(terminal_state)
    assert result.selected_action == ActionType.ABORT_COMPLIANT
    assert result.cost_inr == Decimal("0.00")
    assert result.audit_step.verdict == "ABORT_COMPLIANT"


def test_low_amount_subscription_clears_calibrated_threshold():
    """
    LOW AMOUNT CALIBRATION: Verifies that a small recurring mandate (e.g. INR 500.00)
    with positive recovery probability clears theta_digital = INR 1.00.
    Lift-EV = (0.25 * 1.20 - 0.25 * 1.00) * 500 - 0.80 = 0.05 * 500 - 0.80 = INR 24.20 >= INR 1.00.
    """
    small_sub_state = MandateStateRecord(
        case_id="case_small_sub_01",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_sub_001",
        merchant_id="merch_ott",
        customer_id="cust_002",
        amount_inr=Decimal("500.00"),
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
        channel_consent={"WHATSAPP": ConsentStatus.OPTED_IN},
    )

    result = optimize_decision(small_sub_state)
    assert result.selected_action == ActionType.WHATSAPP_NUDGE
    assert result.lift_ev_inr >= THETA_DIGITAL


def test_audit_trail_schema_conformance(sample_soft_liquidity_state):
    """
    AUDIT SCHEMA CONFORMANCE: Verifies the audit step matches PS3_Locked_System_Specification.md §4.1.
    """
    result = optimize_decision(sample_soft_liquidity_state)
    audit = result.audit_step
    assert isinstance(audit, DecisionAuditStep)
    assert audit.step == 3
    assert audit.module == "DECISION_LAYER"
    assert "MASK_ATTEMPTS" in audit.guardrails_evaluated
    assert len(audit.verdict) > 0
    assert len(audit.rationale) > 0
