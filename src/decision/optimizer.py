"""
Track 3 Expected-Value Decision Optimizer.

Core Decision Formulation:
    Lift-EV(a | S) = (P̂(S) · m(a) − P̂(S) · m(noop)) · Amount − C(a)
    a* = argmax_{a ∈ A_eligible(S)} Lift-EV(a | S)
    if Lift-EV(a* | S) >= θ_digital:
        return a*
    else:
        return ABORT_COMPLIANT

Static Multiplier Ranking Disclosure:
    🔴 MODELED ASSUMPTION (m(a) table):
    Under this flat-multiplier MVP (m(a) ∈ [0.85, 1.20]), channel selection among
    mutually-feasible alternatives is governed by the pre-registered static multiplier
    ranking (m(WHATSAPP_NUDGE) = 1.20 > m(PAYMENT_LINK) = 1.15 > m(SMS_NUDGE) = 1.10)
    rather than individualized contextual uplift modeling. Contextual heterogeneous
    treatment effect estimation is explicitly deferred to future roadmap work.

Escalation Routing Invariant:
    ESCALATE_HUMAN is a terminal compliance routing state for regulatory cases
    (e.g., LEGAL_HOLD codes 07/AP03 and terminal account blocks with no alternatives).
    Per Requirement 6, ESCALATE_HUMAN is excluded from routine EV competition against
    digital recovery channels to protect scarce manual call capacity.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Set

from src.core.models import MandateStateRecord
from src.core.types import ActionType, FailureClass
from src.decision.models import CandidateScore, DecisionAuditStep, DecisionResult
from src.guardrails.engine import compute_feasible_action_set
from src.ml.inference import predict_recovery_probability

# =============================================================================
# Pre-Registered & Frozen Cost Table C(a) in INR (🔴 Modeled Assumptions)
# Anchored to DLT/Meta messaging rates and BPO support labor economics
# =============================================================================
COST_TABLE: Dict[ActionType, Decimal] = {
    ActionType.SILENT_RETRY: Decimal("0.05"),        # Bank rail retry infra
    ActionType.PIN_PROMPTED_RETRY: Decimal("0.10"),  # UPI collect push trigger
    ActionType.SMS_NUDGE: Decimal("0.50"),          # DLT enterprise SMS rate
    ActionType.PAYMENT_LINK: Decimal("0.75"),       # Hosted link + notification
    ActionType.WHATSAPP_NUDGE: Decimal("0.80"),     # WhatsApp Business API utility rate
    ActionType.RE_MANDATE_FLOW: Decimal("2.50"),    # Tokenization & mandate re-setup
    ActionType.COOLDOWN_WAIT: Decimal("0.00"),      # Internal timer, zero direct cost
    ActionType.ESCALATE_HUMAN: Decimal("50.00"),    # Manual support review labor cost
}

# =============================================================================
# Pre-Registered & Frozen Multiplier Table m(a) (🔴 Modeled Assumptions)
# Capped within [0.85, 1.30] based on channel engagement research
# =============================================================================
MULTIPLIER_TABLE: Dict[ActionType, Decimal] = {
    ActionType.SILENT_RETRY: Decimal("1.00"),
    ActionType.PIN_PROMPTED_RETRY: Decimal("1.05"),
    ActionType.SMS_NUDGE: Decimal("1.10"),
    ActionType.PAYMENT_LINK: Decimal("1.15"),
    ActionType.WHATSAPP_NUDGE: Decimal("1.20"),
    ActionType.RE_MANDATE_FLOW: Decimal("0.90"),
    ActionType.COOLDOWN_WAIT: Decimal("0.95"),
    ActionType.ESCALATE_HUMAN: Decimal("1.30"),
}

# Baseline Passive Multiplier (doing nothing extra)
M_NOOP = Decimal("1.00")

# Calibrated Decision Thresholds
THETA_DIGITAL = Decimal("1.00")  # Minimum required net rupee lift for digital actions
THETA_HUMAN = Decimal("25.00")   # Gate for scarce human labor capacity
DELTA = Decimal("1.00")          # Uniform minimum lift margin over noop


def optimize_decision(
    state: MandateStateRecord,
    current_time: Optional[datetime] = None,
    model_path: Optional[Path] = None,
    custom_costs: Optional[Dict[ActionType, Decimal]] = None,
    custom_multipliers: Optional[Dict[ActionType, Decimal]] = None,
    custom_theta_digital: Optional[Decimal] = None,
    custom_theta_human: Optional[Decimal] = None,
) -> DecisionResult:
    """
    Evaluates feasible recovery actions and selects the optimal intervention via Lift-EV.

    Pipeline Steps:
        1. Evaluate deterministic guardrails to obtain strictly feasible action set A_feasible(S).
        2. If A_feasible(S) == {ESCALATE_HUMAN} (e.g. Legal Hold): Route directly to ESCALATE_HUMAN
           bypassing EV formula (Invariant 10).
        3. If A_eligible is empty or contains only non-actionable elements: Return ABORT_COMPLIANT.
        4. Obtain point estimate P̂(S) from Track 1 ML model via predict_recovery_probability().
        5. For each candidate a ∈ A_eligible, compute Lift-EV(a | S) using exact Decimal arithmetic.
        6. Select a* = argmax Lift-EV(a | S).
        7. If Lift-EV(a* | S) >= θ_digital: Return a*. Else return ABORT_COMPLIANT.

    Args:
        state: Immutable MandateStateRecord.
        current_time: Optional evaluation timestamp for temporal guardrail filtering.
        model_path: Optional custom path to serialized scikit-learn pipeline.
        custom_costs: Optional custom cost dictionary (for adversarial/sensitivity benchmarks).
        custom_multipliers: Optional custom multiplier dictionary.
        custom_theta_digital: Optional custom digital gating threshold.
        custom_theta_human: Optional custom human gating threshold.

    Returns:
        DecisionResult: Schema-locked optimization verdict and audit step.
    """
    eval_ts = (current_time or datetime.now(timezone.utc)).isoformat()
    costs = custom_costs or COST_TABLE
    multipliers = custom_multipliers or MULTIPLIER_TABLE
    theta_digital = custom_theta_digital if custom_theta_digital is not None else THETA_DIGITAL
    theta_human = custom_theta_human if custom_theta_human is not None else THETA_HUMAN

    # 1. Guardrail Feasible Set Computation
    feasible_actions, mandatory_notices = compute_feasible_action_set(state, current_time=current_time)

    # 2. Mandatory Compliance Routing Gate (Invariant 10: Legal Hold & Infeasible Terminal States)
    if feasible_actions == {ActionType.ESCALATE_HUMAN}:
        audit_step = DecisionAuditStep(
            timestamp=eval_ts,
            verdict="ESCALATE_HUMAN",
            rationale=(
                f"Mandatory regulatory escalation: Failure code '{state.failure_code}' "
                f"or failure class '{state.failure_class}' requires human intervention. "
                "EV scoring bypassed by compliance invariant."
            ),
        )
        return DecisionResult(
            case_id=state.case_id,
            selected_action=ActionType.ESCALATE_HUMAN,
            is_mandatory_routing=True,
            lift_ev_inr=None,
            p_hat=None,
            cost_inr=costs.get(ActionType.ESCALATE_HUMAN),
            candidate_scores=[],
            audit_step=audit_step,
            execution_timestamp=eval_ts,
        )

    # 3. Formulate Candidate Recovery Actions (Exclude ABORT_COMPLIANT and ESCALATE_HUMAN)
    # Requirement 6: ESCALATE_HUMAN is a terminal state, not scored in routine EV competition.
    candidate_actions = [
        a for a in feasible_actions
        if a in costs and a not in (ActionType.ABORT_COMPLIANT, ActionType.ESCALATE_HUMAN)
    ]

    # 4. Fallback on Empty Candidate Set
    if not candidate_actions:
        audit_step = DecisionAuditStep(
            timestamp=eval_ts,
            verdict="ABORT_COMPLIANT",
            rationale="No recovery actions permitted in feasible set after guardrail masking.",
        )
        return DecisionResult(
            case_id=state.case_id,
            selected_action=ActionType.ABORT_COMPLIANT,
            is_mandatory_routing=False,
            lift_ev_inr=Decimal("0.00"),
            p_hat=None,
            cost_inr=Decimal("0.00"),
            candidate_scores=[],
            audit_step=audit_step,
            execution_timestamp=eval_ts,
        )

    # 5. Score Candidates via Track 1 Model and Lift-EV Formula
    p_hat_float = predict_recovery_probability(state, model_path=model_path)
    p_hat = Decimal(str(round(p_hat_float, 4)))
    amount_inr = state.amount_inr

    candidate_scores: list[CandidateScore] = []
    for action in candidate_actions:
        m_a = multipliers.get(action, Decimal("1.00"))
        c_a = costs.get(action, Decimal("0.00"))

        # Lift probability over passive noop baseline: ΔP = P̂(S) · m(a) - P̂(S) · m(noop)
        lift_prob = (p_hat * m_a) - (p_hat * M_NOOP)
        
        # Lift-EV = ΔP · Amount - C(a)
        lift_ev = (lift_prob * amount_inr) - c_a
        cleared = (lift_ev >= theta_digital)

        candidate_scores.append(
            CandidateScore(
                action=action,
                multiplier=m_a,
                cost_inr=c_a,
                p_hat=p_hat,
                lift_probability=lift_prob,
                lift_ev_inr=lift_ev,
                cleared_threshold=cleared,
            )
        )

    # 6. Argmax Selection over Candidates
    # Deterministic tie-breaking by candidate order
    best_candidate = max(candidate_scores, key=lambda cs: cs.lift_ev_inr)

    # 7. Threshold Gating against θ_digital
    if best_candidate.cleared_threshold:
        selected_action = best_candidate.action
        rationale = (
            f"Selected '{selected_action}' with optimal Lift-EV of ₹{best_candidate.lift_ev_inr:.2f} "
            f"(P̂={p_hat:.4f}, m={best_candidate.multiplier}, Cost=₹{best_candidate.cost_inr:.2f}), "
            f"clearing threshold θ_digital=₹{theta_digital:.2f}."
        )
        verdict = selected_action.value
    else:
        selected_action = ActionType.ABORT_COMPLIANT
        rationale = (
            f"Optimal candidate '{best_candidate.action}' yielded Lift-EV of ₹{best_candidate.lift_ev_inr:.2f}, "
            f"failing threshold θ_digital=₹{theta_digital:.2f}. Safely aborting automated intervention."
        )
        verdict = "ABORT_COMPLIANT"

    audit_step = DecisionAuditStep(
        timestamp=eval_ts,
        verdict=verdict,
        rationale=rationale,
    )

    return DecisionResult(
        case_id=state.case_id,
        selected_action=selected_action,
        is_mandatory_routing=False,
        lift_ev_inr=best_candidate.lift_ev_inr,
        p_hat=p_hat,
        cost_inr=best_candidate.cost_inr if selected_action != ActionType.ABORT_COMPLIANT else Decimal("0.00"),
        candidate_scores=candidate_scores,
        audit_step=audit_step,
        execution_timestamp=eval_ts,
    )
