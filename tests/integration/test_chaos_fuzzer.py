import pytest
from pydantic import ValidationError
from datetime import datetime, timezone
from src.core.types import PaymentRail
from src.orchestration.engine import process_failure_event

def test_chaos_fuzzer_negative_amount():
    raw_event = {
        "case_id": "case_12345",
        "mandate_id": "mandate_9876",
        "merchant_id": "mer_xyz",
        "customer_id": "cust_abc",
        "rail": PaymentRail.UPI_AUTOPAY.value,
        "amount_inr": "-500.00",
        "attempt_count": 1,
        "failure_code": "U19",
        "failure_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    with pytest.raises(ValidationError) as exc_info:
        process_failure_event(raw_event)
    
    assert "amount_inr" in str(exc_info.value)
    assert "Input should be greater than 0" in str(exc_info.value)

def test_chaos_fuzzer_insane_attempt_count():
    raw_event = {
        "case_id": "case_12345",
        "mandate_id": "mandate_9876",
        "merchant_id": "mer_xyz",
        "customer_id": "cust_abc",
        "rail": PaymentRail.UPI_AUTOPAY.value,
        "amount_inr": "500.00",
        "attempt_count": 9999,
        "failure_code": "U19",
        "failure_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    with pytest.raises(ValidationError) as exc_info:
        process_failure_event(raw_event)
        
    assert "attempt_count" in str(exc_info.value)
    assert "Input should be less than or equal to 4" in str(exc_info.value)

def test_chaos_fuzzer_missing_mandatory_fields():
    raw_event = {
        "amount_inr": "500.00",
        "failure_code": "U19",
        # Missing case_id, mandate_id, rail, attempt_count, etc.
    }
    
    with pytest.raises(ValidationError) as exc_info:
        process_failure_event(raw_event)
        
    errors = str(exc_info.value)
    assert "case_id" in errors
    assert "mandate_id" in errors
    assert "rail" in errors
