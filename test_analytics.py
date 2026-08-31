import json
from collections import Counter
from pathlib import Path
from src.core.models import MandateStateRecord
from src.decision.optimizer import optimize_decision

batch_file = Path("data/synthetic_batch_5000.jsonl")
action_counts = Counter()
abort_rate = 0
with open(batch_file, "r") as f:
    for line in f:
        raw_record = json.loads(line)
        state = MandateStateRecord(**raw_record["state"])
        res = optimize_decision(state)
        action_counts[res.selected_action.value] += 1
        if res.selected_action.value == 'ABORT_COMPLIANT':
            abort_rate += 1

print(action_counts)
print(abort_rate)
