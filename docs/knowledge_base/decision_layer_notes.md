# Architectural Decision: Insulation of Decision Layer from Synthetic Data Generator
### Status: LOCKED for Stage 4

---

## 1. The Core Risk: Distributional Circularity (Oracle Self-Scoring)

In benchmark evaluations of agentic decision systems, a critical flaw occurs if the decision planner reads its success-probability priors directly from the same distribution tables used by the synthetic data generator (`src/simulation/distributions.py`). If the agent has access to the exact probability curves governing the simulation:
1. The agent becomes an oracle lookup rather than an inferential optimizer.
2. The measured Net Recovery Rate (NRR) and False Escalation Rate (FER) become circular and unrepresentative of real-world deployment where true latent customer states are unobserved.

---

## 2. Locked Architectural Resolution: Epistemic Separation & Dynamic Inference

To guarantee objective evaluation rigor, the decision engine in Stage 4 will adhere to the following architectural design:

**Locked Resolution:** **The decision layer never reads a static ground-truth prior table from the simulation engine. Instead, it derives its success probability estimates live from the diagnostic classifier's confidence score, observable domain attributes, and independent heuristic priors, with a strict physical import ban on `src/simulation/`.**

### Concrete Enforcement Mechanisms:
1. **Hard Import Insulation:** Static boundary analysis tests (`tests/test_architecture_boundaries.py`) will assert that neither `src/decision/` nor `src/core/config.py` ever imports from `src/simulation/`.
2. **Dynamic Confidence-Driven Estimation:** The diagnostic classifier outputs a `DiagnosticResult` tuple: `(failure_class: FailureClass, confidence: float, features: dict)`. The decision optimizer computes expected yield using this confidence factor modulated by time-since-inflow, attempt count backoff, and observable channel history.
3. **Latent Ground-Truth Separation:** The synthetic data generator (`src/simulation/`) embeds hidden ground-truth recoverability labels and customer state transitions (e.g., hidden bank balance depletion models) that are strictly sequestered from the agent's observation space.

---

## 3. One-Paragraph Formal Justification

> "The decision layer is strictly decoupled from the synthetic data generation engine. While `src/simulation/distributions.py` models ground-truth customer balance replenishment and bank switch behavior using latent probabilistic parameters, `src/decision/` possesses zero access to these generator parameters. The decision agent relies solely on observable state features, the diagnostic classifier's calibrated confidence output, and independent conservative heuristics. This ensures that the evaluation harness tests genuine decision-making under uncertainty, eliminating circular self-grading and providing judge-proof validation of the system's Net Recovery Rate and False Escalation Rate."
