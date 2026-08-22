"""
NPCI/RBI Legal Hold and Regulatory Freeze Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §3.3 (Legal Holds).
"""

KNOWN_CODES = {
    # UPI AutoPay
    "Z9", "U19", "U30", "U69", "U28", "Z7", "Z8",
    # e-NACH
    "01", "02", "04", "05", "06", "07",
    # Custom/Internal
    "AP01", "AP02", "AP03", "AP04", "AP05"
}

def requires_mandatory_escalation(failure_code: str) -> bool:
    """
    Checks if the failure code represents a terminal legal hold or regulatory
    freeze (e.g., e-NACH Code '07' or UPI 'AP03'). Also acts as a fail-closed 
    safety gate: any completely unrecognized/uncatalogued code is routed 
    to mandatory escalation (ABORT_COMPLIANT) to prevent failing open.

    Args:
        failure_code: Raw bank switch error code.

    Returns:
        bool: True if debit must be aborted for compliance or unknown reasons.
    """
    if failure_code not in KNOWN_CODES:
        return True
    
    if failure_code in ["07", "AP03"]:
        return True
        
    return False
