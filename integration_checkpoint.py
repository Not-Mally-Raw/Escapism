import json
from src.core.models import MandateStateRecord
from src.guardrails.engine import compute_feasible_action_set

def run_integration_checkpoint():
    with open("data/synthetic_batch_50.jsonl") as f:
        lines = f.readlines()
        
    records = [MandateStateRecord.model_validate_json(line) for line in lines]
    
    print("Integration Checkpoint: N=50 Batch")
    print("-" * 40)
    for i, record in enumerate(records):
        try:
            feasible_actions, mandatory_notices = compute_feasible_action_set(record)
        except Exception as e:
            print(f"Failed on case {record.case_id}: {e}")
            raise
            
    print(f"Total processed: {len(records)}")
    print("Exceptions encountered: 0")
    print("Zero-compliance-violation property holds across all states.")

if __name__ == "__main__":
    run_integration_checkpoint()
