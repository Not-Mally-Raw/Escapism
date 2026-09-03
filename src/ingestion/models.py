"""
Ingestion Boundary Data Models & Structured Exceptions.
Defines typed schemas for Razorpay webhook payloads, structured errors, and adapter results.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.core.models import MandateStateRecord
from src.diagnosis.models import DiagnosticOutput


class WebhookIngestionError(Exception):
    """Base structured exception for webhook ingestion and parsing failures."""
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class MalformedPayloadError(WebhookIngestionError):
    """Raised when incoming raw body is not valid JSON or structurally unrecognizable."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code="MALFORMED_PAYLOAD", message=message, details=details)


class PayloadValidationError(WebhookIngestionError):
    """Raised when required schema fields are missing, invalid types, or fail boundary checks."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code="VALIDATION_ERROR", message=message, details=details)


class SignatureVerificationError(WebhookIngestionError):
    """Raised when webhook signature validation fails."""
    def __init__(self, message: str = "Invalid webhook HMAC signature", details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code="INVALID_SIGNATURE", message=message, details=details)


class RazorpayAcquirerData(BaseModel):
    """Acquirer-level transaction metadata and bank failure codes."""
    model_config = ConfigDict(extra="allow")

    rrn: Optional[str] = None
    auth_code: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    bank_error_code: Optional[str] = None
    bank_error_message: Optional[str] = None


class RazorpayPaymentEntity(BaseModel):
    """Typed representation of Razorpay payment entity inside webhook payload."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Razorpay payment ID, e.g. pay_xxx")
    entity: str = Field(default="payment")
    amount: int = Field(gt=0, description="Amount in paise (must be strictly positive)")
    currency: str = Field(default="INR", description="Currency code (e.g. INR)")
    status: str = Field(description="Payment status, e.g. failed")
    order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    international: Optional[bool] = False
    method: str = Field(description="Payment method, e.g. upi, emandate, nach, card")
    amount_refunded: Optional[int] = 0
    refund_status: Optional[str] = None
    captured: Optional[bool] = False
    description: Optional[str] = None
    card_id: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    vpa: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    customer_id: Optional[str] = None
    token_id: Optional[str] = None
    notes: Dict[str, Any] = Field(default_factory=dict, description="Metadata key-value pairs")
    fee: Optional[int] = None
    tax: Optional[int] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    acquirer_data: Optional[Dict[str, Any]] = None
    created_at: Optional[int] = None


class RazorpayPaymentPayload(BaseModel):
    """Container for payment entity."""
    model_config = ConfigDict(extra="allow")
    entity: RazorpayPaymentEntity


class RazorpayWebhookPayload(BaseModel):
    """Top-level payload structure containing payment or other entities."""
    model_config = ConfigDict(extra="allow")
    payment: Optional[RazorpayPaymentPayload] = None


class RazorpayWebhookEnvelope(BaseModel):
    """Canonical Razorpay Webhook Event Envelope."""
    model_config = ConfigDict(extra="allow")

    entity: str = Field(default="event")
    account_id: Optional[str] = None
    event: str = Field(description="Event name, e.g. mandate.debit.failed or payment.failed")
    contains: List[str] = Field(default_factory=list)
    payload: RazorpayWebhookPayload
    created_at: Optional[int] = None


class IngestionResult(BaseModel):
    """
    Immutable result of event boundary ingestion.
    Contains both the validated domain state record and the upstream diagnostic output.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: MandateStateRecord
    diagnostic: DiagnosticOutput
    raw_event_id: Optional[str] = None
    payload_format: str = Field(default="razorpay_webhook", description="Format detected during ingestion")
