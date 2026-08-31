from typing import Any, Callable, Dict, Optional
from src.core.models import MandateStateRecord
from src.diagnosis.classifier import diagnose_failure
from src.diagnosis.models import DiagnosticOutput
from src.decision.optimizer import optimize_decision
from src.decision.models import DecisionResult
from src.orchestration.models import RawFailureEvent, OrchestrationResult
from pydantic import ValidationError

def process_failure_event(
    raw_event: Dict[str, Any],
    llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None
) -> OrchestrationResult:
    """
    Unified Orchestrator Entrypoint for E2E Mandate Recovery.
    Binds Track 2 (Diagnostics), Guardrails, Track 1 (ML), and Track 3 (Decision).
    
    Args:
        raw_event: A dictionary representing the raw failed mandate webhook/event.
        llm_callable: Optional mock/LLM callable for Track 2 semantic classification.
        
    Returns:
        OrchestrationResult: Contains the diagnostic output and the strictly validated DecisionResult.
    """
    # 0. Validate incoming raw event
    event = RawFailureEvent(**raw_event)
    
    # 1. Track 2: Semantic Classification
    diagnostic = diagnose_failure(
        bank_code=event.failure_code,
        raw_error_text=event.raw_error_text,
        llm_callable=llm_callable
    )
    
    # 2. Track 1 & Core: Prepare strict schema
    state = MandateStateRecord(
        case_id=event.case_id,
        mandate_id=event.mandate_id,
        merchant_id=event.merchant_id,
        customer_id=event.customer_id,
        rail=event.rail,
        amount_inr=event.amount_inr,
        attempt_count=event.attempt_count,
        failure_code=event.failure_code,
        failure_class=diagnostic.failure_class,
        error_description=event.error_description,
        error_source=event.error_source,
        error_reason=event.error_reason,
        issuer_bank=event.issuer_bank,
        merchant_category=event.merchant_category,
        failure_timestamp=event.failure_timestamp,
        last_attempt_timestamp=event.last_attempt_timestamp,
        afa_required=event.afa_required,
        pre_debit_notice_sent=event.pre_debit_notice_sent,
        customer_timezone=event.customer_timezone,
        channel_consent=event.channel_consent
    )
        
    # 3. Track 3 (Decision Engine) encapsulates Guardrails computation, ML inference (safely casting float to Decimal),
    # and Lift-EV selection.
    decision = optimize_decision(state)
    
    return OrchestrationResult(
        diagnostic=diagnostic,
        decision=decision
    )
