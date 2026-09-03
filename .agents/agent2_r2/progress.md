# Progress Log - Agent 2 (R2: Guardrails & Decision Engine)

Last visited: 2026-09-02T18:45:00Z

## Completed Work
1. **Default Static Multiplier Lift-EV Path**:
   - Modified `src/decision/optimizer.py` to set `use_uplift: bool = False` as default in `optimize_decision`.
   - Updated audit rationale to label `"via static multiplier"` when static path is active.
2. **Opt-In CATE Uplift Path & Dedicated Adversarial Tests**:
   - Removed `and custom_costs is None and custom_multipliers is None` from `use_learned_cate` in `src/decision/optimizer.py` so that `custom_costs` applies to CATE EV calculations without disabling CATE modeling.
   - Added `test_cate_adversarial_hostile_digital_costs`, `test_cate_adversarial_channel_cost_steering`, and `test_cate_opt_in_explicit_toggle` in `tests/unit/test_decision_optimizer.py`.
3. **Structural Safety Invariants (LEGAL_HOLD & Unknown Codes)**:
   - Updated early mandatory compliance routing gate (step 0 in `optimize_decision`) to check both `state.failure_class == FailureClass.LEGAL_HOLD` and `requires_mandatory_escalation(state.failure_code)`.
   - Guaranteed that zero `LEGAL_HOLD` or unknown code cases ever receive non-null `p_hat` or `lift_ev_inr`.
   - Updated `src/guardrails/legal_hold_filter.py` to reference `CODE_TO_FAILURE_CLASS` and `LEGAL_HOLD_CODES` from `src.core.taxonomy` and normalize input codes (`strip().upper()`).
4. **Property-Based Compliance Testing**:
   - Added parameterized property tests over `LEGAL_HOLD_CODES`, all known non-legal codes in `KNOWN_CODES`, and malformed/unknown codes in `test_decision_optimizer.py`, `test_legal_hold_filter.py`, and `test_compliance_invariants.py`.
   - Full batch invariant tests dynamically compute expected mandatory vs non-mandatory counts rather than relying solely on brittle constants.
5. **Test Verification**:
   - Full test suite: `PYTHONPATH=. .venv/bin/pytest tests/` -> 159 passed, 0 failed in 37.35s.
   - Decision & Guardrail suite: `PYTHONPATH=. .venv/bin/pytest tests/unit/test_decision_optimizer.py tests/unit/test_legal_hold_filter.py ...` -> 94 passed, 0 failed.
