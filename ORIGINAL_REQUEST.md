# Original User Request

## 2026-09-02T18:27:31Z

Stabilize, repair, and harden the Razorpay Revenue Recovery Engine across event boundary normalization, deterministic decision optimization, unconfounded causal simulation, model lineage synchronization, and replay-safe execution.

Working directory: /Users/spandankewte/Downloads/razorpay-revenue-recovery
Integrity mode: development

---

## Multi-Agent Ownership Boundaries & Sequencing

To prevent merge collisions and silent assumption overwrites, tasks must be executed under strict ownership:

1. **Agent 1 (Event Boundary & Ingestion)**:
   - Owns: `src/ingestion/`, webhook fixtures, initial worker event parsing in `src/execution/worker.py`.
2. **Agent 2 (Guardrails & Decision Engine)**:
   - Owns: `src/decision/`, `src/guardrails/`, `tests/unit/test_decision_optimizer.py`.
3. **Agent 3 (Causal Simulation & ML Lineage)**:
   - Owns: `src/simulation/`, `src/ml/`, `scripts/run_monte_carlo.py`, `data/`, model artifacts, and model cards.
4. **Agent 4 (Execution Reliability & Packaging)**:
   - Owns: `src/execution/razorpay_client.py`, worker retry/DLQ mechanics, `pyproject.toml`, `requirements.txt`, documentation.
5. **Integration Lead (Final Phase)**:
   - Sequence: Agents 1–4 complete work in worktrees/branches; Integration Lead verifies merged contracts, runs full `pytest`, benchmarks, and validates end-to-end flow.

---

## Requirements

### R1. Fixture-Driven Event Ingestion Boundary & Worker Normalization
- Create a checked-in, sanitized Razorpay webhook fixture representing `mandate.debit.failed` (covering exact JSON envelope nesting, IDs, amount in paise vs INR, bank error fields, and timestamps).
- Build a typed event adapter that parses this fixture, rejecting ambiguous or malformed payloads fail-closed.
- Execute failure diagnosis (`diagnose_failure`) on the raw bank code and error description *before* constructing the internal domain object (`MandateStateRecord`).
- Update `worker.py` to ingest canonical parsed events from SQLite `inbox` rather than assuming a test-shaped `{"state": {...}}` wrapper.

### R2. Deterministic Decision Engine & Tested Safety Invariants
- Default `use_uplift` to `False` in `optimize_decision`, establishing the pre-registered static multiplier Lift-EV path as the certified production default.
- Treat CATE / T-Learner uplift as an explicit opt-in (`use_uplift=True`), activated only if held-out policy evaluation demonstrates non-inferiority to the static policy.
- Provide dedicated adversarial tests for the CATE path rather than allowing `custom_costs` to silently disable it.
- Enforce the structural safety invariant: `LEGAL_HOLD` and unknown codes must bypass EV/CATE scoring entirely and route to `ESCALATE_HUMAN`.
- Test compliance invariants property-wise (assert every unknown code escalates; assert every `07` and `AP03` escalates; assert known non-legal codes do not escalate merely due to lookup failure) rather than relying solely on hardcoded batch constants.

### R3. Rigorous Causal Data Generation & Model Lineage
- Explicitly define the synthetic data generation contract in `src/simulation/batch_generator.py`:
  - `potential_outcome_noop = Bernoulli(mu_0(state))`
  - `potential_outcome[action] = Bernoulli(clip(mu_0(state) + tau(state, action), 0, 1))`
  - `observed_outcome = potential_outcome[observed_action]`
  - `ground_truth_recoverable = potential_outcome_noop`
- Enforce common support and positivity: ensure logged propensity has an explicit floor (e.g. $\pi(a \mid S) \ge 0.05$ where action $ is eligible) to prevent IPS explosion.
- Re-train the baseline recovery propensity model (`train.py`) against unconfounded baseline outcomes.
- Reconcile `train.py` assertion message and threshold consistency (align the `< 0.15` vs `< 0.05` discrepancy).
- Synchronize dataset SHA256 hashes, artifact hashes, hyperparameters, and slice metrics between `src/ml/models/metadata.json` and `docs/models/recovery_propensity_model_card.md`.

### R4. Replay-Safe Execution & Durable Reconciliation
- Implement replay-safe dispatch in `worker.py`: record an explicit execution intent in SQLite before dispatching external API calls.
- Enforce idempotency keys (`x-razorpay-event-id`) across retries to prevent duplicate gateway operations.
- Support deterministic outcome reconciliation for interrupted executions.
- Implement bounded exponential backoff retries with clean transitions to a `DEAD_LETTER` state upon terminal failures.
- Expand `audit_log` records to durably store: raw event ID, diagnostic output, feasible action set, candidate scores, model version hash, and gateway receipt.

### R5. Dependency Packaging & Honest System Boundaries
- Populate `pyproject.toml` and `requirements.txt` with all genuine runtime dependencies (`fastapi`, `uvicorn`, `aiosqlite`, `streamlit`, `plotly`, `scikit-learn`, `pydantic`).
- Clearly document system boundaries: state transparently that `razorpay_client.py` defaults to mock execution and that omnichannel notifications dispatch webhook intents.

---

## Acceptance Criteria

### Ingestion & Worker Contract
- [ ] Checked-in Razorpay webhook fixture parses cleanly into canonical internal events without Pydantic validation errors.
- [ ] Payloads with missing mandatory fields or invalid signatures fail-closed and log structured errors.
- [ ] `diagnose_failure()` executes upstream of `MandateStateRecord` instantiation.

### Compliance & Decision Safety
- [ ] Property-based compliance checks verify:
  - 100% of unknown/malformed codes escalate to `ESCALATE_HUMAN`.
  - 100% of `07` and `AP03` codes escalate to `ESCALATE_HUMAN`.
  - Zero `LEGAL_HOLD` cases ever receive non-null `p_hat` or `lift_ev_inr`.
- [ ] Full `pytest tests/unit/test_decision_optimizer.py` passes with zero failures on the default static path.
- [ ] Dedicated adversarial tests verify CATE behavior under hostile cost tables when `use_uplift=True`.

### Causal Data & ML Provenance
- [ ] Synthetic batch generator produces complete potential outcome vectors (`potential_outcome_noop`, `potential_outcome[action]`) and logged propensities satisfying positivity ($\pi(a \mid S) \ge 0.05$).
- [ ] Model metadata JSON matches `recovery_propensity_model_card.md` across data SHA256, model SHA256, feature count, and held-out slice metrics.
- [ ] `scripts/run_monte_carlo.py` executes end-to-end without feature-mismatch errors using self-normalized or doubly-robust policy evaluation.

### Execution Reliability & Packaging
- [ ] Worker re-dispatch with identical event ID reuses existing intent without generating duplicate external calls.
- [ ] Terminal failure scenarios transition to `DEAD_LETTER` after configured retry limits.
- [ ] Clean installation via `pip install -e .` succeeds in a fresh virtualenv, running both tests and the Streamlit dashboard without missing-module errors.
