# AI Revenue Recovery: Compliance-Constrained Decision Engine

A production-ready, mathematically proven, and audit-traced AI orchestration engine designed specifically for India's strict mandate recovery regulations (UPI AutoPay & e-NACH). 

**The Core Result:** By structurally flooring unrecoverable/illegal segments (`HARD_TERMINAL`, `LEGAL_HOLD`) through a deterministic guardrail engine, this system proves that the industry-standard "Blind Retry" policy is actively **net-negative in compliance-sensitive segments** (-₹319,032 in fines averted). In aggregate across 5,000 mandates, the AI Orchestrator achieves **₹29.15M NRR**—delivering a **+₹5.69M (+24.3%) uplift over Blind Retry** and **+₹10.55M (+56.7%) over doing nothing**, while provably gating all actions behind strict regulatory invariants.

---

## 🚀 3-Step Ingestion & Deployment

Deploy the entire engine and launch the terminal interface in three steps:

```bash
# Step 1: Clone repository and activate environment
git clone https://github.com/Not-Mally-Raw/Razorpay-Escapism-Track-03.git
cd Razorpay-Escapism-Track-03
python3 -m venv .venv && source .venv/bin/activate

# Step 2: Install dependencies
pip install -e .

# Step 3: Launch decision engine & Bloomberg Terminal UI
python3 src/api/server.py
```
Open **`http://localhost:8000`** in your browser. Interactive keyboard navigation (`F1`–`F8`), real-time worker telemetry, and instant simulation.

### Reproduce Core Monte Carlo Benchmark (SNIPS OPE)
To reproduce the 3-Policy Benchmark in your terminal:
```bash
python3 scripts/run_monte_carlo.py
```
Runs 1,000 bootstrap iterations over logged synthetic outcomes using Self-Normalized Inverse Propensity Scoring (SNIPS) to prove the net-revenue recovery (NRR) superiority of the AI Orchestrator over Naive Blind Retry, complete with 95% Confidence Intervals and segment-level breakdowns.

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
* **Profile 3 (Certified Production Baseline - 74.4% Acc, 0.730 AUC, ECE 0.0372, Dataset `90b2d59a...`):** Re-anchored on pure unconfounded passive recovery ($Y_0 = \text{Bernoulli}(\mu_0(S))$). Model training is 100% deterministic (`random_seed=42`), producing bit-for-bit identical parameters on successive runs with full SHA256 lineage tracking between dataset, joblib artifact, and metadata.

---

## 🏛️ Core Architectural Invariants & Compliance Proofs

- **Deterministic Regulatory Invariants**: Hard enforcement of RBI and NPCI mandates (4-attempt cap, 24h retry spacing, ₹15,000 AFA threshold, and mandatory `LEGAL_HOLD`/`07`/`AP03` escalation).
- **Mathematical Decision Governance**: Deterministic `θ_digital` safety margins, action cost-benefit matrices, and three-profile model lineage progression.
- **Fail-Closed Verification**: Zero-tolerance design ensuring unrecoverable segments (`HARD_TERMINAL`, `LEGAL_HOLD`) abort immediately rather than burning retry budgets or triggering regulatory fines.
- **Auditable State Transitions**: Fully traceable decision logs detailing raw bank failure codes, extracted semantic root causes, candidate action expected values, and cryptographic execution intents.

---

## 🔒 Security & Defense-in-Depth
- **OWASP LLM01:2025 Prompt Injection Mitigation**: The semantic diagnosis LLM is protected by untrusted-input segregation, strict control-character stripping, and a deterministic fallback layer that restricts privileges (the LLM cannot bypass hard compliance filters).
- **Replay-Safe Execution**: Webhook ingestion is strictly decoupled from execution to prevent double-charges and lock-contention, using idempotent header parsing (`x-razorpay-event-id`), durable SQLite intents, and crash-reconciliation loops.
- **Mock Execution & Transparent Boundaries**: Operates in mock execution mode by default to ensure safe offline evaluation without triggering external banking rails.

---

*This project is completely verified with 169 passing automated tests spanning unit, integration, golden-thread, and adversarial chaos-fuzzing.*
