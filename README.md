# AI Revenue Recovery: Compliance-Constrained Decision Engine

A production-ready, mathematically proven, and audit-traced AI orchestration engine designed specifically for India's strict mandate recovery regulations (UPI AutoPay & e-NACH). 

**The Core Result:** By structurally flooring unrecoverable/illegal segments (`HARD_TERMINAL`, `LEGAL_HOLD`) through a deterministic guardrail engine, this system proves that the industry-standard "Blind Retry" policy is actively **net-negative in compliance-sensitive segments** (-₹319,032 in fines averted). In aggregate across 5,000 mandates, the AI Orchestrator achieves **₹29.15M NRR**—delivering a **+₹5.69M (+24.3%) uplift over Blind Retry** and **+₹10.55M (+56.7%) over doing nothing**, while provably gating all actions behind strict regulatory invariants.

---

## ⚡ One-Command Demo
To run the interactive Analytics and Decision Dashboard:

```bash
# 1. Setup Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Run the Dashboard
streamlit run src/dashboard/app.py
```

To reproduce the core Monte Carlo 3-Policy Benchmark in the terminal, run:
```bash
python3 scripts/run_monte_carlo.py
```

This will run 1,000 bootstrap iterations over logged synthetic outcomes using Self-Normalized Inverse Propensity Scoring (SNIPS) to prove the net-revenue recovery (NRR) superiority of the AI Orchestrator over the Naive Blind-Retry policy, complete with 95% Confidence Intervals and segment-level breakdowns.

---

## 🏗️ Why We Built This

Payment recovery is not one problem; it is two problems stacked:
1. **"What are we legally allowed to do?"** (NPCI cap of 4 attempts, 24h/72h spacing, ₹15,000 AFA threshold). This requires a 100% deterministic, fail-closed answer.
2. **"Of the allowed actions, which recovers the most money?"** This requires probabilistic AI/ML estimation.

Most systems either prompt an LLM to be "compliant" (dangerous, non-deterministic) or write a basic rules engine that ignores intelligent recovery. **This architecture refuses to blur them.** The Guardrail Engine rigorously computes the allowed subset of actions, and the ML/Decision track selects the highest Expected Value (EV) action *only from that subset*.

---

## 📊 Model Lineage & The Three-Profile Progression

The recovery propensity estimator (`src/ml/`) evolved through three distinct, audited stages:
* **Profile 1 (Exploration - 80.1% Acc, 0.875 AUC, Dataset `40f623dd...`):** Early proof-of-concept calibrated to 2.0% legal hold base rates.
* **Profile 2 (Causal Shift - 72.1% Acc, 0.761 AUC, Dataset `4f4e09e2...`):** Expanded merchant/customer diversity, but revealed policy contamination when `ground_truth_recoverable` was assigned as treatment-conditioned outcome.
* **Profile 3 (Certified Production Baseline - 74.4% Acc, 0.730 AUC, ECE 0.0372, Dataset `90b2d59a...`):** Re-anchored on pure unconfounded passive recovery ($Y_0 = \text{Bernoulli}(\mu_0(S))$). Model training is 100% deterministic (`random_seed=42`), producing bit-for-bit identical parameters on successive runs with full SHA256 lineage tracking between dataset, joblib artifact, and model cards.

---

## 📚 Key Artifacts & Proofs

- **[Project Defense & Market Context](docs/project_defense_and_justification.md)**: Explains the fundamental design choices, including why global baselines like SEPA rules fail under Indian regulations.
- **[Decision Governance Record](docs/decision_governance_record.md)**: Documents the math behind the deterministic `θ_digital` safety margin, action multipliers, and three-profile model lineage.
- **[Compliance Proof Appendix](docs/compliance_proof_appendix.md)**: A map of every hard Indian regulatory invariant and the automated tests that guarantee they are never violated.
- **[Recovery Playbook](docs/recovery_playbook.md)**: A human-readable trace of real synthetic cases passing through the entire decision pipeline.

---

## 🔒 Security & Defense-in-Depth
- **OWASP LLM01:2025 Prompt Injection Mitigation**: The semantic diagnosis LLM is protected by untrusted-input segregation, strict control-character stripping, and a deterministic fallback layer that restricts privileges (the LLM cannot bypass hard compliance filters).
- **Replay-Safe Execution**: Webhook ingestion is strictly decoupled from execution to prevent double-charges and lock-contention, using idempotent header parsing (`x-razorpay-event-id`), durable SQLite intents, and crash-reconciliation loops.
- **Mock Execution & Transparent Boundaries**: Operates in mock execution mode by default to ensure safe offline evaluation without triggering external banking rails.

---

*This project is completely verified with 169 passing automated tests spanning unit, integration, golden-thread, and adversarial chaos-fuzzing.*
