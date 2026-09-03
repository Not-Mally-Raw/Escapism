import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.core.models import MandateStateRecord
from src.core.types import ActionType, FailureClass
from src.decision.optimizer import COST_TABLE, optimize_decision
from src.ml.uplift import NOOP_ACTION, UPLIFT_ACTIONS, uplift_model_available


DATA_PATH = Path("data/causal_batch_5000.jsonl")


def load_logged_data(filepath: Path = DATA_PATH):
    if not filepath.exists():
        raise FileNotFoundError(
            f"{filepath} not found. Run `python src/simulation/batch_generator.py` "
            "and `python -m src.ml.uplift` before this benchmark."
        )
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            row["state"] = MandateStateRecord(**row["state"])
            records.append(row)
    return records


def _as_logged_action(action: ActionType) -> str:
    if action in (ActionType.ABORT_COMPLIANT, ActionType.ESCALATE_HUMAN):
        return NOOP_ACTION
    return action.value if action.value in UPLIFT_ACTIONS else NOOP_ACTION


def policy_noop(state: MandateStateRecord) -> str:
    return NOOP_ACTION


def policy_blind_retry(state: MandateStateRecord) -> str:
    return ActionType.SILENT_RETRY.value


def policy_ai_orchestrator(state: MandateStateRecord) -> str:
    return _as_logged_action(optimize_decision(state).selected_action)


def estimate_policy_value(records, policy_fn, num_bootstrap: int = 500, seed: int = 42):
    """
    Self-normalized inverse propensity scoring (SNIPS).
    Uses observed logged outcomes, not model-predicted probabilities, to avoid
    the self-referential Monte Carlo flaw.
    """
    rng = np.random.default_rng(seed)
    n = len(records)

    # Precompute per-record terms once across the dataset to avoid re-evaluating policy_fn in bootstrap loop
    precomputed = []
    for row in records:
        state: MandateStateRecord = row["state"]
        logged_action = row["observed_action"]
        chosen_action = policy_fn(state)
        segment = state.failure_class.value

        is_match = (chosen_action == logged_action)
        if not is_match:
            precomputed.append({
                "match": False,
                "weight": 0.0,
                "value": 0.0,
                "cost": 0.0,
                "fine": 0.0,
                "segment": segment,
            })
            continue

        propensity = max(float(row["propensity"]), 0.05)
        weight = 1.0 / propensity
        gross = float(bool(row["observed_outcome"])) * float(state.amount_inr)
        cost = float(COST_TABLE.get(ActionType(chosen_action), 0.0)) if chosen_action != NOOP_ACTION else 0.0

        fine = 0.0
        if chosen_action == ActionType.SILENT_RETRY.value and state.failure_class in (
            FailureClass.HARD_TERMINAL,
            FailureClass.LEGAL_HOLD,
        ):
            fine = 500.0

        value = gross - cost - fine
        precomputed.append({
            "match": True,
            "weight": weight,
            "value": value,
            "cost": cost,
            "fine": fine,
            "segment": segment,
        })

    def estimate(indices):
        weighted_value = 0.0
        weight_sum = 0.0
        matched = 0
        illegal_fines = 0.0
        action_costs = 0.0
        by_segment = {}

        for idx in indices:
            item = precomputed[int(idx)]
            segment = item["segment"]
            by_segment.setdefault(segment, {"value": 0.0, "weight": 0.0, "matches": 0})

            if not item["match"]:
                continue

            w = item["weight"]
            v = item["value"]
            f = item["fine"]
            c = item["cost"]

            weighted_value += w * v
            weight_sum += w
            matched += 1
            illegal_fines += f * w
            action_costs += c * w
            by_segment[segment]["value"] += w * v
            by_segment[segment]["weight"] += w
            by_segment[segment]["matches"] += 1

        estimate_per_case = weighted_value / weight_sum if weight_sum else 0.0
        total_value = estimate_per_case * n
        segment_values = {
            segment: (vals["value"] / vals["weight"] * n if vals["weight"] else 0.0)
            for segment, vals in by_segment.items()
        }
        return total_value, matched, illegal_fines, action_costs, segment_values

    point, matched, illegal_fines, action_costs, segment_values = estimate(np.arange(n))
    boot = []
    for _ in range(num_bootstrap):
        boot_indices = rng.integers(0, n, size=n)
        boot.append(estimate(boot_indices)[0])
    ci_low, ci_high = np.percentile(boot, [2.5, 97.5])
    return {
        "mean_nrr": point,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "matched": matched,
        "match_rate": matched / n,
        "illegal_fines_weighted": illegal_fines,
        "action_costs_weighted": action_costs,
        "segment_values": segment_values,
    }


def run_evaluation(records):
    policies = [
        ("Policy 1: Do Nothing (NOOP)", policy_noop),
        ("Policy 2: Blind Retry", policy_blind_retry),
        ("Policy 3: AI Orchestrator", policy_ai_orchestrator),
    ]
    results = []
    segment_rows = []
    for name, fn in policies:
        res = estimate_policy_value(records, fn)
        results.append(
            {
                "Policy": name,
                "SNIPS NRR (₹)": res["mean_nrr"],
                "95% CI (₹)": f"[{res['ci_low']:,.0f}, {res['ci_high']:,.0f}]",
                "Logged Match Rate": f"{res['match_rate']:.1%}",
            }
        )
        for segment, value in res["segment_values"].items():
            segment_rows.append({"Policy": name, "failure_class": segment, "SNIPS NRR (₹)": value})
    return pd.DataFrame(results), pd.DataFrame(segment_rows)


if __name__ == "__main__":
    records = load_logged_data()
    print("=================================================================================================")
    print("        OFFLINE POLICY EVALUATION: LOGGED OUTCOMES + INVERSE PROPENSITY SCORING")
    print("=================================================================================================")
    print("Method: Self-normalized IPS over epsilon-greedy synthetic logged data.")
    print("Important: this uses observed logged outcomes, not the optimizer's own predicted probability.")
    print("Uplift artifact present:", uplift_model_available())
    print("Fine model: 🔴 illustrative placeholder (₹500 for illegal blind retry on terminal/legal cases).")
    print("-------------------------------------------------------------------------------------------------")
    metrics, segments = run_evaluation(records)
    print(metrics.to_string(index=False, float_format="{:,.2f}".format))
    print("=================================================================================================\n")
    print("Segment-level SNIPS estimates")
    if not segments.empty:
        pivot = segments.pivot_table(index="failure_class", columns="Policy", values="SNIPS NRR (₹)", aggfunc="sum")
        print(pivot.to_string(float_format=lambda x: f"₹{x:,.0f}"))
    print("=================================================================================================")
