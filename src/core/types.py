"""
Core Type Definitions for AI Revenue Recovery System.
Defines finite domain enums for payment rails, failure classes, and action types.
"""

from enum import StrEnum


class PaymentRail(StrEnum):
    """Supported recurring payment rails."""
    UPI_AUTOPAY = "UPI_AUTOPAY"
    ENACH = "ENACH"


class FailureClass(StrEnum):
    """Categorization of transaction/mandate failure root causes."""
    SOFT_LIQUIDITY = "SOFT_LIQUIDITY"
    HARD_TERMINAL = "HARD_TERMINAL"
    TECHNICAL_RETRYABLE = "TECHNICAL_RETRYABLE"
    AMBIGUOUS_DECLINE = "AMBIGUOUS_DECLINE"
    LEGAL_HOLD = "LEGAL_HOLD"


class ActionType(StrEnum):
    """
    Action space for revenue recovery.
    Distinguishes primary mutually-exclusive recovery actions from
    mandatory co-occurring regulatory notifications.
    """
    # Primary Mutually-Exclusive Recovery Interventions
    SILENT_RETRY = "SILENT_RETRY"
    PIN_PROMPTED_RETRY = "PIN_PROMPTED_RETRY"
    PAYMENT_LINK = "PAYMENT_LINK"
    WHATSAPP_NUDGE = "WHATSAPP_NUDGE"
    SMS_NUDGE = "SMS_NUDGE"
    RE_MANDATE_FLOW = "RE_MANDATE_FLOW"
    COOLDOWN_WAIT = "COOLDOWN_WAIT"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    ABORT_COMPLIANT = "ABORT_COMPLIANT"

    # Mandatory Co-Occurring Regulatory Notifications (RBI Obligations)
    # Note: These are compliance obligations, not recovery interventions.
    # They co-occur with primary actions rather than competing in the feasible set.
    SEND_PRE_DEBIT_NOTICE = "SEND_PRE_DEBIT_NOTICE"  # Must fire >=24h before any debit execution
    SEND_POST_TXN_NOTICE = "SEND_POST_TXN_NOTICE"    # Must fire after every attempt (success or failure)
