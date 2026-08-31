import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.models import MandateStateRecord
from src.core.types import ActionType
from src.decision.optimizer import optimize_decision
from src.ml.inference import predict_recovery_probability

def main():
    cases = []
    with open("data/synthetic_batch_5000.jsonl") as f:
        for line in f:
            data = json.loads(line)
            cases.append(MandateStateRecord(**data.get("state", data)))

    # Find cases
    soft_liq = None
    legal_hold = None
    afa_masked = None
    abort_comp = None

    for state in cases:
        dec = optimize_decision(state)
        
        if not soft_liq and state.failure_class == "SOFT_LIQUIDITY" and dec.selected_action in [ActionType.WHATSAPP_NUDGE, ActionType.PAYMENT_LINK]:
            soft_liq = (state, dec)
            
        if not legal_hold and state.failure_class == "LEGAL_HOLD" and dec.selected_action == ActionType.ESCALATE_HUMAN:
            legal_hold = (state, dec)
            
        if not afa_masked and state.afa_required and dec.selected_action != ActionType.SILENT_RETRY and state.failure_class == "SOFT_LIQUIDITY":
            afa_masked = (state, dec)
            
        if not abort_comp and dec.selected_action == ActionType.ABORT_COMPLIANT:
            abort_comp = (state, dec)
            
    print("# Recovery Playbook: AI Orchestrator Examples\n")
    
    for title, tup in [
        ("Case 1: SOFT_LIQUIDITY Success (Digital Channel Lift)", soft_liq),
        ("Case 2: LEGAL_HOLD (Mandatory Escalation)", legal_hold),
        ("Case 3: AFA-Gated (SILENT_RETRY properly masked)", afa_masked),
        ("Case 4: ABORT_COMPLIANT (Expected Value too low)", abort_comp)
    ]:
        if not tup: continue
        state, dec = tup
        print(f"## {title}")
        print(f"**Case ID:** `{state.case_id}` | **Amount:** ₹{state.amount_inr} | **Class:** `{state.failure_class}`")
        print(f"- **P̂(S) Base Recovery:** {float(dec.p_hat if dec.p_hat else 0.0):.4f}")
        print(f"- **Selected Action:** `{dec.selected_action.value}`")
        if dec.lift_ev_inr is not None:
            print(f"- **Lift-EV Calculation:** ₹{float(dec.lift_ev_inr):.2f} (Cost: ₹{float(dec.cost_inr):.2f})")
        print(f"- **System Rationale:** {dec.audit_step.rationale}\n")

if __name__ == "__main__":
    main()
