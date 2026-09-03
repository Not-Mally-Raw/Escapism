"""
NPCI/RBI Legal Hold and Regulatory Freeze Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §3.3 (Legal Holds).
"""

from src.core.taxonomy import CODE_TO_FAILURE_CLASS, LEGAL_HOLD_CODES

KNOWN_CODES = set(CODE_TO_FAILURE_CLASS.keys())

def requires_mandatory_escalation(failure_code: str) -> bool:
    """
    Checks if the failure code represents a terminal legal hold or regulatory
    freeze (e.g., e-NACH Code '07' or UPI 'AP03'). Also acts as a fail-closed 
    safety gate: any completely unrecognized/uncatalogued code is routed 
    to mandatory escalation (ESCALATE_HUMAN) to prevent failing open.

    Args:
        failure_code: Raw bank switch error code.

    Returns:
        bool: True if debit must be escalated for compliance or unknown reasons.
    """
    if not failure_code:
        return True
    
    code = failure_code.strip().upper()
    if code not in KNOWN_CODES:
        return True
    
    if code in LEGAL_HOLD_CODES:
        return True
        
    return False

