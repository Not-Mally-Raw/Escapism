"""
Ambiguity Handling for Diagnostics.
Resolves uncertainty and flags when human escalation or strict fallback is needed.
"""
from typing import Optional
from src.core.types import FailureClass
from src.diagnosis.models import DiagnosticOutput

CONFIDENCE_THRESHOLD = 0.40

def resolve_ambiguity(diagnosis: DiagnosticOutput) -> DiagnosticOutput:
    """
    Evaluates a diagnosis for low confidence and applies the Uncertainty Protocol
    (as described in error_taxonomy.md §4).
    
    If the LLM or classifier is uncertain (confidence <= 0.40), we explicitly
    flag it or downgrade the action path (e.g. pivoting to AMBIGUOUS_DECLINE or 
    demanding human escalation).
    """
    # For fail-closed property (Constraint B6): if input is fundamentally indeterminate,
    # we force a safe failure class.
    
    if diagnosis.confidence <= CONFIDENCE_THRESHOLD:
        # If it's already an ambiguous decline, we leave it.
        # Otherwise, we might force it to ambiguous or escalate.
        # This implementation will be expanded when the full decision layer is built.
        return DiagnosticOutput(
            failure_class=FailureClass.AMBIGUOUS_DECLINE,
            confidence=diagnosis.confidence,
            evidence=diagnosis.evidence + ["Downgraded due to low confidence threshold"]
        )
        
    return diagnosis
