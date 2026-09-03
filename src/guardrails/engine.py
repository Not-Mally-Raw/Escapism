"""
Deterministic Guardrail Orchestrator Engine.
Citing: docs/knowledge_base/rbi_npci_regulations.md §3 (Combined Feasible Action Mask).
"""

from datetime import datetime
from typing import Optional

from src.core.models import MandateStateRecord
from src.core.types import ActionType, FailureClass
from src.guardrails.afa_enforcer import is_silent_retry_permitted
from src.guardrails.attempt_limiter import check_attempt_cap
from src.guardrails.consent_gate import is_channel_permitted, ACTION_TO_CHANNEL
from src.guardrails.contact_gate import is_within_contact_hours, next_valid_contact_window
from src.guardrails.legal_hold_filter import requires_mandatory_escalation
from src.guardrails.spacing_validator import check_spacing, get_min_spacing_delta
from src.guardrails.window_mask import is_in_non_peak_window, next_valid_execution_window


def compute_feasible_action_set(
    state: MandateStateRecord,
    current_time: Optional[datetime] = None,
) -> tuple[set[ActionType], set[ActionType]]:
    """
    Computes the strictly feasible primary action set and mandatory regulatory notification set
    for a given mandate state record.

    Regulatory Citation:
        rbi_npci_regulations.md §3:
        A_feasible(S) = A_universe ∩ Mask_Attempts(k) ∩ Mask_Spacing(Δt) ∩
                        Mask_Window(t) ∩ Mask_AFA(Amount) ∩ Mask_FPC(t_contact) ∩ Mask_Legal(Code)

    Args:
        state: Immutable snapshot of the mandate failure record.
        current_time: Optional candidate evaluation timestamp. If provided, applies real-time
                      execution window and contact hours filtering.

    Returns:
        tuple[set[ActionType], set[ActionType]]:
            - primary_actions: Mutually-exclusive recovery interventions available to the decision layer.
            - mandatory_notifications: Co-occurring regulatory notifications required by RBI.
    """
    # 1. Check Legal Hold & Litigation (Short-Circuit)
    # Citing: rbi_npci_regulations.md §2.4 — Code 07 requires immediate human escalation
    if requires_mandatory_escalation(state.failure_code) or state.failure_class == FailureClass.LEGAL_HOLD:
        return {ActionType.ESCALATE_HUMAN}, set()

    # 2. Mandatory Co-Occurring Notifications
    # Citing: rbi_npci_regulations.md §2.3 (Pre-debit notice >=24h) & Post-txn notice
    mandatory_notifications: set[ActionType] = set()
    if not state.pre_debit_notice_sent:
        mandatory_notifications.add(ActionType.SEND_PRE_DEBIT_NOTICE)
    mandatory_notifications.add(ActionType.SEND_POST_TXN_NOTICE)

    # 3. Base Primary Action Universe
    primary_actions: set[ActionType] = {
        ActionType.SILENT_RETRY,
        ActionType.PIN_PROMPTED_RETRY,
        ActionType.PAYMENT_LINK,
        ActionType.WHATSAPP_NUDGE,
        ActionType.SMS_NUDGE,
        ActionType.RE_MANDATE_FLOW,
        ActionType.COOLDOWN_WAIT,
        ActionType.ESCALATE_HUMAN,
        ActionType.ABORT_COMPLIANT,
    }

    # 4. Apply NPCI Attempt Cap Guardrail (k <= 4)
    # Citing: rbi_npci_regulations.md §1.1 — k >= 4 exhausts all presentation attempts
    if not check_attempt_cap(state.attempt_count):
        primary_actions.discard(ActionType.SILENT_RETRY)
        primary_actions.discard(ActionType.PIN_PROMPTED_RETRY)

    # 5. Apply RBI ₹15,000 AFA Threshold Guardrail
    # Citing: rbi_npci_regulations.md §2.2 — Amount > ₹15,000 masks out SILENT_RETRY
    if not is_silent_retry_permitted(state.amount_inr):
        primary_actions.discard(ActionType.SILENT_RETRY)

    # 5b. Apply Pre-Debit Notice Gate (Instruction 2)
    # Citing: rbi_npci_regulations.md §2.3 — Retries are NOT in feasible set until notice sent >=24h prior.
    if not state.pre_debit_notice_sent:
        primary_actions.discard(ActionType.SILENT_RETRY)
        primary_actions.discard(ActionType.PIN_PROMPTED_RETRY)


    # 6. Apply Hard Terminal Failure Class Filter
    if state.failure_class == FailureClass.HARD_TERMINAL:
        # Cannot retry closed/blocked accounts on bank rail
        # Clear ALL recovery actions; terminal states must abort cleanly
        primary_actions = {ActionType.ABORT_COMPLIANT}

    # 6c. Apply Channel Consent Gate (Self-Imposed Best Practice)
    # Citing: docs/research/market_context.md §3.4
    # Fail-closed: UNKNOWN or OPTED_OUT consent blocks the channel.
    for action_name, channel_key in ACTION_TO_CHANNEL.items():
        action_type = ActionType(action_name)
        if action_type in primary_actions:
            if not is_channel_permitted(state.channel_consent, channel_key):
                primary_actions.discard(action_type)

    # 7. Temporal Filtering — Fail-Closed on Missing Evidence
    # If attempt_count > 1 but last_attempt_timestamp is None, we cannot verify spacing.
    # Fail-closed: block retries rather than assuming spacing is satisfied.
    if state.attempt_count > 1 and state.last_attempt_timestamp is None:
        primary_actions.discard(ActionType.SILENT_RETRY)
        primary_actions.discard(ActionType.PIN_PROMPTED_RETRY)

    # 8. Optional Real-Time Temporal Filtering (if current_time is passed)
    if current_time is not None and state.last_attempt_timestamp is not None:
        next_attempt_number = min(state.attempt_count + 1, 4)

        # Spacing interval validation
        spacing_ok = check_spacing(next_attempt_number, state.last_attempt_timestamp, current_time)
        window_ok = is_in_non_peak_window(current_time)
        contact_ok = is_within_contact_hours(current_time, state.customer_timezone)

        # If spacing or bank window not met right now, immediate auto-debits cannot fire at current_time
        if not (spacing_ok and window_ok):
            primary_actions.discard(ActionType.SILENT_RETRY)
            primary_actions.discard(ActionType.PIN_PROMPTED_RETRY)

        # If customer contact hours violated at current_time, direct interactive nudges cannot fire right now
        if not contact_ok:
            primary_actions.discard(ActionType.WHATSAPP_NUDGE)
            primary_actions.discard(ActionType.SMS_NUDGE)

    return primary_actions, mandatory_notifications
