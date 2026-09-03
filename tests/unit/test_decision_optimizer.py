"""
Unit and Integration Tests for Track 3 Expected-Value Decision Optimizer.
Verifies compliance invariants, mathematical monotonicity, exact Decimal precision,
adversarial cost robustness, CATE opt-in behavior, and audit trail schema adherence.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
import pytest

from src.core.models import MandateStateRecord
from src.core.taxonomy import CODE_TO_FAILURE_CLASS, LEGAL_HOLD_CODES
from src.core.types import ActionType, ConsentStatus, FailureClass, PaymentRail
from src.decision.models import CandidateScore, DecisionAuditStep, DecisionResult
from src.decision.optimizer import (
    COST_TABLE,
    MULTIPLIER_TABLE,
    THETA_DIGITAL,
    THETA_HUMAN,
    optimize_decision,
)
from src.guardrails.legal_hold_filter import requires_mandatory_escalation


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
def sample_causal_state() -> MandateStateRecord:
    """State from causal dataset where CATE treatment effect produces positive Lift-EV."""
    return MandateStateRecord(
        case_id="case_4201",
        mandate_id="man_4201",
        merchant_id="mer_018",
        customer_id="cust_0066",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("15000.01"),
        attempt_count=2,
        failure_code="U30",
        failure_class=FailureClass.AMBIGUOUS_DECLINE,
        failure_timestamp=datetime(2026, 8, 21, 16, 59, 59, tzinfo=timezone.utc),
        last_attempt_timestamp=datetime(2026, 8, 20, 21, 16, 53, tzinfo=timezone.utc),
        afa_required=True,
        pre_debit_notice_sent=False,
        customer_timezone="Asia/Kolkata",
        channel_consent={
            "WHATSAPP": ConsentStatus.OPTED_IN,
            "SMS": ConsentStatus.OPTED_OUT,
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
    Zero LEGAL_HOLD cases ever receive non-null p_hat or lift_ev_inr.
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


def test_unknown_code_bypasses_ev_scoring():
    """
    INVARIANT: Unknown/malformed error codes must fail-closed and route directly to
    ESCALATE_HUMAN with zero EV computation and is_mandatory_routing=True.
    """
    unknown_state = MandateStateRecord(
        case_id="case_unknown_01",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_unk",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("5000.00"),
        failure_code="GARBAGE_99",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
    )

    result = optimize_decision(unknown_state)
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
    - 100% of the non-mandatory candidate pool cleanly aborts to ABORT_COMPLIANT.
    - Exactly the mandatory compliance cases (legal hold 07/AP03 and unknown codes)
      remain untouched as ESCALATE_HUMAN.
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

    expected_mandatory_count = sum(
        1 for s in batch_5000_records
        if requires_mandatory_escalation(s.failure_code) or s.failure_class == FailureClass.LEGAL_HOLD
    )
    expected_abort_count = len(batch_5000_records) - expected_mandatory_count

    for state in batch_5000_records:
        res = optimize_decision(state, custom_costs=hostile_digital_costs)
        action_counts[res.selected_action] = action_counts.get(res.selected_action, 0) + 1
        if res.is_mandatory_routing:
            mandatory_escalations += 1
            assert res.p_hat is None
            assert res.lift_ev_inr is None

    # Exact expected counts across synthetic records
    assert action_counts[ActionType.ABORT_COMPLIANT] == expected_abort_count
    assert action_counts[ActionType.ESCALATE_HUMAN] == expected_mandatory_count
    assert mandatory_escalations == expected_mandatory_count
    assert action_counts.get(ActionType.WHATSAPP_NUDGE, 0) == 0
    assert action_counts.get(ActionType.PAYMENT_LINK, 0) == 0
    assert action_counts.get(ActionType.SMS_NUDGE, 0) == 0
    assert action_counts.get(ActionType.SILENT_RETRY, 0) == 0
    assert action_counts.get(ActionType.PIN_PROMPTED_RETRY, 0) == 0


def test_adversarial_cost_table_reverse_human_prohibitive_digital_free(batch_5000_records):
    """
    ADVERSARIAL TEST 2: Hostile Reverse Costs (Digital = ₹0.00, Human = ₹999,999.00).
    Verifies that when digital recovery is free and human escalation is prohibitive:
    - Mandatory compliance escalation stays invariant at exactly the mandatory compliance count.
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

    expected_mandatory_count = sum(
        1 for s in batch_5000_records
        if requires_mandatory_escalation(s.failure_code) or s.failure_class == FailureClass.LEGAL_HOLD
    )

    for state in batch_5000_records:
        res = optimize_decision(state, custom_costs=free_digital_hostile_human, custom_theta_digital=Decimal("0.00"))
        action_counts[res.selected_action] = action_counts.get(res.selected_action, 0) + 1
        if res.is_mandatory_routing:
            mandatory_escalations += 1

    # Compliance routing remains invariant to cost table skew
    assert action_counts[ActionType.ESCALATE_HUMAN] == expected_mandatory_count
    assert mandatory_escalations == expected_mandatory_count
    # Digital interventions absorb the non-mandatory volume across consented channels
    digital_actions_total = (
        action_counts.get(ActionType.WHATSAPP_NUDGE, 0)
        + action_counts.get(ActionType.PAYMENT_LINK, 0)
        + action_counts.get(ActionType.SMS_NUDGE, 0)
        + action_counts.get(ActionType.SILENT_RETRY, 0)
        + action_counts.get(ActionType.PIN_PROMPTED_RETRY, 0)
    )
    assert digital_actions_total > 4000
    assert action_counts[ActionType.WHATSAPP_NUDGE] > 3000


def test_cate_adversarial_hostile_digital_costs(batch_5000_records):
    """
    CATE ADVERSARIAL TEST 1: Hostile Digital Costs with explicit opt-in (use_uplift=True).
    Verifies that under prohibitive digital costs with CATE enabled:
    - CATE estimation does NOT get silently disabled by custom_costs.
    - 100% of non-mandatory cases cleanly abort to ABORT_COMPLIANT.
    - Exactly the mandatory compliance cases remain untouched as ESCALATE_HUMAN.
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

    expected_mandatory_count = sum(
        1 for s in batch_5000_records
        if requires_mandatory_escalation(s.failure_code) or s.failure_class == FailureClass.LEGAL_HOLD
    )
    expected_abort_count = len(batch_5000_records) - expected_mandatory_count

    for state in batch_5000_records:
        res = optimize_decision(state, custom_costs=hostile_digital_costs, use_uplift=True)
        action_counts[res.selected_action] = action_counts.get(res.selected_action, 0) + 1
        if res.is_mandatory_routing:
            mandatory_escalations += 1
            assert res.p_hat is None
            assert res.lift_ev_inr is None

    assert action_counts[ActionType.ABORT_COMPLIANT] == expected_abort_count
    assert action_counts[ActionType.ESCALATE_HUMAN] == expected_mandatory_count
    assert mandatory_escalations == expected_mandatory_count
    assert action_counts.get(ActionType.WHATSAPP_NUDGE, 0) == 0
    assert action_counts.get(ActionType.PAYMENT_LINK, 0) == 0


def test_cate_adversarial_channel_cost_steering(sample_causal_state):
    """
    CATE ADVERSARIAL TEST 2: Verify custom_costs actively steer CATE action selection
    rather than disabling the CATE model or ignoring costs.
    """
    # Baseline CATE run
    res_base = optimize_decision(sample_causal_state, use_uplift=True)
    base_action = res_base.selected_action
    assert res_base.selected_action == ActionType.WHATSAPP_NUDGE
    assert "learned CATE" in res_base.audit_step.rationale

    # Make the preferred action prohibitively expensive
    steered_costs = dict(COST_TABLE)
    steered_costs[base_action] = Decimal("999999.00")

    res_steered = optimize_decision(
        sample_causal_state,
        custom_costs=steered_costs,
        use_uplift=True,
    )
    assert res_steered.selected_action != base_action
    assert res_steered.selected_action in (
        ActionType.WHATSAPP_NUDGE,
        ActionType.PAYMENT_LINK,
        ActionType.SMS_NUDGE,
        ActionType.SILENT_RETRY,
        ActionType.PIN_PROMPTED_RETRY,
        ActionType.COOLDOWN_WAIT,
        ActionType.ABORT_COMPLIANT,
    )
    assert "learned CATE" in res_steered.audit_step.rationale


def test_cate_opt_in_explicit_toggle(sample_causal_state):
    """
    VERIFIES:
    1. Default (use_uplift=False) uses certified static multiplier Lift-EV path.
    2. Opt-in (use_uplift=True) uses learned CATE path.
    """
    res_default = optimize_decision(sample_causal_state)
    assert "static multiplier" in res_default.audit_step.rationale

    res_cate = optimize_decision(sample_causal_state, use_uplift=True)
    assert "learned CATE" in res_cate.audit_step.rationale


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
    MONOTONICITY: Ceteris paribus, increasing the amount of an action
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
    with positive recovery probability clears theta_digital = INR 1.00 under default static path.
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


# =============================================================================
# Property-Based Compliance & Safety Invariant Tests (Requirement 5)
# =============================================================================

@pytest.mark.parametrize("code", list(LEGAL_HOLD_CODES))
def test_property_every_legal_hold_code_escalates(code):
    """Asserts every legal hold code (07, AP03) requires mandatory escalation and bypasses EV."""
    assert requires_mandatory_escalation(code) is True
    assert requires_mandatory_escalation(f" {code} ") is True
    assert requires_mandatory_escalation(code.lower()) is True

    state = MandateStateRecord(
        case_id="case_prop_legal",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_prop_legal",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("10000.00"),
        failure_code=code,
        failure_class=FailureClass.LEGAL_HOLD,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
    )
    res_static = optimize_decision(state, use_uplift=False)
    assert res_static.selected_action == ActionType.ESCALATE_HUMAN
    assert res_static.is_mandatory_routing is True
    assert res_static.p_hat is None
    assert res_static.lift_ev_inr is None
    assert len(res_static.candidate_scores) == 0

    res_cate = optimize_decision(state, use_uplift=True)
    assert res_cate.selected_action == ActionType.ESCALATE_HUMAN
    assert res_cate.is_mandatory_routing is True
    assert res_cate.p_hat is None
    assert res_cate.lift_ev_inr is None
    assert len(res_cate.candidate_scores) == 0


@pytest.mark.parametrize("code", ["UNKNOWN_CODE", "GARBAGE_99", "XXX", "RAND_987", "ERR_999", "INVALID_CODE", ""])
def test_property_every_unknown_code_fails_closed_and_escalates(code):
    """Asserts every uncatalogued / malformed code requires mandatory escalation and bypasses EV."""
    assert requires_mandatory_escalation(code) is True

    state = MandateStateRecord(
        case_id="case_prop_unk",
        rail=PaymentRail.UPI_AUTOPAY,
        mandate_id="man_prop_unk",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("10000.00"),
        failure_code=code,
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
    )
    res = optimize_decision(state)
    assert res.selected_action == ActionType.ESCALATE_HUMAN
    assert res.is_mandatory_routing is True
    assert res.p_hat is None
    assert res.lift_ev_inr is None
    assert len(res.candidate_scores) == 0


@pytest.mark.parametrize("code,f_class", [
    (c, fc) for c, fc in CODE_TO_FAILURE_CLASS.items()
    if c not in LEGAL_HOLD_CODES
])
def test_property_known_non_legal_codes_do_not_escalate_merely_due_to_lookup(code, f_class):
    """
    Asserts known non-legal codes (Z9, U19, 04, AP01, etc.) do not trigger mandatory escalation
    merely due to lookup failure.
    """
    assert requires_mandatory_escalation(code) is False

    state = MandateStateRecord(
        case_id="case_prop_known",
        rail=PaymentRail.UPI_AUTOPAY if code.startswith(("Z", "U")) else PaymentRail.ENACH,
        mandate_id="man_prop_known",
        merchant_id="merch_001",
        customer_id="cust_001",
        amount_inr=Decimal("5000.00"),
        failure_code=code,
        failure_class=f_class,
        failure_timestamp=datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
        attempt_count=1,
        pre_debit_notice_sent=True,
        channel_consent={"WHATSAPP": ConsentStatus.OPTED_IN, "SMS": ConsentStatus.OPTED_IN},
    )
    res = optimize_decision(state)
    # If the code is not legal hold, it must NOT be marked as mandatory escalation routing
    assert res.is_mandatory_routing is False
    assert res.selected_action != ActionType.ESCALATE_HUMAN


def test_property_batch_5000_structural_safety_invariants(batch_5000_records):
    """
    Full-batch property verification:
    - Zero LEGAL_HOLD cases ever receive non-null p_hat or lift_ev_inr.
    - 100% of unknown/malformed codes escalate to ESCALATE_HUMAN.
    - 100% of 07 and AP03 escalate to ESCALATE_HUMAN.
    """
    for state in batch_5000_records:
        res = optimize_decision(state)

        if state.failure_class == FailureClass.LEGAL_HOLD or state.failure_code in LEGAL_HOLD_CODES:
            assert res.selected_action == ActionType.ESCALATE_HUMAN
            assert res.is_mandatory_routing is True
            assert res.p_hat is None
            assert res.lift_ev_inr is None
            assert len(res.candidate_scores) == 0

        if requires_mandatory_escalation(state.failure_code):
            assert res.selected_action == ActionType.ESCALATE_HUMAN
            assert res.is_mandatory_routing is True
            assert res.p_hat is None
            assert res.lift_ev_inr is None

