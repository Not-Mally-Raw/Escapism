# AI Revenue Recovery: Compliance-Constrained Decision Engine

A production-ready, mathematically proven, and audit-traced AI orchestration engine designed specifically for India's strict mandate recovery regulations (UPI AutoPay & e-NACH). 

**The Core Result:** By structurally flooring unrecoverable/illegal segments (`HARD_TERMINAL`, `LEGAL_HOLD`) through a deterministic guardrail engine, this system proves that the industry-standard "Blind Retry" policy is actively net-negative in compliance-sensitive segments. This system recovers millions of rupees safely by gating AI actions behind strict regulatory invariants.

---

## ⚡ One-Command Demo
To run the interactive Analytics and Decision Dashboard:

```bash
# 1. Setup Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the Dashboard
streamlit run src/dashboard/app.py
```

To reproduce the core Monte Carlo 3-Policy Benchmark in the terminal, run:
```bash
python3 scripts/run_monte_carlo.py
```

This will run 1,000 Monte Carlo iterations to prove the net-revenue recovery (NRR) superiority of the AI Orchestrator over the Naive Blind-Retry policy, complete with 95% Confidence Intervals and segment-level breakdowns.

---

## 🏗️ Why We Built This

Payment recovery is not one problem; it is two problems stacked:
1. **"What are we legally allowed to do?"** (NPCI cap of 4 attempts, 24h/72h spacing, ₹15,000 AFA threshold). This requires a 100% deterministic, fail-closed answer.
2. **"Of the allowed actions, which recovers the most money?"** This requires probabilistic AI/ML estimation.

Most systems either prompt an LLM to be "compliant" (dangerous, non-deterministic) or write a basic rules engine that ignores intelligent recovery. **This architecture refuses to blur them.** The Guardrail Engine rigorously computes the allowed subset of actions, and the ML/Decision track selects the highest Expected Value (EV) action *only from that subset*.

---

## 📚 Key Artifacts & Proofs

- **[Project Defense & Market Context](docs/project_defense_and_justification.md)**: Explains the fundamental design choices, including why global baselines like SEPA rules fail under Indian regulations.
- **[Decision Governance Record](docs/decision_governance_record.md)**: Documents the math behind the deterministic `θ_digital` safety margin and the action multipliers.
- **[Compliance Proof Appendix](docs/compliance_proof_appendix.md)**: A map of every hard Indian regulatory invariant and the automated tests that guarantee they are never violated.
- **[Recovery Playbook](docs/recovery_playbook.md)**: A human-readable trace of real synthetic cases passing through the entire decision pipeline.

---

## 🔒 Security & Defense-in-Depth
- **OWASP LLM01:2025 Prompt Injection Mitigation**: The semantic diagnosis LLM is protected by untrusted-input segregation, strict control-character stripping, and a deterministic fallback layer that restricts privileges (the LLM cannot bypass hard compliance filters).
- **Atomic Execution**: Webhook ingestion is strictly decoupled from execution to prevent double-charges and lock-contention, using idempotent header parsing (`x-razorpay-event-id`).
- **Live Integration**: Fully tested against the Razorpay Test Gateway.

---

*This project is completely verified with 70+ passing tests spanning unit, integration, golden-thread, and adversarial chaos-fuzzing.*
