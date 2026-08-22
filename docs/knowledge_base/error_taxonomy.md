# Dual-Rail Error Taxonomy & Diagnostic Mapping
### Sourcing Key: 🟢 Verified Regulation / Processor Docs | 🟡 Derived Logic | 🔴 Modeled Assumption

A fundamental flaw in naive recovery systems is treating all payment failure codes identically. This document defines the exact, verified code mapping for **UPI AutoPay** (U-series and Z-series) and **e-NACH** (NPCI Return Codes), along with their assigned failure classes, action eligibility, and calibrated success priors.

---

## 1. UPI AutoPay Failure Code Taxonomy

UPI AutoPay runs over the standard UPI switch with recurring mandate purpose metadata. It inherits NPCI's core UPI response code structure.

| Code | Official Meaning | Failure Class | Action Eligibility | Handling Protocol |
|---|---|---|---|---|
| `Z9` | 🟢 Insufficient funds in customer account | **Soft / Liquidity** | Spaced retry, interactive WhatsApp/SMS nudge | Calculate customer salary cycle prior; slot into next non-peak window $\ge 24$h. |
| `U19` | 🟢 Request authorisation declined | **Ambiguous Decline** | Spaced retry with lower confidence prior | Do not assume low balance. Re-evaluate with secondary signals before scheduling retry. |
| `U30` | 🟢 Debit has failed (generic gateway/bank failure) | **Ambiguous Decline** | Conditional retry | Treat conservatively. If repeated twice, escalate or offer alternate Payment Link. |
| `U69` | 🟢 Collect request expired (customer timeout) | **Soft / UX Friction** | Interactive Payment Link, WhatsApp nudge | Customer missed the approval notification window. Re-dispatch link with fresh validity. |
| `U28` | 🟢 Customer bank switch inoperative / down | **Technical Downtime** | 30-min cooldown retry | **Does not consume attempt quota** under fair implementation. Retry after switch recovery. |
| `Z7` | 🟢 Too many transactions in interval (rate-limited) | **Technical Rate-Limit** | Exponential backoff cooldown | Delay retry by 2–4 hours into the next permitted non-peak slot. |
| `Z8` | 🟢 Per-transaction limit exceeded | **Hard (Ticket Mismatch)** | `PAYMENT_LINK` | Amount exceeds bank limit. Auto-retry will fail. Route to `PAYMENT_LINK` (*Note: Dynamic ticket amount-splitting is a merchant-side business decision out of this system's scope*). |

---

## 2. e-NACH Failure Code Taxonomy

e-NACH uses NPCI's dedicated Return Code taxonomy, divided into Presentation (execution) and Registration stages.

### 2.1 e-NACH Presentation (Execution) Codes

| Code | Meaning | Failure Class | Feasible Action Set | Protocol |
|---|---|---|---|---|
| `01` | Account closed | **Hard / Terminal** | `ESCALATE_HUMAN`, `PAYMENT_LINK` | Account permanently inactive. $P(\text{Success}) = 0$. Zero further auto-debits. |
| `02` | No such account | **Hard / Terminal** | `ESCALATE_HUMAN` | Account number invalid or non-existent. |
| `04` | Balance insufficient | **Soft / Liquidity** | `SILENT_RETRY`, `PIN_PROMPTED_RETRY`, `WHATSAPP_NUDGE` | Enforce NPCI spacing ($24$h/$72$h/$168$h) and non-peak masks. |
| `05` | Not arranged for | **Hard (Customer Setup)** | `PAYMENT_LINK`, `RE_MANDATE_FLOW` | Bank setup does not permit auto-debits. Prompt re-registration. |
| `06` | Payment stopped by drawer | **Hard (Mandate Revoked)** | `RE_MANDATE_FLOW`, `ESCALATE_HUMAN` | Customer instructed bank to stop debit. Cease auto-debits; request fresh AFA. |
| `07` | Payment stopped under court order / litigation | **Legal Hold** | `ESCALATE_HUMAN` **ONLY** | **Strict Regulatory Gate:** Instant automated shutdown. Zero automated contact. |

### 2.2 e-NACH Registration Codes

| Code | Meaning | Failure Class | Recommended Strategy |
|---|---|---|---|
| `AP01` | Account blocked / frozen | **Hard / Terminal** | Prompt customer for alternate bank account. |
| `AP02` | Account closed | **Hard / Terminal** | Halt onboarding; request fresh mandate submission. |
| `AP03` | Account frozen (regulatory) | **Legal Hold** | *Mapped from Legal-Adjacent to strict Legal Hold.* Escalate to compliance operations. No automation. |
| `AP04` | Account inoperative | **Hard / Terminal** | Prompt customer to activate bank account or provide alternate. |
| `AP05` | No such account number | **Hard / Terminal** | Validation error; re-trigger account input flow. |

---

## 3. Success-Probability Priors ($P(\text{Success} \mid \text{Class}, k)$)

The decision model utilizes calibrated probability priors to optimize expected recovery. These numbers are explicitly classified by their evidentiary basis:

* 🟢 **Verified Fact:** Industry aggregate failure rate for UPI AutoPay is $8\text{--}15\%$; e-mandate card failures are $2\text{--}3\%$. Over $20\text{ million}$ AutoPay cancellations monthly are caused by low balance.
* 🟡 **Derived Rule:** Hard declines (e-NACH `01`, `02`, `MD01`) have $P(\text{Success}) = 0.000$ by mathematical certainty.
* 🔴 **Modeled Assumptions (Configurable Calibration Table):**

| Failure Class | $P(\text{Success})$ at $k=2$ (Retry 1) | $P(\text{Success})$ at $k=3$ (Retry 2) | $P(\text{Success})$ at $k=4$ (Retry 3) | Evidentiary Basis |
|---|---|---|---|---|
| **Soft / Liquidity** (`Z9`, `04`) | $0.45$ (baseline) / $0.70$ (post-salary) | $0.55$ (baseline) / $0.80$ (post-salary) | $0.25$ (diminishing return) | 🔴 Modeled prior: Liquidity clusters around salary cycle dates (1st–5th, 15th, month-end). |
| **Technical Downtime** (`U28`, `91`) | $0.90$ (after 30m cooldown) | $0.95$ | $0.95$ | 🔴 Modeled prior: Technical switch outages are transient and clear rapidly. |
| **Ambiguous Decline** (`U19`, `U30`) | $0.20$ | $0.15$ | $0.05$ | 🔴 Modeled prior: Conservative baseline preventing attempt burn on unverified declines. |
| **UX Friction** (`U69`) | $0.65$ (interactive link) | $0.40$ | $0.20$ | 🔴 Modeled prior: Nudges recover customers who simply missed notification windows. |
| **Hard / Terminal** (`01`, `02`, `AP01`) | **$0.000$** | **$0.000$** | **$0.000$** | 🟡 Derived logic: Retrying closed/blocked accounts is mathematically guaranteed to fail. |
| **Legal Hold** (`07`) | **$0.000$** (Automation Blocked) | **$0.000$** | **$0.000$** | 🟢 Verified rule: Code `07` forbids automated processing. |

---

## 4. Handling Ambiguous Declines (The Uncertainty Protocol)

🔴 **MODELED ASSUMPTION — Designed Heuristic:** The customer-history branching rules below are modeled decision heuristics constructed to balance retry conservation against recovery yield. They do not represent an official regulatory directive.

When the diagnostic engine encounters `U19` or `U30`:
1. It flags the classification confidence as **Low ($\text{Confidence} \le 0.40$)**.
2. It checks customer history:
   * If customer successfully paid last cycle $\implies$ allow single spaced retry at $k=2$.
   * If failure repeats $\implies$ immediately pivot to `PAYMENT_LINK` or `ESCALATE_HUMAN` to protect remaining attempt quota.
3. If expected net yield falls below confidence threshold $\theta$, the agent executes `ABORT_COMPLIANT`.
