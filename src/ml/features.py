"""
Feature Extraction and Anti-Leakage Boundary for Recovery Propensity Model.
Extracts schema-constrained features from MandateStateRecord or equivalent dicts.

PCI-DSS & Governance:
Enforces strict rejection of ground-truth labels (anti-leakage) and raw PII / PAN / VPA (PCI-DSS).
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Union
from zoneinfo import ZoneInfo

from src.core.models import MandateStateRecord
from src.core.types import ConsentStatus, FailureClass, PaymentRail

IST = ZoneInfo("Asia/Kolkata")

# Banned field names that must NEVER enter feature extraction (PCI-DSS & Anti-Leakage)
LEAKAGE_FIELDS = {
    "ground_truth_recoverable",
    "ground_truth",
    "ground_truth_label",
}

BANNED_PII_FIELDS = {
    "pan",
    "card_number",
    "cvv",
    "raw_account_number",
    "bank_account_number",
    "aadhaar",
}

FEATURE_COLUMNS_CATEGORICAL = [
    "failure_class",
    "rail",
    "consent_whatsapp",
    "consent_sms",
    "consent_payment_link",
]

FEATURE_COLUMNS_NUMERIC = [
    "attempt_count",
    "amount_inr",
    "afa_required",
    "time_since_last_attempt_hours",
    "has_last_attempt",
    "pre_debit_notice_sent",
    "is_weekend",
    "hour_of_day",
    "consent_score",
]

FEATURE_COLUMNS_ALL = FEATURE_COLUMNS_CATEGORICAL + FEATURE_COLUMNS_NUMERIC


def extract_features(record: Union[MandateStateRecord, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts a strictly schema-validated feature dictionary for model inference/training.

    Anti-Leakage Guard:
        Raises ValueError if any ground-truth label field is present in input.

    PCI-DSS Guard:
        Raises ValueError if raw cardholder data (PAN) or prohibited PII is present.

    Args:
        record: MandateStateRecord instance or dictionary of observable mandate state.

    Returns:
        Dict[str, Any]: Schema-compliant feature mapping ready for pipeline transformation.
    """
    # 1. Inspect input dictionary for leakage & prohibited fields
    if isinstance(record, dict):
        keys_lower = {k.lower() for k in record.keys()}
        
        leakage_detected = keys_lower.intersection(LEAKAGE_FIELDS)
        if leakage_detected:
            raise ValueError(
                f"Anti-leakage violation: Ground truth label field(s) {leakage_detected} "
                "detected in feature extraction input."
            )
            
        banned_detected = keys_lower.intersection(BANNED_PII_FIELDS)
        if banned_detected:
            raise ValueError(
                f"PCI-DSS / Privacy violation: Prohibited PII/Cardholder field(s) {banned_detected} "
                "detected in feature extraction input."
            )

        # Normalize dictionary keys into a structured MandateStateRecord if needed,
        # or extract directly from dictionary
        if "case_id" in record and "failure_class" in record:
            state = MandateStateRecord(**record)
        else:
            raise ValueError("Input dictionary lacks required MandateStateRecord fields.")
    elif isinstance(record, MandateStateRecord):
        state = record
    else:
        raise TypeError(f"Expected MandateStateRecord or dict, got {type(record).__name__}")

    # 2. Extract failure class & rail as strings
    failure_class_str = state.failure_class.value if isinstance(state.failure_class, FailureClass) else str(state.failure_class)
    rail_str = state.rail.value if isinstance(state.rail, PaymentRail) else str(state.rail)

    # 3. Process timestamps & derived temporal features in IST
    ts = state.failure_timestamp
    if ts.tzinfo is None:
        raise ValueError("failure_timestamp must be timezone-aware (rejecting naive datetime).")
    ts_ist = ts.astimezone(IST)
    is_weekend = 1 if ts_ist.weekday() >= 5 else 0
    hour_of_day = ts_ist.hour

    if state.last_attempt_timestamp is not None:
        last_ts = state.last_attempt_timestamp
        if last_ts.tzinfo is None:
            raise ValueError("last_attempt_timestamp must be timezone-aware.")
        delta_seconds = (ts - last_ts).total_seconds()
        time_since_last_attempt_hours = max(0.0, float(delta_seconds) / 3600.0)
        has_last_attempt = 1
    else:
        time_since_last_attempt_hours = 0.0
        has_last_attempt = 0

    # 4. Process channel consent
    consent_dict = state.channel_consent or {}
    
    def _get_status_str(channel: str) -> str:
        val = consent_dict.get(channel, ConsentStatus.UNKNOWN)
        return val.value if isinstance(val, ConsentStatus) else str(val)

    consent_whatsapp = _get_status_str("WHATSAPP")
    consent_sms = _get_status_str("SMS")
    consent_payment_link = _get_status_str("PAYMENT_LINK")

    consent_score = sum(
        1 for ch in ["WHATSAPP", "SMS", "PAYMENT_LINK"]
        if consent_dict.get(ch) in (ConsentStatus.OPTED_IN, "OPTED_IN")
    )

    # 5. Build canonical feature dictionary
    return {
        "failure_class": failure_class_str,
        "rail": rail_str,
        "consent_whatsapp": consent_whatsapp,
        "consent_sms": consent_sms,
        "consent_payment_link": consent_payment_link,
        "attempt_count": int(state.attempt_count),
        "amount_inr": float(state.amount_inr),
        "afa_required": 1 if state.afa_required else 0,
        "time_since_last_attempt_hours": float(time_since_last_attempt_hours),
        "has_last_attempt": int(has_last_attempt),
        "pre_debit_notice_sent": 1 if state.pre_debit_notice_sent else 0,
        "is_weekend": int(is_weekend),
        "hour_of_day": int(hour_of_day),
        "consent_score": int(consent_score),
    }
