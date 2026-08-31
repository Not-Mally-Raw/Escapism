from src.orchestration.models import RawFailureEvent
from src.core.models import MandateStateRecord

raw_event = {
    "case_id": "c1", "mandate_id": "m1", "merchant_id": "mer1", "customer_id": "cust1",
    "rail": "UPI_AUTOPAY", "amount_inr": "500", "attempt_count": 1, "failure_code": "01",
    "failure_class": "HARD_TERMINAL", "failure_timestamp": "2026-08-15T16:59:59+05:30",
    "channel_consent": {"WHATSAPP": "OPTED_IN"}
}

event = RawFailureEvent(**raw_event)
print("Raw event consent:", event.channel_consent)

state1 = MandateStateRecord(**raw_event)
print("State1 consent:", state1.channel_consent)

state2 = MandateStateRecord(
    case_id=event.case_id, mandate_id=event.mandate_id, merchant_id=event.merchant_id,
    customer_id=event.customer_id, rail=event.rail, amount_inr=event.amount_inr,
    attempt_count=event.attempt_count, failure_code=event.failure_code,
    failure_class="HARD_TERMINAL", failure_timestamp=event.failure_timestamp,
    channel_consent=event.channel_consent
)
print("State2 consent:", state2.channel_consent)
