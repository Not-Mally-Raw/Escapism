"""
RBI ₹15,000 Additional Factor Authentication (AFA) Enforcer Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §2.2 (RBI Digital Payments E-Mandate Framework).
"""

from decimal import Decimal

AFA_THRESHOLD_INR = Decimal("15000.00")


def is_silent_retry_permitted(amount_inr: Decimal | float | int) -> bool:
    """
    Evaluates whether an automated recurring debit may execute without customer PIN re-entry.

    Regulatory Citation:
        rbi_npci_regulations.md §2.2:
        - Amount <= ₹15,000: Eligible for SILENT_RETRY (automated background debit).
        - Amount > ₹15,000: SILENT_RETRY is legally prohibited. Every presentation requires
          customer-present PIN or 3DS authentication (PIN_PROMPTED_RETRY or PAYMENT_LINK).

    Args:
        amount_inr: Transaction principal amount in Indian Rupees.

    Returns:
        bool: True if silent retry is permitted (amount <= 15000), False if AFA is required.
    """
    dec_amount = Decimal(str(amount_inr))
    return dec_amount <= AFA_THRESHOLD_INR
