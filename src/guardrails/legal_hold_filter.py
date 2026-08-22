"""
NPCI / Statutory Legal Hold & Mandatory Escalation Filter Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §2.4 (NPCI e-NACH Procedural Guidelines).
"""

# Return codes indicating court orders, statutory freezes, or litigation holds
LEGAL_HOLD_CODES = {"07", "AP03"}


def requires_mandatory_escalation(failure_code: str) -> bool:
    """
    Checks if a return code denotes a legal hold or mandatory human escalation requirement.

    Regulatory Citation:
        rbi_npci_regulations.md §2.4:
        - Code '07': Payment stopped under court order / litigation.
        - Code 'AP03': Account frozen by regulatory authority.
        When present, all automated retries and customer outreach MUST cease immediately.
        The feasible action set collapses strictly to {ActionType.ESCALATE_HUMAN}.

    Args:
        failure_code: Raw bank switch error / return code string.

    Returns:
        bool: True if code triggers mandatory immediate escalation, False otherwise.
    """
    clean_code = failure_code.strip().upper()
    return clean_code in LEGAL_HOLD_CODES
