# Handoff Report: Milestone 2 (R2) Guardrails & Decision Engine

**Agent**: Agent 2 (Guardrails & Decision Engine)  
**Working Directory**: `/Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent2_r2`  
**Timestamp**: 2026-09-02T18:45:00Z  
**Target Milestone**: M2 (R2) — Deterministic Decision Engine & Tested Safety Invariants  

---

## 1. Observation

1. **Default `use_uplift` configuration**:
   In `src/decision/optimizer.py`, `optimize_decision` previously had parameter `use_uplift: bool = True` (line 86). Under this setting, inference attempted to use CATE uplift modeling even when running routine production evaluations, causing test failures on calibrated static thresholds when CATE predicted different channel rankings.
   Verbatim failure before fix:
   ```
   FAILED tests/unit/test_decision_optimizer.py::test_low_amount_subscription_clears_calibrated_threshold
   AssertionError: assert <ActionType.PIN_PROMPTED_RETRY> == <ActionType.WHATSAPP_NUDGE>
   ```

2. **CATE Path Masking via `custom_costs`**:
   In `src/decision/optimizer.py` line 200, `use_learned_cate` was guarded with `and custom_costs is None and custom_multipliers is None`. Passing custom cost dictionaries silently bypassed CATE calculations and forced static multiplier calculations.

3. **Structural Safety Invariant for `LEGAL_HOLD` and Unknown Codes**:
   In `src/decision/optimizer.py`, the early mandatory compliance routing gate (lines 121–141) checked `if state.failure_class == FailureClass.LEGAL_HOLD:`, but did not check `requires_mandatory_escalation(state.failure_code)`. Unknown failure codes had to fall through to `compute_feasible_action_set`.
   In `src/guardrails/legal_hold_filter.py`, `KNOWN_CODES` was an independently maintained set rather than referencing `CODE_TO_FAILURE_CLASS` and `LEGAL_HOLD_CODES` from `src.core.taxonomy`. Input codes were not stripped or upper-cased prior to set containment check.

4. **Hardcoded Batch Constants in Tests**:
   In `tests/unit/test_decision_optimizer.py`, adversarial tests asserted hardcoded constants (`4655` aborts, `345` escalations) based on an older dataset revision, whereas `data/synthetic_batch_5000.jsonl` contains 373 mandatory escalation records (100 legal hold + 273 unknown/malformed codes) and 4627 non-mandatory records.

5. **Test Execution Verification**:
   Running `PYTHONPATH=. .venv/bin/pytest tests/` executes 159 tests with 100% pass rate.
   Running `PYTHONPATH=. .venv/bin/pytest tests/unit/test_decision_optimizer.py tests/unit/test_legal_hold_filter.py tests/integration/test_compliance_invariants.py` executes 69 tests with 100% pass rate.

---

## 2. Logic Chain

1. **Production Static Lift-EV Baseline**:
   - Setting `use_uplift: bool = False` as the default in `optimize_decision` (Observation 1) satisfies Requirement 1, establishing the pre-registered static multiplier formula $\text{Lift-EV}(a \mid S) = (\hat{P}(S) \cdot m(a) - \hat{P}(S) \cdot m(\text{noop})) \cdot \text{Amount} - C(a)$ as the certified production default.

2. **Explicit CATE Opt-In with Adversarial Robustness**:
   - Removing the `custom_costs is None` precondition from `use_learned_cate` (Observation 2) allows `optimize_decision(state, custom_costs=..., use_uplift=True)` to execute CATE uplift evaluation $\Delta P = \hat{\tau}(S, a)$ while accurately subtracting custom action costs $C(a)$.
   - Adding dedicated tests (`test_cate_adversarial_hostile_digital_costs`, `test_cate_adversarial_channel_cost_steering`, and `test_cate_opt_in_explicit_toggle`) verifies CATE behavior under hostile cost structures without regression.

3. **Guaranteed Structural Safety Isolation**:
   - Integrating `requires_mandatory_escalation(state.failure_code)` directly into the early routing gate of `optimize_decision` (Observation 3) ensures that all `LEGAL_HOLD` and unrecognized/malformed codes route to `ESCALATE_HUMAN` prior to any feature extraction, recovery propensity scoring, or CATE inference.
   - For all such cases, `DecisionResult` returns `is_mandatory_routing=True`, `p_hat=None`, `lift_ev_inr=None`, and `candidate_scores=[]`.

4. **Property-Based Compliance Verification**:
   - Refactoring `requires_mandatory_escalation` to import canonical constants from `src.core.taxonomy` and normalize strings ensures robust fail-closed handling for empty, whitespace, lowercase, and unknown codes.
   - Adding parameterized property tests across all legal hold codes, all known non-legal codes, and malformed strings (Observation 4 & 5) guarantees invariant compliance property-wise across the full state space.

---

## 3. Caveats

- No caveats. All changes strictly adhere to the minimal change principle and respect the project boundaries defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

---

## 4. Conclusion

Milestone 2 (R2) requirements are completely implemented and verified:
1. Default `use_uplift=False` in `optimize_decision` establishes the certified static multiplier Lift-EV path.
2. CATE uplift modeling operates as an explicit opt-in (`use_uplift=True`).
3. Dedicated adversarial tests for CATE under hostile and steered costs pass 100%.
4. Structural safety invariant is enforced: 100% of `LEGAL_HOLD` and unknown codes bypass scoring and route to `ESCALATE_HUMAN` with null `p_hat` and null `lift_ev_inr`.
5. Property-based compliance testing verifies invariants across all taxonomy codes and batch records.
6. 100% of decision optimizer, legal hold, and compliance tests pass (159/159 in repository).

---

## 5. Verification Method

To independently verify this implementation:

```bash
# 1. Run all unit tests for the decision optimizer and guardrails
PYTHONPATH=. .venv/bin/pytest tests/unit/test_decision_optimizer.py tests/unit/test_legal_hold_filter.py tests/integration/test_compliance_invariants.py -v

# 2. Run the complete test suite across all modules
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

### Invalidation Conditions
- Any `LEGAL_HOLD` case receiving non-null `p_hat` or `lift_ev_inr`.
- `optimize_decision` defaulting `use_uplift` to `True`.
- `requires_mandatory_escalation` failing to escalate an unknown error code.
- Any test failure in `tests/unit/test_decision_optimizer.py`.
