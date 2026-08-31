from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from src.core.types import PaymentRail, FailureClass
from src.diagnosis.models import DiagnosticOutput
from src.decision.models import DecisionResult

class RawFailureEvent(BaseModel):
    """
    Schema for the incoming webhook payload.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    case_id: str
    mandate_id: str
    merchant_id: str = "mer_default_001"
    customer_id: str = "cust_default_001"
    rail: PaymentRail
    amount_inr: Decimal = Field(gt=Decimal("0.00"))
    attempt_count: int = Field(ge=1, le=4)
    failure_code: str
    raw_error_text: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_reason: Optional[str] = None
    issuer_bank: Optional[str] = None
    merchant_category: Optional[str] = None
    failure_timestamp: str
    last_attempt_timestamp: Optional[str] = None
    afa_required: bool = False
    pre_debit_notice_sent: bool = False
    customer_timezone: str = "Asia/Kolkata"
    channel_consent: Dict[str, Any] = Field(default_factory=dict)

class OrchestrationResult(BaseModel):
    """
    Augmented DecisionResult that also exposes intermediate diagnostic outputs.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    diagnostic: DiagnosticOutput
    decision: DecisionResult
