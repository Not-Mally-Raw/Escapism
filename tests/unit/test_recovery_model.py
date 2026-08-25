"""
Unit Tests for Recovery Propensity Model (Track 1).
Verifies model inference, anti-leakage protection, PCI-DSS field rejection,
structural sanity on LEGAL_HOLD, and determinism.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from src.core.models import MandateStateRecord
from src.core.types import ConsentStatus, FailureClass, PaymentRail
from src.ml.inference import get_model_pipeline, predict_recovery_probability


@pytest.fixture
def sample_soft_liquidity_record() -> MandateStateRecord:
    return MandateStateRecord(
        case_id="test_case_001",
        mandate_id="man_001",
        merchant_id="mer_001",
        customer_id="cust_001",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("2500.00"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
        last_attempt_timestamp=None,
        afa_required=False,
        pre_debit_notice_sent=True,
        customer_timezone="Asia/Kolkata",
        channel_consent={
            "WHATSAPP": ConsentStatus.OPTED_IN,
            "SMS": ConsentStatus.OPTED_IN,
            "PAYMENT_LINK": ConsentStatus.OPTED_IN,
        },
    )


@pytest.fixture
def sample_legal_hold_record() -> MandateStateRecord:
    return MandateStateRecord(
        case_id="test_case_002",
        mandate_id="man_002",
        merchant_id="mer_001",
        customer_id="cust_002",
        rail=PaymentRail.ENACH,
        amount_inr=Decimal("15000.00"),
        attempt_count=1,
        failure_code="07",
        failure_class=FailureClass.LEGAL_HOLD,
        failure_timestamp=datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
        last_attempt_timestamp=None,
        afa_required=False,
        pre_debit_notice_sent=True,
        customer_timezone="Asia/Kolkata",
        channel_consent={
            "WHATSAPP": ConsentStatus.OPTED_IN,
            "SMS": ConsentStatus.OPTED_IN,
            "PAYMENT_LINK": ConsentStatus.OPTED_IN,
        },
    )


def test_model_artifact_loads_successfully():
    """Confirms the serialized recovery propensity pipeline exists and loads."""
    pipeline = get_model_pipeline()
    assert pipeline is not None
    assert hasattr(pipeline, "predict_proba")


def test_predict_recovery_probability_valid_range(sample_soft_liquidity_record):
    """Prediction on a valid MandateStateRecord returns a float in [0.0, 1.0]."""
    p = predict_recovery_probability(sample_soft_liquidity_record)
    assert isinstance(p, float)
    assert 0.0 <= p <= 1.0
    assert p > 0.05  # Soft liquidity should have non-trivial recovery probability


def test_anti_leakage_boundary_rejects_ground_truth():
    """
    Anti-Leakage Invariant:
    Any input dict containing 'ground_truth_recoverable' must be immediately rejected with ValueError.
    """
    leaky_input = {
        "case_id": "leak_001",
        "mandate_id": "man_leak",
        "merchant_id": "mer_001",
        "customer_id": "cust_001",
        "rail": "UPI_AUTOPAY",
        "amount_inr": Decimal("500.00"),
        "attempt_count": 1,
        "failure_code": "Z9",
        "failure_class": "SOFT_LIQUIDITY",
        "failure_timestamp": datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
        "channel_consent": {"WHATSAPP": "OPTED_IN"},
        "ground_truth_recoverable": True,  # FORBIDDEN LEAKAGE FIELD
    }
    with pytest.raises(ValueError, match="Anti-leakage violation"):
        predict_recovery_probability(leaky_input)


def test_pci_dss_banned_fields_rejected():
    """
    PCI-DSS & Privacy Invariant:
    Input containing raw PAN, CVV, or card/account identifiers must be rejected.
    """
    prohibited_input = {
        "case_id": "pci_001",
        "mandate_id": "man_pci",
        "merchant_id": "mer_001",
        "customer_id": "cust_001",
        "rail": "UPI_AUTOPAY",
        "amount_inr": Decimal("500.00"),
        "attempt_count": 1,
        "failure_code": "Z9",
        "failure_class": "SOFT_LIQUIDITY",
        "failure_timestamp": datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
        "channel_consent": {},
        "pan": "4111111111111111",  # FORBIDDEN RAW PAN
    }
    with pytest.raises(ValueError, match="PCI-DSS / Privacy violation"):
        predict_recovery_probability(prohibited_input)


def test_legal_hold_structural_sanity_near_zero(sample_legal_hold_record):
    """
    Structural Sanity Check:
    A LEGAL_HOLD case must receive predicted recovery probability < 0.05.
    """
    p = predict_recovery_probability(sample_legal_hold_record)
    assert p < 0.05, f"Expected LEGAL_HOLD P < 0.05, got {p:.4f}"


def test_inference_determinism(sample_soft_liquidity_record):
    """
    Determinism Invariant:
    Multiple calls on identical inputs yield identical floating point values.
    """
    p1 = predict_recovery_probability(sample_soft_liquidity_record)
    p2 = predict_recovery_probability(sample_soft_liquidity_record)
    assert p1 == p2


def test_missing_optional_fields_handled_gracefully():
    """Model handles records with minimal optional fields (no last attempt, empty consent)."""
    minimal_record = MandateStateRecord(
        case_id="min_001",
        mandate_id="man_min",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("1000.00"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc),
        last_attempt_timestamp=None,
        channel_consent={},
    )
    p = predict_recovery_probability(minimal_record)
    assert 0.0 <= p <= 1.0
