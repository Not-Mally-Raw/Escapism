import pytest
from decimal import Decimal
from datetime import datetime, timezone
from src.core.types import PaymentRail, FailureClass, ActionType, ConsentStatus
from src.orchestration.engine import process_failure_event
from src.orchestration.models import OrchestrationResult
from src.diagnosis.models import DiagnosticOutput

def mock_llm(code: str, text: str) -> DiagnosticOutput:
    return DiagnosticOutput(
        failure_class=FailureClass.SOFT_LIQUIDITY,
        confidence=0.9,
        evidence=["Mocked LLM interpretation for testing"]
    )

def test_golden_thread_process_failure_event():
    """P0: Strengthen golden-thread assertions"""
    raw_event = {
        "case_id": "case_12345",
        "mandate_id": "mandate_9876",
        "rail": PaymentRail.UPI_AUTOPAY.value,
        "amount_inr": "5000.00",
        "attempt_count": 1,
        "failure_code": "U19",
        "raw_error_text": "Insufficient funds in customer account",
        "failure_timestamp": datetime.now(timezone.utc).isoformat(),
        "channel_consent": {
            "WHATSAPP": ConsentStatus.OPTED_IN,
            "SMS": ConsentStatus.OPTED_IN,
            "PAYMENT_LINK": ConsentStatus.OPTED_IN
        }
    }
    
    result = process_failure_event(raw_event, llm_callable=mock_llm)
    
    assert isinstance(result, OrchestrationResult)
    decision = result.decision
    assert decision.case_id == "case_12345"
    
    # Assert it returns a digital action, not ABORT_COMPLIANT or ESCALATE_HUMAN
    assert decision.selected_action in [
        ActionType.WHATSAPP_NUDGE, 
        ActionType.PAYMENT_LINK, 
        ActionType.SMS_NUDGE, 
        ActionType.PIN_PROMPTED_RETRY
    ]
    
    # Check mandatory routing flag and basic EV fields
    assert decision.is_mandatory_routing is False
    assert decision.lift_ev_inr is not None
    assert decision.lift_ev_inr >= Decimal("0.00")
    
    # P1: Add feasible-set membership assertion
    # The feasible set contains everything the guardrails allowed. The selected action MUST be within the candidate_scores evaluated (which means it's feasible).
    candidate_actions = [cs.action for cs in decision.candidate_scores]
    assert decision.selected_action in candidate_actions
    assert result.diagnostic.failure_class == FailureClass.SOFT_LIQUIDITY

def test_mandatory_escalation_path():
    """P0: Add full-path mandatory escalation test (LEGAL_HOLD / code 07)"""
    raw_event = {
        "case_id": "case_legal_hold",
        "mandate_id": "mandate_9876",
        "rail": PaymentRail.UPI_AUTOPAY.value,
        "amount_inr": "5000.00",
        "attempt_count": 1,
        "failure_code": "07", # This typically maps to LEGAL_HOLD deterministically
        "failure_timestamp": datetime.now(timezone.utc).isoformat(),
        "channel_consent": {}
    }
    
    # P1: Explicit test / documentation of behaviour when llm_callable is None.
    # We pass None. The deterministic taxonomy (Track 2) should intercept '07' and map it to LEGAL_HOLD without LLM.
    result = process_failure_event(raw_event, llm_callable=None)
    
    decision = result.decision
    assert result.diagnostic.failure_class == FailureClass.LEGAL_HOLD
    assert decision.selected_action == ActionType.ESCALATE_HUMAN
    assert decision.is_mandatory_routing is True
    assert decision.lift_ev_inr is None # Bypassed EV math
