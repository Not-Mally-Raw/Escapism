"""
Evaluation Metrics for AI Revenue Recovery System.
Enforces the strict terminal financial success state definition for NRR.
"""
from decimal import Decimal
from typing import List
from enum import StrEnum
from pydantic import BaseModel

class PaymentState(StrEnum):
    INTERVENTION_SENT = "INTERVENTION_SENT"
    LINK_OPENED = "LINK_OPENED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"

class ExecutionOutcome(BaseModel):
    case_id: str
    amount_inr: Decimal
    final_state: PaymentState
    ground_truth_recoverable: bool
    escalated_to_human: bool

def calculate_nrr(outcomes: List[ExecutionOutcome]) -> tuple[Decimal, float]:
    """
    Calculates Net Revenue Recovered (NRR).
    STRICT COMPLIANCE: Only CAPTURED and SETTLED states count as revenue.
    Returns: (total_recovered_inr, recovery_percentage)
    """
    total_eligible = sum(o.amount_inr for o in outcomes)
    if total_eligible == 0:
        return Decimal("0.00"), 0.0

    terminal_success_states = {PaymentState.CAPTURED, PaymentState.SETTLED}
    
    recovered = sum(
        o.amount_inr for o in outcomes 
        if o.final_state in terminal_success_states
    )
    
    percentage = float(recovered / total_eligible)
    return recovered, percentage

def calculate_fer(outcomes: List[ExecutionOutcome]) -> float:
    """
    Calculates False Escalation Rate (FER).
    FER = (Escalated AND Ground-Truth Recoverable) / Total Escalated
    """
    escalated = [o for o in outcomes if o.escalated_to_human]
    if not escalated:
        return 0.0
        
    false_escalations = [o for o in escalated if o.ground_truth_recoverable]
    return len(false_escalations) / len(escalated)
