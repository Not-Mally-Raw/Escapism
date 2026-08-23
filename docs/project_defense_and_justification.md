# Project Justification & Defense
### AI Revenue Recovery — Track 03, Flaw B (Mandate & UPI AutoPay Debits)

This document answers the three critical questions any reviewer, auditor, or engineer will ask when evaluating this project's architecture. It serves as the foundational defense of why this system was built the way it was.

---

## 1. The Core Bet, Stated Plainly

> **Payment recovery is not one problem. It is two problems stacked, and most systems dangerously blur them together. This project refuses to blur them.**

**Problem A: *"What are we legally and contractually allowed to do to this customer, right now?"*** 
This is a question with a **correct, checkable, deterministic answer**. NPCI's attempt cap is exactly 4. RBI's Additional Factor of Authentication (AFA) threshold is exactly ₹15,000. These are not suggestions; they are the law.

**Problem B: *"Of the things we're allowed to do, which one recovers the most money?"*** 
This is a question with **no correct answer**, only a better or worse probabilistic estimate, because customer liquidity and behavior are genuinely uncertain.

Most systems—including generic AI agent hackathons and off-the-shelf commercial retry logic—either solve Problem B and hope Problem A comes along for free (e.g., an LLM "prompted" to be compliant), or solve Problem A so rigidly that Problem B is ignored (a basic rules engine).

**The bet this project makes:** These two problems have fundamentally different failure modes. 
* Problem A fails *catastrophically and legally* (an unauthorized silent debit >₹15,000 constitutes a direct breach of RBI's digital mandate framework, inviting regulatory penalties and reputational damage). 
* Problem B fails *gracefully and statistically* (a suboptimal retry time loses a few rupees). 

Therefore, they require different engineering treatments. Problem A gets deterministic code, proven by exhaustive invariant tests and AST boundary enforcement. Problem B gets a probabilistic LLM/Classifier model that is allowed to guess, but *only within the hard boundaries Problem A has already drawn.*

---

## 2. Comparative Analysis — Why Not the Alternatives

### 2.1 vs. Stripe Smart Retries (Single ML Model)
Stripe's approach is a single black-box ML model that learns retry timing from aggregate data. 
* **The Reality Check:** Stripe's "Smart Retries" feature **explicitly excludes India-issued cards**. (Source: Stripe documentation: `stripe.com/docs/billing/revenue-recovery/smart-retries`). Stripe's own engineering team evaluated the Indian regulatory environment and chose to exclude it from their flagship ML retry product entirely, rather than try to make the probabilistic model compliant. This validates our core thesis: the Indian regulatory environment requires a rules-first architecture, not an ML-first one. 
* **The Trade-off:** By treating compliance as a rigid predecessor to optimization, our system can operate safely in the Indian regulatory environment where Stripe's native ML cannot.

### 2.2 vs. Razorpay's Native Retry Infrastructure
Razorpay's own Intelligent Payment Retry and Failed Payment Recovery are production-grade systems. We do not claim to out-recover them on raw volume.
* **The Differentiation:** Razorpay's public documentation describes intelligent retry logic, but our system's differentiation is **provable legibility**. Our compliance is an independently checkable, auditable artifact. We decouple the NPCI/RBI rules (Problem A) entirely from the recovery logic (Problem B). If the RBI audits this system, we can hand them a pure mathematical proof (the Guardrail Engine) guaranteeing zero violations, rather than asking them to trust an ML model's weights.

### 2.3 vs. A Generic "LLM Decides Everything" Agent
* **Compliance:** An LLM with unrestricted execution authority is a massive liability. Prompt adherence degrades under adversarial input or ambiguity. Our LLM is restricted to outputting a strict `DiagnosticOutput` JSON schema. It *never* executes a payment; it merely recommends a classification that the Guardrail Engine filters.
* **Failure Mode:** A generic agent improvises under ambiguity. Our system implements a strict **fail-closed** Uncertainty Protocol (e.g., routing unknown bank codes to `ABORT_COMPLIANT`).

---

## 3. Justifying the "Microscopic" Decisions

Every small engineering adjustment made during this build was load-bearing. None were incidental cleanup.

| Microscopic Decision | The Catastrophic Failure it Prevents |
|---|---|
| **AST Import Boundary Tests** | Prevents future engineers from quietly wiring the decision layer's success estimate to the same probability distribution the synthetic generator uses to create ground truth. Prevents the benchmark from "grading its own answer key." |
| **🟢/🟡/🔴 Provenance Tags** | Prevents the dangerous assumption that internal best-practices are laws, or that laws are mere suggestions. (e.g., accurately downgrading 8AM-7PM contact hours from verified law to 🟡 Best Practice, while strictly enforcing it to avoid RBI Ombudsman harassment penalties). |
| **Fail-Closed on Unknown Codes** | A silent "fail-open" on an uncatalogued bank code (e.g., a new NPCI legal hold code) would bypass the system, directly contradicting the project's zero-violation claim. |
| **Strict NRR Definition** | Net Revenue Recovered (NRR) strictly ignores `LINK_OPENED` or `AUTHORIZED`. It only counts `CAPTURED` or `SETTLED`. This prevents dashboard metrics from lying to executives. |
| **Timezone-Naive Rejection** | Silently assuming IST for a naive datetime violates cross-border contact hour laws. The engine now throws a fatal `ValueError` if fed a naive datetime. |

---

## 4. How the System Actually Works (End-to-End Walkthrough)

**The Scenario:** A ₹25,000 UPI AutoPay subscription debit fails at 09:12 IST with bank code `Z9` (insufficient funds), on attempt 1 of the cycle.

1. **Ingestion & Diagnosis (Stage 3):** The webhook arrives. The LLM diagnostic classifier maps `Z9` to `SOFT_LIQUIDITY`. It emits a strict JSON schema. The `ambiguity_handler.py` verifies the LLM's confidence score.
2. **Deterministic Guardrails (Stage 2):** The Guardrail Engine evaluates the state:
   * *Legal Hold?* No.
   * *Attempt Cap?* 1 is < 4. (Pass)
   * *AFA Threshold?* ₹25,000 > ₹15,000. (Fail). The engine **mutates the feasible action set**, permanently discarding `SILENT_RETRY` but preserving `PIN_PROMPTED_RETRY`.
   * *Pre-Debit Notice?* Verified sent >24h ago. (Pass)
3. **Probabilistic Decision (Stage 4):** The LLM/Decision layer looks at the restricted feasible set (now only containing `PIN_PROMPTED_RETRY`, `PAYMENT_LINK`, `WHATSAPP_NUDGE`, `ESCALATE_HUMAN`). It calculates expected yields and selects `WHATSAPP_NUDGE` because liquidity failures respond well to interactive nudges.
4. **Execution & Audit:** The nudge is dispatched. The entire rationale—including the exact RBI rule that blocked the silent retry—is logged for audit.

*What exists right now:* Stages 1 (Data Generation) and 2 (Guardrails) are built, fully tested, and proven. Stage 3 (Diagnosis) is currently in active development.
