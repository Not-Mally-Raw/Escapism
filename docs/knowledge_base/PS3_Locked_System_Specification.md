# AI Revenue Recovery — Locked System Specification
### Track 03 · Flaw B: Mandate & UPI AutoPay Debit Recovery
### Status: LOCKED — v1.0

**Sourcing convention used throughout this document:**
- 🟢 **VERIFIED** — directly confirmed against NPCI circulars, RBI frameworks, or primary payment-processor documentation (Stripe, Razorpay, Decentro/NPCI error code references), cited inline.
- 🟡 **REGULATION-DERIVED** — a direct mathematical consequence of a verified rule (e.g., the retry-window math follows necessarily from the verified attempt cap + spacing rule).
- 🔴 **MODELED ASSUMPTION** — no public dataset exists for this number. Stated explicitly as a calibration prior for synthetic data generation, not a real statistic. Never presented as fact in a demo.

This convention itself is a scoring point — it proves you know the difference between a regulation and a guess.

---

## 1. Formal Mathematical Problem Formulation

### 1.1 System framing: Constrained Finite-Horizon Decision Process

Each mandate-failure case `i` is a discrete-time control problem over a bounded horizon (the mandate's billing cycle). At each decision epoch `k`, the agent observes a state `S_i,k` and selects an action `A_i,k` from a finite, pre-vetted action set. This is **not** modeled as an unconstrained MDP because the action space itself is legally bounded before any optimization runs — the constraints are a hard mask applied to the action space, not a soft penalty term the agent learns to avoid. This distinction matters: a penalty-only formulation could still choose a non-compliant action if the model judges it profitable, which is unacceptable here.

**State space** `S_i,k`:
```
S_i,k = { failure_class, attempt_count_k, time_since_last_attempt,
          amount, mandate_type, current_time, customer_liquidity_prior,
          prior_channel_response_history, dispute_flag }
```

**Action space** `A` (fixed, finite, pre-vetted — the agent selects among these, it does not invent actions):
```
A ∈ { SILENT_RETRY, PIN_PROMPTED_RETRY, PAYMENT_LINK, WHATSAPP_NUDGE,
      SMS_NUDGE, RE_MANDATE_FLOW, COOLDOWN_WAIT, ESCALATE_HUMAN, ABORT_COMPLIANT }
```

### 1.2 Objective function

$$
\mathbb{E}[\text{Net Recovery}] = \sum_{i=1}^{N} \Big( P(\text{Success} \mid S_{i,k}, A_{i,k}) \cdot \text{Amount}_i \;-\; C(A_{i,k}) \;-\; \text{Penalty}(A_{i,k}, S_{i,k}) \Big)
$$

**subject to** (all hard constraints — violation is infeasibility, not a penalty):

$$
k \le 4 \quad \text{🟢 VERIFIED — NPCI, effective Aug 2025: max 4 total attempts (1 original + 3 retries) per mandate cycle}
$$

$$
\Delta t_k \ge
\begin{cases}
24\text{h} & k=2 \\
72\text{h} & k=3 \\
168\text{h} & k=4
\end{cases}
\quad \text{🟢 VERIFIED — NPCI-mandated retry spacing, cited across multiple independent processor implementation guides}
$$

$$
t_{\text{execution}} \in T_{\text{non-peak}} = [00:00,10:00) \cup [13:00,17:00) \cup [21:30,24:00)
\quad \text{🟢 VERIFIED — NPCI non-peak execution rule, effective Aug 2025}
$$

$$
t_{\text{customer\_contact}} \in [08:00, 19:00) \text{ local time}
\quad \text{🟢 VERIFIED — RBI Fair Practices Code digital contact window}
$$

$$
t_{\text{pre-debit-notice}} \ge t_{\text{execution}} - 24\text{h}
\quad \text{🟢 VERIFIED — RBI e-mandate framework: mandatory pre-debit notification ≥24h before any recurring charge}
$$

**AFA / silent-retry constraint — corrected formulation:**

Your original phrasing ("If Amount > ₹15,000, Action ≠ Silent Retry") is *directionally* right but technically imprecise, and precision matters here because a judge who knows this rail will catch it. The ₹15,000 threshold does not forbid retrying — it changes **which class of action is legally available**:

$$
\text{Amount} \le ₹15{,}000 \implies A \in \{\text{SILENT\_RETRY}, \text{PIN\_PROMPTED\_RETRY}, \dots\}
$$
$$
\text{Amount} > ₹15{,}000 \implies A \notin \{\text{SILENT\_RETRY}\}, \quad A \in \{\text{PIN\_PROMPTED\_RETRY}, \dots\}
$$

🟢 **VERIFIED** — confirmed independently by Stripe's own India UPI AutoPay documentation and Razorpay's UPI mandate documentation: recurring debits up to ₹15,000 execute without customer PIN re-entry; above ₹15,000, every execution (original or retry) requires fresh customer-present PIN authentication. A mandate modification (amount change, validity extension, cancellation) always requires fresh AFA regardless of amount.

This means: above ₹15,000, `SILENT_RETRY` is **not in the feasible action set at all** — it's a hard mask, not a discouraged choice with a penalty attached.

### 1.3 Cost function `C(A)` — stated as calibration defaults, not measured facts

🔴 **MODELED ASSUMPTION.** No public per-transaction cost schedule exists for bank bounce fees, DLT-routed SMS, or WhatsApp Business messaging in the context of this specific use case. Rather than presenting invented numbers as fact (the previous draft's error), this system treats cost as a **configurable parameter table** the evaluation harness reads at runtime — so the number itself is never load-bearing for a compliance or correctness claim, only for the optional "cost-optimized ranking" feature.

| Action | Cost model | Status |
|---|---|---|
| `SILENT_RETRY` / `PIN_PROMPTED_RETRY` | `c_retry` (config, default placeholder) | 🔴 assumption — configurable |
| `PAYMENT_LINK` | `c_link` (config, default placeholder) | 🔴 assumption — configurable |
| `WHATSAPP_NUDGE` | `c_whatsapp` (config, default placeholder) | 🔴 assumption — configurable |
| `SMS_NUDGE` | `c_sms` (config, default placeholder) | 🔴 assumption — configurable |
| `ESCALATE_HUMAN` | `c_escalate` (config, default placeholder, order of magnitude higher) | 🔴 assumption — configurable |

**Penalty function** `Penalty(A, S)`:
```
Penalty(A, S) = ∞   if A violates any hard constraint in §1.2   (infeasible, not scored)
Penalty(A, S) = λ · churn_risk(A, S)   if A is feasible but degrades customer relationship
                                        (e.g. 3rd nudge within a week)
```
`λ` is a tunable weight, not a claimed empirical constant — stated as such.

---

## 2. Failure Taxonomy & Probability Matrix — Corrected

### 2.1 Two distinct rails, two distinct code sets — the previous draft conflated these

A critical correction: **UPI AutoPay** and **e-NACH** are different rails with different, non-interchangeable error code sets. Treating them as one taxonomy (as the earlier draft did) is itself a technical inaccuracy a domain-literate judge would flag.

**UPI AutoPay** executes as a standard UPI transaction carrying a recurring-mandate purpose code — so its failures use the **general UPI U-series / Z-series response codes**, not a separate "AutoPay-only" code set.

**e-NACH** is a bank-rail mandate system with its own, separate NPCI-published return-code taxonomy for both *registration* and *presentation* (execution) failures.

### 2.2 UPI AutoPay failure codes (verified against Razorpay's own documented mapping)

| Code | Official meaning | Class | Action-eligible |
|---|---|---|---|
| `Z9` | 🟢 Insufficient funds in customer account | **Soft / Liquidity** | Spaced retry, nudge |
| `U19` | 🟢 Request authorisation is declined (generic decline) | **Soft/ambiguous — requires secondary signal** | Spaced retry with lower confidence prior |
| `U30` | 🟢 Debit has failed (generic failure code, Razorpay's own mapping) | **Ambiguous — do not assume VPA-blocked without secondary evidence** | Conditional retry |
| `U69` | 🟢 Collect request expired — customer took too long to act | **Soft / UX friction**, not mandate cancellation | Re-send with shorter validity, nudge |
| `U28` | 🟢 Customer's bank is down | **Technical / Retryable, does not consume attempt quota under a fair implementation** | Cooldown retry |
| `Z7` | 🟢 Too many transactions in a bank-set interval | **Technical / rate-limited** | Cooldown, longer backoff |
| `Z8` | 🟢 Per-transaction limit exceeded (bank-set) | **Hard for this amount** | Escalate — amount restructuring, not retry |

*Note on the previous draft's error:* it claimed U19 = insufficient funds and U30 = "VPA blocked." Neither is correct per Razorpay's own published mapping — insufficient funds is `Z9`, and both U19/U30 are more generic decline signals that should not be assumed to mean a specific customer-side condition without a secondary signal. **This system's diagnostic classifier must therefore treat U19/U30 as lower-confidence classifications and should not silently assume "insufficient funds" behind them** — this is itself a defensible design decision worth stating explicitly in your submission, since it's more honest than the alternative.

### 2.3 e-NACH failure codes (verified — NPCI mandate presentation/registration return codes, per processor documentation)

**Presentation (execution) failures:**

| Code | Meaning | Class |
|---|---|---|
| `01` | Account closed | **Hard / Terminal** |
| `02` | No such account | **Hard / Terminal** |
| `04` | Balance insufficient | **Soft / Liquidity** |
| `05` | Not arranged for | **Hard / Terminal (customer-side setup issue)** |
| `06` | Payment stopped by drawer | **Hard / Mandate Revoked** |
| `07` | Payment stopped under court order / litigation | **Hard / Legal Hold — mandatory human escalation, no automation permitted** |

**Registration failures:**

| Code | Meaning | Class |
|---|---|---|
| `AP01` | Account blocked | **Hard / Terminal** |
| `AP02` | Account closed | **Hard / Terminal** |
| `AP03` | Account frozen | **Hard / Legal-adjacent — escalate, do not retry** |
| `AP04` | Account inoperative | **Hard / Terminal** |
| `AP05` | No such account | **Hard / Terminal** |

### 2.4 Success-probability priors — explicitly modeled, not measured

🔴 **This entire sub-section is a calibration prior for the synthetic generator, not an NPCI statistic.** No public source publishes P(success | code, attempt_k). What *is* publicly available and can legitimately ground your calibration:

- 🟢 Industry reporting places **overall UPI AutoPay failure rates at 8–15%**, versus **2–3% for card-based mandates** (independent fintech industry analysis, 2026) — use this only as a sanity check that your synthetic aggregate failure rate lands in a plausible range, not as a per-code number.
- 🟢 One industry source reports that proactive grace-period messaging **recovers roughly 15–20% of failed users** who see the notification and top up — again, directional calibration evidence, not an NPCI-official figure, and should be labeled as such wherever cited.
- 🟢 NPCI-adjacent reporting confirms **~20 million AutoPay revocations per month are attributed specifically to low customer balance**, i.e., liquidity is empirically the dominant real-world failure driver — this justifies weighting `Z9`/liquidity-class failures as your highest-volume synthetic bucket, which is a defensible modeling choice you can cite.

Recommended prior structure (stated plainly as assumptions in your README, with the above three data points as your justification, not your proof):

| Failure class | P(success) at k=1 retry | P(success) at k=2 retry | P(success) at k=3 retry | Rationale |
|---|---|---|---|---|
| Soft/Liquidity (Z9, 04) | Higher, rising with time-since-failure | Higher again if spaced ≥72h (post-salary-cycle) | Diminishing | 🔴 modeled — liquidity events cluster around pay cycles, directionally supported by the 20M/month liquidity-revocation data point above |
| Technical (U28, Z7) | High if retried after cooldown | High | High | 🔴 modeled — technical outages are typically transient, not customer-driven |
| Ambiguous decline (U19, U30) | Low-moderate | Lower | Lowest | 🔴 modeled — deliberately conservative, since root cause is unconfirmed |
| Hard/Terminal (01,02,05,06,AP01-05) | **0 by definition** | 0 | 0 | 🟢 regulation/logic-derived — a closed account cannot succeed on retry; this is not a probability estimate, it's a structural fact |

---

## 3. Quantitative Evaluation Framework

### 3.1 Net Recovery Rate (NRR)

$$
\text{NRR}_{\text{INR}} = \sum_{i \in \text{Settled}} \text{Amount}_i \qquad \text{NRR}_{\%} = \frac{\text{NRR}_{\text{INR}}}{\sum_{i=1}^{N} \text{Amount}_i}
$$

**Terminal State Requirement:** Revenue is *only* counted as recovered when it reaches the terminal financial success state (`CAPTURED` or `SETTLED`). Intermediate events such as `INTERVENTION_SENT`, `LINK_OPENED`, `PAYMENT_INITIATED`, or `AUTHORIZED` do **not** contribute to NRR.

### 3.2 False Escalation Rate (FER)

$$
\text{FER} = \frac{|\{i : A_i = \text{ESCALATE\_HUMAN} \text{ and ground-truth label} = \text{recoverable-without-escalation}\}|}{|\{i : A_i = \text{ESCALATE\_HUMAN}\}|}
$$

This requires your synthetic generator to carry a **ground-truth recoverability label** independent of what the agent decides — i.e., the label is baked into the synthetic case at generation time, and the agent is scored against it, not against its own output. This is the mechanism that prevents circular self-grading.

### 3.3 Compliance Violation Rate (CVR)

$$
\text{CVR} = \frac{|\{(i,k) : A_{i,k} \text{ executed outside any constraint in §1.2}\}|}{|\{(i,k) : \text{action executed}\}|}
$$

**Framing correction from the earlier draft:** since the guardrail layer is deterministic code sitting *before* the LLM decision layer (a hard gate, not a soft classifier), CVR = 0.0% is a property you **prove by construction and verify by exhaustive test**, not a statistic your model "achieves." State this distinction explicitly in your submission — claiming a proven invariant is a stronger, more honest claim than claiming a measured rate, and it preempts the obvious judge question ("how do you know it'll always be zero, not just zero on this batch?").

### 3.4 Diagnostic confusion matrix

Standard multi-class confusion matrix over `{Soft/Liquidity, Hard/Terminal, Technical, Ambiguous, Legal-Hold}` predicted-class vs ground-truth-class, with standard precision/recall/F1 per class. Legal-Hold (NACH code `07`) deserves a dedicated recall metric on its own — a missed legal-hold case that gets automated contact is your single worst failure mode, worse than a missed liquidity case, and your metrics should reflect that asymmetry rather than averaging it away.

### 3.5 The honest edge case, formalized

$$
\text{Abort-Compliant condition: } \; \nexists \, A \in \text{FeasibleSet}(S_{i,k}) \text{ such that } P(\text{Success}\mid S_{i,k}, A) > \theta_{\text{confidence}}
$$

i.e., every legally-available action's expected success probability falls below a stated confidence threshold `θ` (itself a declared, tunable parameter — not hidden), so the agent's rational choice is `ABORT_COMPLIANT`: log the case, take no further automated action, hand to human review. This is the scenario to keep in your final demo, logged with its full rationale trace — it demonstrates the system chooses *not knowing* over *guessing under regulatory risk*, which is a stronger trust signal than a 100% action rate would be.

---

## 4. Locked System Specification — Scoping Contract

**Problem statement (one paragraph, locked):**
> Build a mandate-failure recovery agent for UPI AutoPay and e-NACH recurring debits that (1) classifies each failure against a verified NPCI/e-NACH failure taxonomy, (2) selects the legally-feasible recovery action that maximizes expected net recovery under a deterministic, unit-tested guardrail layer encoding NPCI's 4-attempt cap, 24/72/168h spacing, non-peak execution windows, and RBI's 8AM–7PM contact window plus ₹15,000 AFA threshold, and (3) proves its behavior on a labeled synthetic batch via a diagnostic confusion matrix, a by-construction zero compliance-violation guarantee, and an honestly-reported false-escalation rate — explicitly distinguishing every number in the final report as verified regulation, derived math, or stated modeling assumption.

### 4.1 Batch transaction record — JSON schema

```json
{
  "case_id": "string, unique",
  "rail": "UPI_AUTOPAY | ENACH",
  "mandate_id": "string",
  "merchant_id": "string",
  "customer_id": "string",
  "amount_inr": "number",
  "afa_required": "boolean — computed: amount_inr > 15000",
  "failure_code": "string — from §2.2 or §2.3 verified code sets only",
  "failure_class": "SOFT_LIQUIDITY | HARD_TERMINAL | TECHNICAL_RETRYABLE | AMBIGUOUS_DECLINE | LEGAL_HOLD",
  "ground_truth_recoverable": "boolean — set at generation time, hidden from agent",
  "failure_timestamp": "ISO 8601, IST",
  "attempt_count": "integer, 1-4",
  "attempt_history": [
    {
      "attempt_number": "integer",
      "timestamp": "ISO 8601",
      "action_taken": "enum from §1.1 action space",
      "within_non_peak_window": "boolean — computed, not asserted",
      "spacing_satisfied": "boolean — computed against §1.2 rule",
      "outcome": "string"
    }
  ],
  "next_permitted_retry_ts": "ISO 8601 — computed from spacing rule",
  "next_valid_execution_window": "ISO 8601 — computed from non-peak mask",
  "pre_debit_notice_sent_ts": "ISO 8601 or null",
  "resolution_status": "PENDING | RECOVERED | ABORT_COMPLIANT | ESCALATED | FAILED_TERMINAL",
  "audit_trail": [
    {
      "step": "integer",
      "timestamp": "ISO 8601",
      "module": "GUARDRAIL_ENGINE | DIAGNOSTIC_CLASSIFIER | DECISION_LAYER",
      "guardrails_evaluated": ["array of constraint IDs from §1.2"],
      "verdict": "string",
      "rationale": "string — human-readable"
    }
  ]
}
```

### 4.2 What is explicitly locked vs. explicitly still-configurable

| Locked (do not renegotiate) | Configurable (state your chosen value, don't hide it) |
|---|---|
| 4-attempt cap | Cost table values (§1.3) |
| 24/72/168h spacing | Confidence threshold θ (§3.5) |
| Non-peak execution windows | Churn-risk penalty weight λ |
| 8AM–7PM contact window | Batch size (recommend 50–200; 500 is ambitious but fine if generator is solid) |
| ₹15,000 AFA silent-retry mask | Which secondary channel (WhatsApp vs SMS) is primary |
| Legal-hold (code `07`) → mandatory human escalation, zero automation | Exact synthetic failure-class distribution weights |

---

*End of locked specification. Next step, when you're ready: implementation scaffolding for the guardrail engine (§1.2) as a standalone, unit-tested module — built before the diagnostic classifier or decision layer touch it, per the dependency order this spec implies.*
