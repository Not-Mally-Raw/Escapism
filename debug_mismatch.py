import json
from pathlib import Path
from src.core.models import MandateStateRecord
from src.decision.optimizer import optimize_decision
from src.orchestration.engine import process_failure_event
from src.core.types import FailureClass
from src.diagnosis.models import DiagnosticOutput

batch_file = Path("data/synthetic_batch_5000.jsonl")

mismatch_count = 0
with open(batch_file, "r") as f:
    for line in f:
        raw_record = json.loads(line)
        
        # Original standalone track 3
        state1 = MandateStateRecord(**raw_record["state"])
        res1 = optimize_decision(state1)
        
        # New orchestration E2E
        raw_event = dict(raw_record["state"])
        expected_class = raw_event["failure_class"]
        raw_event["raw_error_text"] = "dummy text to trigger LLM"
        
        def mock_llm(code: str, text: str) -> DiagnosticOutput:
            return DiagnosticOutput(
                failure_class=FailureClass(expected_class),
                confidence=0.9,
                evidence=["Mocked"]
            )
            
        res2 = process_failure_event(raw_event, llm_callable=mock_llm)
        
        if res1.selected_action != res2.decision.selected_action:
            print("MISMATCH FOUND!")
            print(f"Standalone action: {res1.selected_action}")
            print(f"E2E action: {res2.decision.selected_action}")
            print(f"Standalone state: {state1.model_dump()}")
            
            # Let's see what state process_failure_event constructed
            # Wait, process_failure_event doesn't return the state, but we can reconstruct it
            from src.orchestration.models import RawFailureEvent
            event = RawFailureEvent(**raw_event)
            diagnostic = mock_llm(event.failure_code, "dummy")
            state2 = MandateStateRecord(
                case_id=event.case_id, mandate_id=event.mandate_id, merchant_id=event.merchant_id,
                customer_id=event.customer_id, rail=event.rail, amount_inr=event.amount_inr,
                attempt_count=event.attempt_count, failure_code=event.failure_code,
                failure_class=diagnostic.failure_class, failure_timestamp=event.failure_timestamp,
                afa_required=event.afa_required, pre_debit_notice_sent=event.pre_debit_notice_sent,
                customer_timezone=event.customer_timezone, channel_consent=event.channel_consent
            )
            print(f"E2E constructed state: {state2.model_dump()}")
            break

