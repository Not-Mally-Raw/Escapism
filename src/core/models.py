"""
Pydantic v2 Domain Models for Mandate Recovery Engine.
All state models are immutable snapshots (frozen) with strict boundary validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.core.types import ActionType, ConsentStatus, FailureClass, PaymentRail


class AttemptLogEntry(BaseModel):
    """Immutable record of an individual presentation attempt."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_number: int = Field(ge=1, le=4)
    timestamp: datetime
    action_taken: ActionType
    within_non_peak_window: bool
    spacing_satisfied: bool
    outcome: str


class MandateStateRecord(BaseModel):
    """
    Core immutable domain state representation of a failed mandate case.
    Encapsulates identifiers, financial context, failure diagnostics,
    execution counters, and regulatory compliance flags.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(description="Unique case identifier")
    mandate_id: str = Field(description="Underlying recurring mandate token")
    merchant_id: str = Field(default="mer_default_001")
    customer_id: str = Field(default="cust_default_001")
    rail: PaymentRail
    amount_inr: Decimal = Field(gt=Decimal("0.00"), description="Principal amount in INR")
    attempt_count: int = Field(ge=1, le=4, description="Lifetime presentation count in current cycle (1 to 4)")
    failure_code: str = Field(description="Raw bank switch error code (e.g. Z9, 04, 07)")
    failure_class: FailureClass
    error_description: Optional[str] = Field(
        default=None,
        description="Free-text failure description from Razorpay/bank payload, sanitized before LLM use",
    )
    error_source: Optional[str] = Field(default=None, description="Failure source such as customer, bank, or razorpay")
    error_reason: Optional[str] = Field(default=None, description="Granular gateway/bank failure reason")
    issuer_bank: Optional[str] = Field(default=None, description="Issuer bank identifier when available")
    merchant_category: Optional[str] = Field(default=None, description="Merchant vertical/category when available")
    failure_timestamp: datetime
    last_attempt_timestamp: Optional[datetime] = None
    afa_required: bool = Field(default=False, description="Computed or explicit flag indicating if AFA is required")
    pre_debit_notice_sent: bool = Field(default=False, description="Whether pre-debit notice >=24h was dispatched")
    customer_timezone: str = Field(default="Asia/Kolkata", description="IANA Timezone of the recipient")
    channel_consent: Dict[str, ConsentStatus] = Field(
        default_factory=dict,
        description="Per-channel consent state (WHATSAPP, SMS, PAYMENT_LINK). "
                    "Missing keys are treated as UNKNOWN (fail-closed)."
    )
