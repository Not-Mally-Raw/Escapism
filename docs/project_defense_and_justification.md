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

Therefore, they require different engineering treatments. Problem A gets deterministic code, verified by exhaustive invariant tests and AST boundary enforcement. Within the modeled policy domain and supplied state, prohibited actions are structurally excluded from the feasible action set. Problem B gets a probabilistic LLM/Classifier model that is allowed to guess, but *only within the hard boundaries Problem A has already drawn.*

**The sorting is the product.** The core question for any payment recovery system isn't "does AI handle everything?" — it's: what percentage of cases never reaches a human, what percentage reaches a human with work already assembled, and what data decided the split. This project makes that split explicit and auditable:

| Tier | What happens | This project's mechanism |
|---|---|---|
| **Resolved** | Fully automated — no human needed | Guardrail engine returns a feasible action set; decision layer selects and executes |
| **Assembled** | Routed to human, but with pre-assembled context | `ESCALATE_HUMAN` with `DiagnosticOutput` attached — the human receives failure class, confidence, evidence, and feasible actions already computed |
| **Judgment** | Genuine human judgment on novel/complex cases | Legal-hold cases (code `07`/`AP03`) and genuinely ambiguous declines below the initial ambiguity threshold |

**Why India specifically:** India's NPCI/RBI mandate framework is more granular and prescriptive than any comparable jurisdiction. SEPA Direct Debit (EU) provides an 8-week unconditional dispute window and 14-day pre-notification — but no attempt cap, no escalating spacing schedule, and no AFA threshold. India's rules are tighter and faster. A system that treats Indian mandate recovery as a subset of global retry logic will miss constraints that don't exist elsewhere. (Comparative detail: `docs/research/market_context.md §2`.)

---

## 2. Comparative Analysis — Why Not the Alternatives

### 2.1 vs. Stripe Smart Retries (Single ML Model)
Stripe's approach is a single black-box ML model that learns retry timing from aggregate data. 
* **Verified:** Stripe's "Smart Retries" feature **explicitly excludes India-issued cards**. (Source: Stripe documentation: `stripe.com/docs/billing/revenue-recovery/smart-retries`). This creates an important market boundary: Stripe's general Smart Retries approach cannot be directly applied to this Indian recurring-payment use case. We do not claim to know Stripe's internal reason for that exclusion unless Stripe explicitly documents it.
* **The Trade-off:** By treating compliance as a rigid predecessor to optimization, our system can operate safely in the Indian regulatory environment where Stripe's native ML retry product is not offered.

### 2.2 vs. Razorpay's Native Retry Infrastructure
Razorpay's own Intelligent Payment Retry and Failed Payment Recovery are production-grade systems. We do not claim to out-recover them on raw volume.
* **The Differentiation:** We are making compliance independently inspectable rather than treating it as an implicit property of an optimization system. We decouple the NPCI/RBI rules (Problem A) entirely from the recovery logic (Problem B). If the RBI audits this system, we can hand them independently verifiable guardrail code with cited regulatory sources, rather than asking them to trust an ML model's weights.

### 2.3 vs. A Generic "LLM Decides Everything" Agent
* **Compliance:** An LLM with unrestricted execution authority is a massive liability. Prompt adherence degrades under adversarial input or ambiguity. Our LLM is restricted to outputting a strict `DiagnosticOutput` JSON schema. It *never* executes a payment; it merely recommends a classification that the Guardrail Engine filters.
* **Failure Mode:** A generic agent improvises under ambiguity. Our system implements a strict **fail-closed** Uncertainty Protocol (e.g., routing unknown bank codes to `ABORT_COMPLIANT`).

---

## 3. Justifying the "Microscopic" Decisions

Every small engineering adjustment made during this build was load-bearing. None were incidental cleanup.

| Microscopic Decision | The Catastrophic Failure it Prevents |
|---|---|
| **AST Import Boundary Tests** | Prevents future engineers from quietly wiring the decision layer's success estimate to the same probability distribution the synthetic generator uses to create ground truth. Prevents the benchmark from "grading its own answer key." |
| **🟢/🟡/🔴 Provenance Tags** | Prevents the dangerous assumption that internal best-practices are laws, or that laws are mere suggestions. (e.g., accurately downgrading 8AM-7PM contact hours from verified law to 🟡 Best Practice, while strictly enforcing it to avoid RBI Ombudsman harassment penalties). This is not an idiosyncratic obsession — serious practitioners in adjacent regulated domains enforce the same discipline. SF AI Labs' own strategy documents explicitly label their projected improvements as "modeled automation targets from the strategy work rather than measured production results" (`docs/research/market_context.md §3.5`). |
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

## 4. Market Context: Why Global Baselines Fail Here (SEPA vs. India)
A common critique is: *"Why build a bespoke rules engine when standard dunning logic (like Stripe Smart Retries) already exists?"* 
Because standard dunning logic is built for environments like SEPA, where retry policies are largely determined by merchant risk tolerance. 
India's regulatory environment (NPCI/RBI) is structurally different:
- **SEPA:** No hard statutory cap on retry attempts.
- **India:** NPCI strictly caps presentation attempts at exactly 4 per mandate cycle.
- **SEPA:** Timing is flexible based on ML models.
- **India:** Mandates require rigid 24h / 72h / 168h escalating spacing between retry attempts.
- **SEPA:** Frictionless retries for any amount.
- **India:** ₹15,000 AFA (Additional Factor of Authentication) threshold on silent retries.

A system that treats Indian mandate recovery as a subset of global retry logic will inevitably violate constraints that simply don't exist in other jurisdictions. This is the regulatory basis for the project's rules-first architecture: the guardrail engine MUST sit between the ML model and the outside world.

## 5. The Three-Tier Sorting Pattern
The workflow is architected using a proven operational pattern (analogous to the Three-Tier Sorting seen in Healthcare Revenue Cycle Management):
1. **Resolved (Zero Human Touch):** The deterministic Guardrail Engine computes a feasible action set. The Decision Layer (Track 3) selects and executes the highest-EV action automatically.
2. **Assembled (Human with Context):** The engine triggers `ESCALATE_HUMAN` but attaches the full `DiagnosticOutput`. The human operator receives the failure class, confidence score, evidence, and the pre-computed feasible actions, drastically reducing resolution time.
3. **Judgment (Human Expertise Required):** Reserved for novel/complex cases (e.g., Legal Holds, `AP03`, `07`, or genuinely ambiguous declines below the heuristic threshold).

The success of this system isn't defined by "does AI handle everything?", but rather: what percentage of cases never reach a human, what percentage reach one with the work already assembled, and what deterministic data decided the split?
