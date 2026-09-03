# Progress — Agent 3 (Causal Simulation & ML Lineage - R3)
Last visited: 2026-09-02T18:38:30Z

## Status: COMPLETE

### 1. Synthetic Causal Generation Contract (R3.1 & R3.2)
- [x] Defined complete potential outcome contract in `src/simulation/batch_generator.py`:
  - `potential_outcome_noop = Bernoulli(mu_0(state))`
  - `potential_outcome[action] = Bernoulli(clip(mu_0(state) + tau(state, action), 0, 1))`
  - `observed_outcome = potential_outcome[observed_action]`
  - `ground_truth_recoverable = potential_outcome_noop`
- [x] Enforced common support and positivity floor: `propensity >= 0.05` for all eligible logged actions to prevent IPS explosion.
- [x] Updated `CausalSimulationRecord` and `SimulationRecord` in `src/simulation/models.py` to support complete potential outcome vector.
- [x] Regenerated all synthetic data files (`data/synthetic_batch_50.jsonl`, `data/synthetic_batch_500.jsonl`, `data/synthetic_batch_5000.jsonl`, `data/causal_batch_5000.jsonl`, `data/test_cases_edge.jsonl`).

### 2. Feature Extractor Alignment & Model Retraining (R3.3 & R3.4)
- [x] Aligned `src/ml/features.py` to exact canonical 14-dimensional feature vector specification, eliminating uncatalogued collinear features.
- [x] Reconciled assertion threshold to `< 0.05` with matching error message in `src/ml/train.py`.
- [x] Retrained recovery propensity model on unconfounded baseline outcomes (`src/ml/train.py`).
  - Accuracy: 74.40%
  - ROC-AUC: 0.7300
  - PR-AUC: 0.5223
  - Calibration ECE: 0.0372 (< 3.8%)
  - Structural Sanity: Max P(LEGAL_HOLD) = 0.0269 < 0.05, Mean P = 0.0174 < 0.05.
- [x] Retrained uplift T-learner model with vectorized PEHE evaluation in `src/ml/uplift.py`.

### 3. Provenance & Model Card Synchronization (R3.5)
- [x] Computed and serialized `model_sha256` into `src/ml/models/metadata.json`.
- [x] Fully synchronized dataset SHA256 (`90b2d59a5d96...`), model SHA256 (`bfab55a8fb19...`), hyperparameter CV results, test metrics, and slice metrics into `docs/models/recovery_propensity_model_card.md`.

### 4. Monte Carlo Evaluation Optimization (R3.6)
- [x] Optimized `scripts/run_monte_carlo.py` by precomputing policy decisions prior to bootstrap resampling, executing end-to-end SNIPS evaluation in under 1 second.
- [x] Verified clean execution of `scripts/run_monte_carlo.py`.

### 5. Automated Testing & Verification
- [x] Added unit tests in `tests/unit/test_batch_generator.py` and `tests/unit/test_recovery_model.py`.
- [x] Verified all 13 unit tests in simulation and ML suites pass cleanly.
