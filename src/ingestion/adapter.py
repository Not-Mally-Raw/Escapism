"""
Typed Event Adapter for Razorpay Webhook Ingestion Boundary.
Transforms raw Razorpay webhook envelopes into canonical MandateStateRecords.
Enforces fail-closed schema validation and executes failure diagnosis upstream of domain instantiation.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Optional, Union
from pydantic import ValidationError

from src.core.models import MandateStateRecord
from src.core.types import ConsentStatus, PaymentRail
from src.diagnosis.classifier import diagnose_failure
from src.diagnosis.models import DiagnosticOutput
from src.ingestion.models import (
    IngestionResult,
    MalformedPayloadError,
    PayloadValidationError,
    RazorpayWebhookEnvelope,
)


class RazorpayEventAdapter:
    """
    Adapter responsible for:
    1. Parsing and validating Razorpay webhook envelopes fail-closed.
    2. Converting currency amounts from paise (integer) to INR (Decimal).
    3. Extracting and mapping payment rails, error codes, and customer consent.
    4. Executing upstream failure diagnosis (`diagnose_failure`) BEFORE domain record creation.
    5. Constructing the immutable `MandateStateRecord`.
    """

    @classmethod
    def parse_event(
        cls,
        raw_payload: Union[str, bytes, Dict[str, Any]],
        event_id: Optional[str] = None,
        llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None,
    ) -> IngestionResult:
        """
        Main adapter entrypoint. Ingests raw JSON string, bytes, or parsed dict,
        performs fail-closed validation, diagnoses failure upstream, and returns IngestionResult.
        """
        payload_dict = cls._coerce_to_dict(raw_payload)

        # Detect format: Canonical Razorpay webhook envelope vs legacy / direct formats
        if cls._is_razorpay_webhook(payload_dict):
            return cls._parse_razorpay_webhook(payload_dict, event_id=event_id, llm_callable=llm_callable)
        elif "state" in payload_dict:
            return cls._parse_legacy_wrapped(payload_dict, event_id=event_id, llm_callable=llm_callable)
        elif "case_id" in payload_dict or "mandate_id" in payload_dict or "failure_code" in payload_dict:
            return cls._parse_flat_canonical(payload_dict, event_id=event_id, llm_callable=llm_callable)
        else:
            raise MalformedPayloadError(
                "Unrecognized payload structure: neither canonical Razorpay webhook nor valid domain format.",
                details={"keys": list(payload_dict.keys())},
            )

    @classmethod
    def _coerce_to_dict(cls, raw: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """Safely deserialize raw string/bytes into dictionary, failing closed on invalid JSON."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, bytes):
            try:
                raw_str = raw.decode("utf-8")
            except UnicodeDecodeError as e:
                raise MalformedPayloadError(f"Payload encoding error: {e}", details={"error": str(e)})
        elif isinstance(raw, str):
            raw_str = raw
        else:
            raise MalformedPayloadError(
                f"Unsupported raw payload type: {type(raw).__name__}",
                details={"type": str(type(raw))},
            )

        try:
            parsed = json.loads(raw_str)
            if not isinstance(parsed, dict):
                raise MalformedPayloadError(
                    f"Expected JSON object at root, got {type(parsed).__name__}",
                    details={"type": str(type(parsed))},
                )
            return parsed
        except json.JSONDecodeError as e:
            raise MalformedPayloadError(f"Invalid JSON payload: {e}", details={"error": str(e)})

    @classmethod
    def _is_razorpay_webhook(cls, payload: Dict[str, Any]) -> bool:
        """Check if dictionary has Razorpay event envelope markers."""
        if payload.get("entity") == "event" and "payload" in payload:
            return True
        if "event" in payload and "payload" in payload and isinstance(payload.get("payload"), dict):
            return True
        return False

    @classmethod
    def _parse_razorpay_webhook(
        cls,
        payload_dict: Dict[str, Any],
        event_id: Optional[str] = None,
        llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None,
    ) -> IngestionResult:
        """Parses canonical Razorpay webhook envelope."""
        try:
            envelope = RazorpayWebhookEnvelope.model_validate(payload_dict)
        except ValidationError as e:
            raise PayloadValidationError(
                f"Razorpay webhook envelope validation failed: {e}",
                details={"errors": e.errors()},
            )

        if not envelope.payload.payment or not envelope.payload.payment.entity:
            raise PayloadValidationError(
                "Webhook payload does not contain a valid payment entity",
                details={"event": envelope.event},
            )

        payment = envelope.payload.payment.entity

        # 1. Amount validation & conversion (paise to INR)
        if payment.amount is None or payment.amount <= 0:
            raise PayloadValidationError(
                f"Invalid payment amount: {payment.amount}. Must be strictly positive paise.",
                details={"amount": payment.amount},
            )
        amount_inr = (Decimal(payment.amount) / Decimal("100")).quantize(Decimal("0.01"))

        # Currency validation
        if payment.currency and payment.currency.upper() != "INR":
            raise PayloadValidationError(
                f"Unsupported currency: {payment.currency}. Only INR is supported.",
                details={"currency": payment.currency},
            )

        # 2. Payment rail mapping
        notes = payment.notes or {}
        rail = cls._extract_payment_rail(payment.method, notes)

        # 3. Extract bank error code and raw error text
        bank_code, raw_error_text = cls._extract_bank_error(payment, notes)
        if not bank_code:
            raise PayloadValidationError(
                "Unable to determine bank failure code from webhook acquirer data or error fields.",
                details={"payment_id": payment.id, "error_code": payment.error_code},
            )

        # 4. Upstream Failure Diagnosis (Executed BEFORE domain object construction)
        diagnostic = diagnose_failure(
            bank_code=bank_code,
            raw_error_text=raw_error_text,
            llm_callable=llm_callable,
        )

        # 5. Extract metadata and identifiers
        case_id = str(notes.get("case_id") or f"case_{payment.id}")
        mandate_id = str(notes.get("mandate_id") or payment.token_id or payment.order_id or f"man_{payment.id}")
        merchant_id = str(notes.get("merchant_id") or envelope.account_id or "mer_default_001")
        customer_id = str(payment.customer_id or notes.get("customer_id") or "cust_default_001")

        try:
            attempt_count = int(notes.get("attempt_count", 1))
        except (ValueError, TypeError):
            attempt_count = 1

        if not (1 <= attempt_count <= 4):
            raise PayloadValidationError(
                f"attempt_count must be between 1 and 4, got {attempt_count}",
                details={"attempt_count": attempt_count},
            )

        afa_required = cls._parse_bool(notes.get("afa_required", False))
        pre_debit_notice_sent = cls._parse_bool(notes.get("pre_debit_notice_sent", False))
        customer_timezone = str(notes.get("customer_timezone", "Asia/Kolkata"))

        # 6. Parse channel consent
        channel_consent = cls._parse_channel_consent(notes.get("channel_consent"))

        # 7. Parse failure timestamp
        failure_timestamp = cls._parse_timestamp(payment.created_at or envelope.created_at)

        # 8. Instantiate domain state record with already diagnosed failure_class
        try:
            state = MandateStateRecord(
                case_id=case_id,
                mandate_id=mandate_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
                rail=rail,
                amount_inr=amount_inr,
                attempt_count=attempt_count,
                failure_code=bank_code,
                failure_class=diagnostic.failure_class,
                error_description=raw_error_text or payment.error_description,
                error_source=payment.error_source,
                error_reason=payment.error_reason,
                issuer_bank=payment.bank,
                merchant_category=notes.get("merchant_category"),
                failure_timestamp=failure_timestamp,
                last_attempt_timestamp=cls._parse_optional_timestamp(notes.get("last_attempt_timestamp")),
                afa_required=afa_required,
                pre_debit_notice_sent=pre_debit_notice_sent,
                customer_timezone=customer_timezone,
                channel_consent=channel_consent,
            )
        except ValidationError as e:
            raise PayloadValidationError(
                f"Failed to instantiate MandateStateRecord: {e}",
                details={"errors": e.errors()},
            )

        return IngestionResult(
            state=state,
            diagnostic=diagnostic,
            raw_event_id=event_id or envelope.account_id,
            payload_format="razorpay_webhook",
        )

    @classmethod
    def _parse_legacy_wrapped(
        cls,
        payload_dict: Dict[str, Any],
        event_id: Optional[str] = None,
        llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None,
    ) -> IngestionResult:
        """Handles legacy test payloads wrapped in 'state'."""
        state_raw = payload_dict["state"]
        if not isinstance(state_raw, dict):
            raise PayloadValidationError("Payload 'state' must be a dictionary")

        state_data = dict(state_raw)
        bank_code = state_data.get("failure_code")
        if not bank_code:
            raise PayloadValidationError("Missing failure_code in legacy state payload")

        raw_error_text = payload_dict.get("raw_error_text") or state_data.get("error_description")

        # Execute diagnosis upstream
        diagnostic = diagnose_failure(
            bank_code=bank_code,
            raw_error_text=raw_error_text,
            llm_callable=llm_callable,
        )

        state_data["failure_class"] = diagnostic.failure_class
        if "amount_inr" in state_data and not isinstance(state_data["amount_inr"], Decimal):
            try:
                state_data["amount_inr"] = Decimal(str(state_data["amount_inr"]))
            except InvalidOperation:
                raise PayloadValidationError(f"Invalid amount_inr: {state_data['amount_inr']}")

        if "channel_consent" in state_data and isinstance(state_data["channel_consent"], dict):
            state_data["channel_consent"] = cls._parse_channel_consent(state_data["channel_consent"])

        try:
            state = MandateStateRecord(**state_data)
        except ValidationError as e:
            raise PayloadValidationError(
                f"Failed to instantiate MandateStateRecord from legacy payload: {e}",
                details={"errors": e.errors()},
            )

        return IngestionResult(
            state=state,
            diagnostic=diagnostic,
            raw_event_id=event_id,
            payload_format="legacy_wrapped",
        )

    @classmethod
    def _parse_flat_canonical(
        cls,
        payload_dict: Dict[str, Any],
        event_id: Optional[str] = None,
        llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None,
    ) -> IngestionResult:
        """Handles flat canonical dictionary representations."""
        state_data = dict(payload_dict)
        bank_code = state_data.get("failure_code")
        if not bank_code:
            raise PayloadValidationError("Missing failure_code in flat canonical payload")

        raw_error_text = state_data.get("raw_error_text") or state_data.get("error_description")

        diagnostic = diagnose_failure(
            bank_code=bank_code,
            raw_error_text=raw_error_text,
            llm_callable=llm_callable,
        )

        state_data["failure_class"] = diagnostic.failure_class
        if "amount_inr" in state_data and not isinstance(state_data["amount_inr"], Decimal):
            try:
                state_data["amount_inr"] = Decimal(str(state_data["amount_inr"]))
            except InvalidOperation:
                raise PayloadValidationError(f"Invalid amount_inr: {state_data['amount_inr']}")

        if "channel_consent" in state_data and isinstance(state_data["channel_consent"], dict):
            state_data["channel_consent"] = cls._parse_channel_consent(state_data["channel_consent"])

        # Remove keys not belonging to MandateStateRecord
        state_data.pop("raw_error_text", None)

        try:
            state = MandateStateRecord(**state_data)
        except ValidationError as e:
            raise PayloadValidationError(
                f"Failed to instantiate MandateStateRecord from flat payload: {e}",
                details={"errors": e.errors()},
            )

        return IngestionResult(
            state=state,
            diagnostic=diagnostic,
            raw_event_id=event_id,
            payload_format="canonical_flat",
        )

    @classmethod
    def _extract_payment_rail(cls, method: str, notes: Dict[str, Any]) -> PaymentRail:
        """Extracts and normalizes PaymentRail from method and notes."""
        if "rail" in notes:
            rail_str = str(notes["rail"]).upper()
            try:
                return PaymentRail(rail_str)
            except ValueError:
                pass

        norm_method = (method or "").strip().lower()
        if norm_method in ("upi", "upi_autopay"):
            return PaymentRail.UPI_AUTOPAY
        elif norm_method in ("emandate", "nach", "enach", "card", "netbanking"):
            return PaymentRail.ENACH
        else:
            # Default to UPI_AUTOPAY or ENACH based on method
            return PaymentRail.UPI_AUTOPAY

    @classmethod
    def _extract_bank_error(cls, payment: Any, notes: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Extracts bank failure code and descriptive text from payment entity."""
        acquirer_data = payment.acquirer_data or {}
        bank_code = acquirer_data.get("bank_error_code")
        
        error_parts = []
        if payment.error_description:
            error_parts.append(payment.error_description)
        bank_msg = acquirer_data.get("bank_error_message")
        if bank_msg and bank_msg not in error_parts:
            error_parts.append(bank_msg)
        if not error_parts and payment.description:
            error_parts.append(payment.description)

        raw_error_text = " - ".join(error_parts) if error_parts else None

        if not bank_code:
            # Fallback to direct error fields
            bank_code = payment.error_code or payment.error_reason or notes.get("failure_code")

        if bank_code:
            bank_code = str(bank_code).strip()

        return bank_code, raw_error_text

    @classmethod
    def _parse_bool(cls, val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "t")
        return False

    @classmethod
    def _parse_channel_consent(cls, consent_val: Any) -> Dict[str, ConsentStatus]:
        """Parses channel consent dictionary or JSON string into Dict[str, ConsentStatus]."""
        if not consent_val:
            return {}

        raw_dict = consent_val
        if isinstance(consent_val, str):
            try:
                raw_dict = json.loads(consent_val)
            except json.JSONDecodeError:
                return {}

        if not isinstance(raw_dict, dict):
            return {}

        result = {}
        for channel, status in raw_dict.items():
            if isinstance(status, ConsentStatus):
                result[channel] = status
            elif isinstance(status, str):
                try:
                    result[channel] = ConsentStatus(status.upper())
                except ValueError:
                    result[channel] = ConsentStatus.UNKNOWN
            else:
                result[channel] = ConsentStatus.UNKNOWN
        return result

    @classmethod
    def _parse_timestamp(cls, ts_val: Any) -> datetime:
        """Parses timestamp into a timezone-aware UTC datetime."""
        if isinstance(ts_val, datetime):
            if ts_val.tzinfo is None:
                return ts_val.replace(tzinfo=timezone.utc)
            return ts_val
        if isinstance(ts_val, (int, float)):
            return datetime.fromtimestamp(ts_val, tz=timezone.utc)
        if isinstance(ts_val, str):
            try:
                # Try ISO format
                dt = datetime.fromisoformat(ts_val)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @classmethod
    def _parse_optional_timestamp(cls, ts_val: Any) -> Optional[datetime]:
        if ts_val is None:
            return None
        return cls._parse_timestamp(ts_val)
