## 2026-09-02T18:29:36Z
You are Agent 2 (Guardrails & Decision Engine) for Milestone 2 (R2).
Your working directory is: /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent2_r2

Read the authoritative requirements and project documents:
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/ORIGINAL_REQUEST.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. An auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Ownership Boundaries:
- Owns: `src/decision/`, `src/guardrails/`, `tests/unit/test_decision_optimizer.py`, and related decision/guardrail tests.

Requirements (R2):
1. Default `use_uplift` to `False` in `optimize_decision`, establishing the pre-registered static multiplier Lift-EV path as the certified production default.
2. Treat CATE / T-Learner uplift as an explicit opt-in (`use_uplift=True`), activated only if held-out policy evaluation demonstrates non-inferiority to the static policy.
3. Provide dedicated adversarial tests for the CATE path rather than allowing `custom_costs` to silently disable it.
4. Enforce the structural safety invariant: `LEGAL_HOLD` and unknown codes must bypass EV/CATE scoring entirely and route to `ESCALATE_HUMAN`. Zero `LEGAL_HOLD` cases ever receive non-null `p_hat` or `lift_ev_inr`.
5. Test compliance invariants property-wise (assert every unknown code escalates; assert every `07` and `AP03` escalates; assert known non-legal codes do not escalate merely due to lookup failure) rather than relying solely on hardcoded batch constants.
6. Ensure `pytest tests/unit/test_decision_optimizer.py` and all guardrail tests pass with 100% success.

Deliverables:
- Maintain `.agents/agent2_r2/progress.md` with progress and test verification commands/outputs.
- Deliver full report to `.agents/agent2_r2/handoff.md`.
- Send completion message with summary when finished.
