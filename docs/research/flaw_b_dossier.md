# Research & Architecture Dossier — Flaw B (Mandate & UPI AutoPay Debits)
### Status: RESEARCH DELIVERABLE — Documentation Only
### Sourcing Key: 🟢 Verified Source Cited | 🟡 Own Analysis / Derived | 🔴 Modeled Assumption / Unverified

> **STEP 0 Result — Ground-Truth Verification:**
> \`find . -iname "PS3_Locked_System_Specification*"\` returned exactly one file:
> \`./docs/knowledge_base/PS3_Locked_System_Specification.md\` (274 lines).
> No \`-2\` variant exists in the repository. This single file is the authoritative locked specification.
> There is no reconciliation needed, and no evidence of the earlier overwrite incident producing a duplicate.

---

## Deliverable A: Competitive Matrix & The Compliance Moat

### A.1 The Three-Way Comparison

This project's thesis is that payment recovery is two stacked problems with different failure modes: (1) a deterministic legal-feasibility question, and (2) a probabilistic revenue-optimization question. The table below compares three paradigms against how they handle this separation.

| Dimension | Fixed-Schedule Dunning (T+1/T+3) | Generic LLM Agent | This Project: Guardrail Engine + Probabilistic Optimizer |
|---|---|---|---|
| **Retry timing** | Static calendar rules (e.g., retry on day 1, day 3, day 7) regardless of failure type or customer context | Model decides timing — may or may not respect regulatory spacing | Timing constrained by deterministic spacing validator (\`spacing_validator.py\`); optimization layer selects *within* permitted windows only |
| **Failure-class discrimination** | None — treats \`Z9\` (insufficient funds) identically to \`07\` (court order) | Depends on prompt quality; may hallucinate distinctions or miss legal-hold codes | Exhaustive code-to-class mapping per \`error_taxonomy.md\`; \`07\`/\`AP03\` hard-gated to \`ESCALATE_HUMAN\` only |
| **Compliance guarantee** | Accidental — schedule may or may not respect the 4-attempt cap or AFA threshold | None provable — depends on prompt adherence, which degrades under ambiguity or model updates | **Proven by construction:** guardrails are pure functions, exhaustively unit-tested, physically isolated from any probabilistic component by AST boundary tests (\`test_architecture_boundaries.py\`) |
| **Auditability** | Reconstructable from schedule config but not from individual case reasoning | "The model decided to" — not reproducible, not defensible to a regulator | Every action traces to a specific guardrail check with a citation to the regulation that motivated it |
| **Adaptivity** | Zero — never improves without manual rule changes | High — learns from data continuously | Planned (Phase 9–10): probabilistic layer can improve, but *only within the boundary the deterministic layer has already drawn* |
| **Failure under ambiguity** | Executes next scheduled retry regardless | Model improvises, potentially past a legal boundary | System fails closed — ambiguous/unknown input blocks the action (\`legal_hold_filter.py\` §3.4: uncatalogued codes route to \`ABORT_COMPLIANT\`) |

### A.2 Market Teardown: Stripe Smart Retries

🟢 **Verified Fact (Source: Stripe official documentation, \`stripe.com/docs/billing/revenue-recovery/smart-retries\`):**

Stripe's documentation lists the conditions under which it will *not* retry a payment. Among them:

> *"The payment card is India-issued."*

This appears alongside other non-retry conditions like "the issuer returned a hard decline code" and "no payment methods are available."

🟡 **What this implies (own analysis, not a sourced claim):**

Stripe's own engineering team evaluated the Indian regulatory environment — RBI's AFA mandate for transactions >₹15,000, the 24h pre-debit notification requirement, NPCI's attempt caps and spacing rules — and chose to **exclude India-issued cards from their flagship ML retry product entirely**, rather than attempt to make the probabilistic model compliant with these deterministic constraints. This is the strongest independent validation of this project's rules-first architecture: the world's most sophisticated payment retry ML system decided the Indian regulatory domain is not a problem their model should try to solve.

This does **not** mean Stripe's approach is inferior globally. In jurisdictions without India's AFA/mandate constraints, their ML-driven approach is likely superior to a rules-first system. The claim is narrower and more defensible: **for the specific regulatory environment this project targets (Indian recurring mandates), Stripe's own team concluded that an ML-first approach is not viable.**

### A.3 Market Teardown: Razorpay's Native Retry Infrastructure

Razorpay offers three relevant products: **Intelligent Payment Retry** (part of their Subscriptions platform), **Failed Payment Recovery**, and a broader **Intelligent Revenue-Protect** layer.

🟢 **Verified from Razorpay's public documentation and product pages:**

- Razorpay describes an "Intelligent Retry Engine" that considers "user context, bank availability, and merchant priorities" to determine optimal retry timing.
- For Subscriptions, if an auto-charge fails, the system attempts to retry "on the following day" by default.
- Merchants can configure their own retry cadence or select from predefined templates.
- When a payment continues to fail after all retry attempts, the subscription moves from \`pending\` to \`halted\` state, at which point automated charges stop.

[UNVERIFIED] **Whether Razorpay's retry engine internally enforces NPCI's exact numeric constraints (4-attempt cap, 24h/72h/168h spacing, non-peak windows) as explicit, independently auditable gates** — or whether these constraints are implicit in their ML model's learned behavior — is not stated in their public documentation. Their documentation describes the system in "intelligent"/"ML" terms rather than citing specific regulatory rule implementations.

🟡 **What this means for this project's positioning (own analysis):**

This project does not claim to out-recover Razorpay on raw volume — that would be an absurd claim for a hackathon build against a production system with years of real transaction data. The differentiation is **legibility and auditability**: this project's compliance is a citable, independently checkable, unit-tested artifact that can be handed to a regulator. Whether Razorpay's system is equally compliant is unknown from public sources, but its compliance is a property you have to *trust* rather than *verify* from outside.

### A.4 The Compliance Moat — Quantified

The "moat" this project claims is not about recovery rates. It is about the provable properties of the guardrail layer:

| Property | Mechanism | Verification |
|---|---|---|
| CVR = 0% (by construction) | Combined feasible-action mask (\`rbi_npci_regulations.md §3\`) sits in front of any probabilistic component | Exhaustive unit tests on every boundary value; 50-case & 500-case integration checkpoint with 0 violations |
| Legal-Hold Recall = 100% | Code \`07\` and \`AP03\` short-circuit to \`ESCALATE_HUMAN\` before any other logic runs (\`engine.py\` L46–47) | Dedicated \`test_legal_hold_filter.py\` |
| Fail-closed on unknown inputs | Uncatalogued failure codes route to \`ABORT_COMPLIANT\` (\`rbi_npci_regulations.md §3.4\`) | \`test_fail_closed_unknown_code\` |
| No label leakage | \`ground_truth_recoverable\` lives in \`SimulationRecord\` only, not in \`MandateStateRecord\` (\`src/simulation/models.py\`); import boundaries enforced by AST test | \`test_architecture_boundaries.py\` — three tests covering guardrails↔simulation, decision↔simulation, simulation↔decision |

---

## Deliverable B: Applied ML Literature Review — FUTURE ROADMAP ONLY

> **⚠️ PHASE 9–10 CONTENT.** Nothing in this deliverable is an immediate build target. The current build sequence is: diagnostic classifier (Stage 3) → decision layer (Stage 4) → execution (Stage 5) → evaluation harness (Stage 7). Contextual bandits and survival modeling are explicitly deferred to Phase 9–10, well after the baseline decision layer is built and measured. This section exists solely to document the research landscape and show the technical reasoning for the planned future architecture.

### B.1 Contextual Bandits for Action Selection

**The paradigm:** A contextual bandit treats each recovery opportunity as a decision point where the agent observes context (failure class, attempt count, amount, time features), selects an action from the feasible set, and receives a reward (payment recovered or not).

**Why this fits this project's architecture (own analysis):**

The guardrail engine's output is exactly the bandit's action space: \`compute_feasible_action_set()\` returns a pruned set of legal actions. The bandit selects *within* this set. The guardrail layer never changes based on what the bandit learns — maintaining the "two problems stacked" separation.

The key advantage over the project's current static-prior approach (the 🔴 MODELED ASSUMPTION probability table in \`error_taxonomy.md §3\`) is that bandits continuously update their estimates from observed outcomes, adapting to seasonal patterns and merchant-specific behavior without manual recalibration of the prior table.

**Relevant literature and industry practice:**

- 🟢 Adyen has published technical content describing contextual multi-armed bandits for payment routing optimization (Source: adyen.com technical blog on payment optimization).
- 🟢 Academic surveys on RL in fintech (Source: arXiv, systematic surveys on Reinforcement Learning applications in financial services) categorize payment retry optimization under "profit maximization" applications, noting that RL-based strategies outperform static heuristics in dynamic environments.
- [UNVERIFIED] Whether Stripe's internal Smart Retries implementation specifically uses contextual bandits (vs. other ML approaches) is not publicly documented. The claim that "major payment processors use contextual bandits" is stated in secondary sources but not confirmed by Stripe's own technical publications.

**Critical constraint for this project:** The bandit's reward signal must be defined as \`CAPTURED\`/\`SETTLED\` (per the locked NRR definition in \`PS3_Locked_System_Specification.md §3.1\` and \`evals/metrics.py\`), not \`INTERVENTION_SENT\` or \`LINK_OPENED\`. Defining the reward on an intermediate event would create the exact metric-inflation problem the NRR redefinition was designed to prevent.

**Anti-circularity constraint:** The bandit's learned policy must never feed back into \`src/simulation/distributions.py\`. Per \`decision_layer_notes.md\` (locked for Stage 4) and enforced by \`test_architecture_boundaries.py\`: the decision layer derives estimates from live diagnostic confidence, observable features, and independent heuristics — never from the synthetic generator's ground-truth distributions.

### B.2 Survival Analysis for Churn / Recovery Timing

**The paradigm:** Survival analysis models "time-to-event" — in this context, time from first failure to either recovery or permanent churn. Unlike binary classifiers that predict "will this mandate recover," survival models predict "*when* is this mandate most likely to recover if we act."

**Why this fits (own analysis):**

The salary-cycle clustering already modeled in \`latent_state_model.py\` is essentially a hand-coded survival prior: the hypothesis that liquidity-failure customers are more likely to recover around payroll dates (1st–5th, 15th, month-end). A proper survival model (Cox Proportional Hazards or a gradient-boosted survival model) would learn these patterns from data rather than encoding them as fixed assumptions.

**Relevant literature:**

- 🟢 The \`lifelines\` Python library provides production-ready implementations of Kaplan-Meier estimators, Cox Proportional Hazards models, and Aalen's Additive models. It is the standard tool in the Python ecosystem for survival analysis (Source: lifelines documentation, github.com/CamDavidsonPilon/lifelines).
- 🟢 Academic work on survival analysis for subscription churn prediction consistently demonstrates that survival models outperform binary classifiers for time-dependent prediction tasks by properly handling right-censored data (Source: multiple published studies indexed on ResearchGate and academic repositories).
- 🟡 **Own analysis, not a sourced finding:** The specific application of survival analysis to *payment failure recovery timing* (as opposed to subscription churn) is an underexplored area in the published literature. Most survival-analysis-for-churn work focuses on voluntary cancellation, not involuntary failure recovery. Applying the same framework to mandate failures is a reasonable extension, but it should be validated empirically before claiming it works.

**How it would integrate with the guardrail engine (own analysis):** The survival model would output a hazard curve per case — "probability of recovery at time t." The decision layer would use this to choose *when* within the guardrail-permitted windows to schedule actions. The survival model never influences *which* actions are legally feasible — that remains the deterministic guardrail engine's sole responsibility.

**Recommendation for future implementation:** Start with Kaplan-Meier stratified by \`FailureClass\` to validate the salary-cycle hypothesis against real (or realistic synthetic) outcome data before investing in a full Cox model. If the survival curves by failure class don't visibly separate, the survival model adds no information the simpler prior table doesn't already capture.

---

## Deliverable C: Production Data Architecture & Anti-Circularity ETL

### C.1 Webhook Idempotency Architecture

Razorpay delivers webhooks with at-least-once semantics. The ingestion layer (planned at \`src/ingestion/\`) per the project structure must handle:

**Deduplication by Event ID:**

| Concern | Mechanism |
|---|---|
| **At-least-once delivery** | Razorpay may deliver the same webhook event multiple times. Each event carries a unique \`event_id\`. |
| **Idempotency gate** | \`src/ingestion/idempotency.py\` must maintain a persistent set of seen \`event_id\` values. On receipt, check membership before processing. If already seen, return \`200 OK\` without side effects. |
| **Out-of-order protection** | Events for the same mandate may arrive out of chronological order. The state record's \`failure_timestamp\` and \`attempt_count\` must be compared against the existing record; a stale event (lower \`attempt_count\` or older \`failure_timestamp\` than the current state) must be dropped, not applied. |
| **Signature verification** | \`src/ingestion/webhook_verifier.py\` must validate \`X-Razorpay-Signature\` using HMAC SHA-256 before any processing occurs. Unsigned or incorrectly signed events must be rejected with \`401\` — this is a fail-closed gate, consistent with the existing guardrail philosophy. |

**Cross-reference with existing guardrails:** The idempotency gate is logically upstream of the guardrail engine. The guardrail engine (\`src/guardrails/engine.py\`) receives a \`MandateStateRecord\` — it has no awareness of webhook delivery semantics. This separation is correct: the ingestion layer is responsible for ensuring the guardrail engine never sees the same event twice or processes a stale state.

**Implementation note (recommendation, not a current-task change):** For the hackathon build, a SQLite-backed \`seen_event_ids\` table is sufficient. The production roadmap would replace this with a Redis SET or a DynamoDB conditional write, but the idempotency *contract* is identical regardless of backing store.

### C.2 Production State Schema — Extending MandateStateRecord

The current \`MandateStateRecord\` covers the guardrail engine's input requirements. For the full production pipeline (ingestion through execution), the following additions are recommended as **future code changes** (this dossier is documentation-only):

\`\`\`diff
 class MandateStateRecord(BaseModel):
     model_config = ConfigDict(frozen=True, extra="forbid")

     case_id: str
     mandate_id: str
     merchant_id: str = Field(default="mer_default_001")
     customer_id: str = Field(default="cust_default_001")
     rail: PaymentRail
     amount_inr: Decimal = Field(gt=Decimal("0.00"))
     attempt_count: int = Field(ge=1, le=4)
     failure_code: str
     failure_class: FailureClass
     failure_timestamp: datetime
     last_attempt_timestamp: Optional[datetime] = None
     afa_required: bool = Field(default=False)
     pre_debit_notice_sent: bool = Field(default=False)
     customer_timezone: str = Field(default="Asia/Kolkata")
+
+    # --- Recommended additions for production pipeline ---
+    webhook_event_id: Optional[str] = Field(
+        default=None,
+        description="Razorpay webhook event ID for idempotency tracking"
+    )
+    diagnosis: Optional[str] = Field(
+        default=None,
+        description="Serialized DiagnosticOutput JSON from Stage 3 classifier"
+    )
+    selected_action: Optional[str] = Field(
+        default=None,
+        description="ActionType selected by decision layer, for audit trail"
+    )
+    execution_scheduled_at: Optional[datetime] = Field(
+        default=None,
+        description="Timestamp when the selected action is scheduled to fire"
+    )
\`\`\`

**Note:** \`ground_truth_recoverable\` remains strictly in \`src/simulation/models.py::SimulationRecord\`. It must never be added back to \`MandateStateRecord\`. This is confirmed consistent with the existing separation.

### C.3 Synthetic Dataset Calibration

The synthetic data generated in \`data/synthetic_batch_500.jsonl\` and \`data/test_cases_edge.jsonl\` must approximate realistic failure distributions. The following weighting is based on industry data already gathered in this project:

| Failure Class | Proposed Weight | Evidentiary Basis |
|---|---|---|
| **Soft / Liquidity** (\`Z9\`, \`04\`) | ~55–65% | 🔴 MODELED ASSUMPTION. Derived from the industry observation that >20M monthly UPI AutoPay cancellations are caused by low balance (\`error_taxonomy.md §3\`), which strongly suggests liquidity is the dominant failure mode. The exact percentage is not publicly documented. |
| **Technical Retryable** (\`U28\`, \`Z7\`) | ~10–15% | 🔴 MODELED ASSUMPTION. Bank switch downtime and rate-limiting are intermittent and transient. No public source quantifies their share. |
| **Ambiguous Decline** (\`U19\`, \`U30\`) | ~10–15% | 🔴 MODELED ASSUMPTION. Generic decline codes are common in payment processing generally, but their exact prevalence in UPI AutoPay is not publicly documented. |
| **Hard Terminal** (\`01\`, \`02\`, \`Z8\`, \`AP01–AP05\`) | ~5–10% | 🔴 MODELED ASSUMPTION. Closed/frozen accounts are a smaller fraction. |
| **Legal Hold** (\`07\`, \`AP03\`) | ~1–2% | 🔴 MODELED ASSUMPTION. Court-ordered holds are rare events. |
| **UX Friction** (\`U69\`) | ~5–10% | 🔴 MODELED ASSUMPTION. Expired collect requests depend on notification engagement rates. |

**Honesty note:** Every single percentage in the table above is a modeled assumption. The only verified data points grounding these distributions are: (1) the overall UPI AutoPay failure rate is 8–15% (🟢 per \`error_taxonomy.md §3\`), and (2) >20M monthly cancellations are liquidity-driven (🟢 same source). The relative proportions within the failure population are this project's own estimates.

### C.4 Anti-Circularity Boundary — Confirmation of Consistency

The anti-circularity decision is locked in \`decision_layer_notes.md\` (Status: LOCKED for Stage 4) and enforced by \`test_architecture_boundaries.py\`.

**Locked Resolution (restated, not redesigned):**

> "The decision layer never reads a static ground-truth prior table from the simulation engine. Instead, it derives its success probability estimates live from the diagnostic classifier's confidence score, observable domain attributes, and independent heuristic priors, with a strict physical import ban on \`src/simulation/\`."

**Enforcement mechanisms already in place:**

1. \`test_guardrails_import_boundaries()\` — asserts no file in \`src/guardrails/\` imports from \`src.simulation\`
2. \`test_decision_import_boundaries()\` — asserts no file in \`src/decision/\` or \`src/diagnosis/\` imports from \`src.simulation\`
3. \`test_simulation_import_boundaries()\` — asserts no file in \`src/simulation/\` imports from \`src.decision\`

**Consistency check:** This dossier's recommendations (contextual bandits, survival models, webhook pipeline) are all consistent with these boundaries. The bandit/survival model would live in \`src/decision/\` and derive estimates from observable features and diagnostic output, never from \`src/simulation/distributions.py\`. No inconsistency found.

---

## Deliverable D: Adversarial Threat Model

### D.1 Fail-Closed Protocol — Confirmation of Consistency

This dossier's recommendations are consistent with the fail-closed behavior already implemented:

| Failure Mode | Existing Implementation | Status |
|---|---|---|
| **Unrecognized failure code** | \`legal_hold_filter.py\` routes unknown codes to \`ABORT_COMPLIANT\` (mandatory escalation) | ✅ Verified, with test |
| **Missing \`last_attempt_timestamp\`** | \`engine.py\` — temporal filters only apply when \`current_time is not None and state.last_attempt_timestamp is not None\`; non-temporal gates still enforce | ✅ Consistent |
| **Timezone-naive datetime** | \`contact_gate.py\` and \`window_mask.py\` throw explicit \`ValueError\` on naive datetimes | ✅ Verified, with tests |
| **Low-confidence LLM classification** | \`ambiguity_handler.py\` downgrades to \`AMBIGUOUS_DECLINE\` when confidence ≤ 0.40 | ✅ Implemented |

This dossier does **not** propose changing any of these defaults.

### D.2 PII / Data Leakage via LLM Diagnosis

The diagnostic classifier (Stage 3) will receive raw webhook payloads that may contain PII:

| PII Field | Present in Razorpay Webhooks | Risk |
|---|---|---|
| Customer VPA (e.g., \`user@upi\`) | Yes — in UPI AutoPay payment events | LLM prompt injection could extract it; logging raw prompts would persist it |
| Customer phone number | Yes — in mandate registration events | Same risk as VPA |
| Customer email | Yes — in customer-linked events | Same |
| Bank account number (masked) | Partially — last 4 digits common | Lower risk but still PII |

**Existing mitigation by construction:**

The \`DiagnosticOutput\` schema (Constraint B5) contains exactly three fields: \`failure_class\` (an enum), \`confidence\` (a float), and \`evidence\` (a list of strings). Because the LLM's output is schema-validated through Pydantic before it can influence any downstream logic, PII in the raw webhook cannot propagate through the diagnostic output *as structured data* — but it could still appear in the \`evidence\` list strings if the LLM copies verbatim text from the input.

**Recommendations (future code changes, not implemented now):**

1. **Input redaction before LLM invocation:** Before the raw webhook payload is sent to the LLM for classification, apply a redaction pass that replaces VPA/phone/email/account fields with placeholder tokens (e.g., \`[REDACTED_VPA]\`). This prevents the LLM from ever seeing PII.
2. **Evidence field sanitization:** After receiving \`DiagnosticOutput\`, run a regex-based scrub on each string in the \`evidence\` list to catch any patterns matching UPI VPA, phone numbers, or email addresses before logging.
3. **Structured audit logging with field-level redaction:** The audit logger must never log raw webhook payloads. Log only the \`MandateStateRecord\` fields (which contain no VPA/phone/email by design) plus the schema-validated \`DiagnosticOutput\`.
4. **LLM provider data processing agreement:** If using an external LLM API, ensure the API's data processing terms prohibit training on input data. This is a legal/procurement step, not a code change.

### D.3 State Mismanagement — Double-Charge Race Condition

**The threat:** In a concurrent system, two processes could simultaneously evaluate the same mandate state, each conclude that a retry is feasible, and both fire a debit — violating both the 4-attempt cap and the 24h spacing rule.

**Legal and financial consequences:**

- **Double-charge to customer account:** The customer is debited twice. Under RBI's e-mandate framework (🟢 Source: RBI Digital Payments E-Mandate Framework, 2026 — rbi.org.in), unauthorized debits require the bank to process a reversal. The merchant bears the reversal processing cost plus potential penalty.
- **NPCI attempt cap violation:** If the mandate is at \`attempt_count = 3\`, a double-fire would push it to \`attempt_count = 5\`, exceeding the NPCI maximum of 4. This is a regulatory violation, not just a billing error.
- **24h spacing violation:** Two simultaneous retries would have zero spacing between them, violating \`spacing_validator.py\`'s 24h minimum.

**How the existing guardrails would catch this (if the state is correctly maintained):**

- \`attempt_limiter.py\`: \`check_attempt_cap(4)\` returns \`False\`, blocking all retries at the cap.
- \`spacing_validator.py\`: \`check_spacing(attempt_number, last_attempt_ts, now)\` returns \`False\` if the elapsed time is under the required minimum.

**The gap:** These functions are pure — they check the state they're given. If two processes read the *same stale state* before either updates it, both would see \`attempt_count = 3\` and both would pass the cap check. The guardrail functions are correct; the vulnerability is in the state-update layer upstream.

**Recommendations (future code changes):**

1. **Optimistic concurrency control on \`MandateStateRecord\`:** Add a \`version\` or \`etag\` field. Before executing an action, the execution layer must atomically compare-and-swap the state record. If the version has changed since the read, the execution must abort.
2. **Idempotency key on action dispatch:** Each action dispatch must carry a unique idempotency key. Razorpay's API supports idempotency keys — the execution layer must use \`{case_id}_{attempt_count}_{scheduled_timestamp}\` as the key.
3. **Single-writer pattern (simplest for hackathon):** For the current single-process architecture, this threat is mitigated by serialized processing. The race condition only becomes live in a production multi-worker deployment. Document this as a known limitation.

---

## Appendix: Claims Marked [UNVERIFIED]

Per the project's sourcing discipline rule, the following claims in this dossier could not be verified against a specific, checkable source:

| Location | Claim | Status |
|---|---|---|
| §A.3 | Whether Razorpay's retry engine internally enforces NPCI's exact numeric constraints as explicit auditable gates | [UNVERIFIED] — not stated in public documentation |
| §B.1 | Whether Stripe's Smart Retries internally uses contextual bandits specifically | [UNVERIFIED] — secondary sources claim this, Stripe's own publications do not confirm |
| §C.3 | All six failure-class percentage weightings (55–65% liquidity, 10–15% technical, etc.) | [UNVERIFIED] — 🔴 MODELED ASSUMPTIONS, explicitly labeled as such |

No other claims in this dossier present unverified information in the same tone as sourced findings.
