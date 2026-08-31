import json
from pathlib import Path
from collections import Counter
from decimal import Decimal
from src.orchestration.engine import process_failure_event
from src.core.types import ActionType, FailureClass
from src.diagnosis.models import DiagnosticOutput

def main():
    batch_file = Path("data/synthetic_batch_5000.jsonl")
    
    action_counts = Counter()
    
    with open(batch_file, "r") as f:
        for line in f:
            raw_record = json.loads(line)
            raw_event = raw_record["state"]
            expected_class = raw_event["failure_class"]
            
            raw_event["raw_error_text"] = "dummy text to trigger LLM"
            
            def mock_llm(code: str, text: str) -> DiagnosticOutput:
                return DiagnosticOutput(
                    failure_class=FailureClass(expected_class),
                    confidence=0.9,
                    evidence=["Mocked"]
                )
            
            res = process_failure_event(raw_event, llm_callable=mock_llm)
            action_counts[res.decision.selected_action.value] += 1
            
    print("Action Distribution:", action_counts)

if __name__ == "__main__":
    main()
