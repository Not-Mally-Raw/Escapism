import re

with open('src/guardrails/engine.py', 'r') as f:
    code = f.read()

patch = """    # 5. Apply RBI ₹15,000 AFA Threshold Guardrail
    # Citing: rbi_npci_regulations.md §2.2 — Amount > ₹15,000 masks out SILENT_RETRY
    if not is_silent_retry_permitted(state.amount_inr):
        primary_actions.discard(ActionType.SILENT_RETRY)

    # 5b. Apply Pre-Debit Notice Gate (Instruction 2)
    # Citing: rbi_npci_regulations.md §2.3 — Retries are NOT in feasible set until notice sent >=24h prior.
    if not state.pre_debit_notice_sent:
        primary_actions.discard(ActionType.SILENT_RETRY)
        primary_actions.discard(ActionType.PIN_PROMPTED_RETRY)
"""

code = code.replace(
"""    # 5. Apply RBI ₹15,000 AFA Threshold Guardrail
    # Citing: rbi_npci_regulations.md §2.2 — Amount > ₹15,000 masks out SILENT_RETRY
    if not is_silent_retry_permitted(state.amount_inr):
        primary_actions.discard(ActionType.SILENT_RETRY)""",
patch
)

with open('src/guardrails/engine.py', 'w') as f:
    f.write(code)
