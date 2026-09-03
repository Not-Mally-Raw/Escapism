## 2026-09-02T18:30:00Z

<USER_REQUEST>
You are Agent 3 (Causal Simulation & ML Lineage) for Milestone 3 (R3).
Your working directory is: /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent3_r3

Read the authoritative requirements and project documents:
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/ORIGINAL_REQUEST.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. An auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Ownership Boundaries:
- Owns: src/simulation/, src/ml/, scripts/run_monte_carlo.py, data/, model artifacts, and model cards (docs/models/).

Requirements (R3):
1. Explicitly define the synthetic data generation contract in src/simulation/batch_generator.py:
   - potential_outcome_noop = Bernoulli(mu_0(state))
   - potential_outcome[action] = Bernoulli(clip(mu_0(state) + tau(state, action), 0, 1))
   - observed_outcome = potential_outcome[observed_action]
   - ground_truth_recoverable = potential_outcome_noop
2. Enforce common support and positivity: ensure logged propensity has an explicit floor (e.g. pi(a | S) >= 0.05 where action is eligible) to prevent IPS explosion.
3. Re-train the baseline recovery propensity model (src/ml/train.py or equivalent) against unconfounded baseline outcomes.
4. Reconcile train.py assertion message and threshold consistency (align < 0.15 vs < 0.05 discrepancy).
5. Synchronize dataset SHA256 hashes, artifact hashes, hyperparameters, and slice metrics between src/ml/models/metadata.json and docs/models/recovery_propensity_model_card.md.
6. Ensure scripts/run_monte_carlo.py and all simulation/ml tests execute end-to-end cleanly.

Deliverables:
- Maintain .agents/agent3_r3/progress.md with progress and test verification commands/outputs.
- Deliver full report to .agents/agent3_r3/handoff.md.
- Send completion message with summary when finished.
</USER_REQUEST>
