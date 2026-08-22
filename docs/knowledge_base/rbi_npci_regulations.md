# RBI & NPCI Regulatory Grounding & Invariant Constraints
### Sourcing Key: 🟢 Verified Regulation | 🟡 Regulation-Derived Math | 🔴 Modeled Assumption

This reference document formalizes the legal and technical rail constraints governing recurring debits (UPI AutoPay and e-NACH) and digital recovery communication in India. These rules are implemented as **deterministic pre-action gates**, guaranteeing a Compliance Violation Rate of **0.0% by construction**.

**Scope Boundary:** Out of scope: the ₹1,00,000 AFA-exempt carve-out for insurance/mutual-fund/credit-card-bill categories, and the FASTag/NCMC pre-debit-notice exemption. This system targets generic merchant mandates only.

---

## 1. NPCI Mandate Execution Rules (UPI AutoPay & e-NACH)

### 1.1 Maximum Lifetime Attempt Cap ($k \le 4$)
* **Regulation Reference:** 🟢 **VERIFIED — NPCI Circular on Mandate Execution Limits (Effective August 2025).**
* **Rule:** A recurring mandate cycle is legally permitted a maximum of **4 total presentation attempts**:
  * $k = 1$: Original scheduled debit execution.
  * $k = 2$: Retry Attempt 1.
  * $k = 3$: Retry Attempt 2.
  * $k = 4$: Retry Attempt 3 (Final attempt).
* **Hard Invariant:** If $\text{attempt\_count} \ge 4$, the feasible action set masks out all auto-debit retries:
  $$\text{attempt\_count} \ge 4 \implies A \cap \{\text{SILENT\_RETRY}, \text{PIN\_PROMPTED\_RETRY}\} = \emptyset$$
  The cycle is marked `FAILED_TERMINAL` or routed to `ESCALATE_HUMAN`.

---

### 1.2 Retry Spacing & Backoff Intervals
* **Regulation Reference:** 🟢 **VERIFIED — NPCI Mandated Retry Spacing Directive.**
* **Rule:** Retries must not be fired in rapid succession. The minimum time elapsed ($\Delta t_k$) since the immediately preceding debit attempt is strictly bounded:

$$\Delta t_k \ge \begin{cases} 
24\text{ hours} & \text{for } k = 2 \ (\text{Retry 1}) \\
72\text{ hours} & \text{for } k = 3 \ (\text{Retry 2}) \\
168\text{ hours} \ (7\text{ days}) & \text{for } k = 4 \ (\text{Retry 3})
\end{cases}$$

* **Hard Invariant:** Any retry execution where $t_{\text{current}} - t_{\text{last\_attempt}} < \Delta t_k$ is mathematically infeasible and blocked by the scheduler.

---

### 1.3 Non-Peak Execution Windows
* **Regulation Reference:** 🟢 **VERIFIED — NPCI System Load Management Circular (Effective August 2025).**
* **Rule:** Auto-debit presentation batches on the core banking switch are only legally permitted during non-peak operating windows (Indian Standard Time, UTC+05:30):

$$T_{\text{non-peak}} = [00:00, 10:00) \cup [13:00, 17:00) \cup [21:30, 24:00)$$

* **Peak Hours (Strictly Prohibited for Auto-Debits):**
  * Morning Peak: $10:00 \text{ AM} \le t_{\text{execution}} < 1:00 \text{ PM}$
  * Evening Peak: $5:00 \text{ PM} \le t_{\text{execution}} < 9:30 \text{ PM}$
* **Hard Invariant:** Any auto-debit retry scheduled during peak hours must be automatically delayed into the next valid non-peak window slot.

---

## 2. RBI Frameworks for Mandates & Customer Communication

### 2.1 RBI Fair Practices Code: Digital Contact Hours
* **Regulation Reference:** 🟢 **VERIFIED — RBI Fair Practices Code for Lenders & Digital Recovery (Master Direction).**
* **Rule:** Any customer-facing communication (WhatsApp message, SMS, interactive Payment Link nudge, or phone notification) must occur strictly within approved daylight hours in the recipient's local time zone:

$$t_{\text{contact}} \in [08:00, 19:00) \quad (\text{Local Recipient Time})$$

* **Hard Invariant:** Automated communication between $7:00 \text{ PM}$ and $8:00 \text{ AM}$ is an explicit regulatory violation. Inbound failures occurring during night hours must queue customer nudges until exactly $08:00 \text{ AM}$.

---

### 2.2 RBI Digital E-Mandate Framework: The ₹15,000 AFA Rule
* **Regulation Reference:** 🟢 **VERIFIED — RBI Master Direction on Digital Payments E-Mandates (Consolidated Framework).**
* **Rule:** Additional Factor Authentication (AFA / UPI PIN) requirement is tied directly to the principal ticket size:
  * **Transactions $\le ₹15{,}000$:** Eligible for silent, recurring execution without customer intervention.
  * **Transactions $> ₹15{,}000$:** Customer-present authentication (PIN entry or 3DS OTP) is legally mandatory for every presentation attempt.
* **Hard Action Mask:**
  $$\text{Amount} \le ₹15{,}000 \implies A_{\text{feasible}} \subseteq \{\text{SILENT\_RETRY}, \text{PIN\_PROMPTED\_RETRY}, \text{PAYMENT\_LINK}, \dots\}$$
  $$\text{Amount} > ₹15{,}000 \implies \text{SILENT\_RETRY} \notin A_{\text{feasible}}, \quad A_{\text{feasible}} \subseteq \{\text{PIN\_PROMPTED\_RETRY}, \text{PAYMENT\_LINK}, \dots\}$$

---

### 2.3 Pre-Debit Notification Mandate
* **Regulation Reference:** 🟢 **VERIFIED — RBI Circular on Recurring Electronic Mandates.**
* **Rule:** Merchants/Issuers must dispatch an informational pre-debit notice (via SMS or email) at least **24 hours prior** to debit presentation:

$$t_{\text{pre-debit-notice}} \le t_{\text{execution}} - 24\text{ hours}$$

* **Hard Invariant:** If a re-scheduled retry date is modified, a fresh pre-debit alert must precede execution by $\ge 24$ hours.

---

### 2.4 Legal Hold & Litigation (e-NACH Code 07)
* **Regulation Reference:** 🟢 **VERIFIED — NPCI Procedural Guidelines for e-NACH Return Codes.**
* **Rule:** When an account is flagged under court order, insolvency, or statutory litigation (Return Code `07`), all automated collection, debits, and nudges must cease immediately.
* **Hard Invariant:**
  $$\text{failure\_code} = \text{'07'} \implies A_{\text{feasible}} = \{\text{ESCALATE\_HUMAN}\}$$
  Automated dunning or retrying a Code `07` case is a critical compliance violation.

---

## 3. The Combined Feasible Action Mask

The deterministic Guardrail Engine computes the feasible action set by applying all regulatory masks simultaneously:

$$A_{\text{feasible}}(S) = A_{\text{universe}} \cap \text{Mask}_{\text{Attempts}}(k) \cap \text{Mask}_{\text{Spacing}}(\Delta t) \cap \text{Mask}_{\text{Window}}(t) \cap \text{Mask}_{\text{AFA}}(\text{Amount}) \cap \text{Mask}_{\text{FPC}}(t_{\text{contact}}) \cap \text{Mask}_{\text{Legal}}(Code)$$

Because this mask sits strictly **in front of** the probabilistic decision layer, the Compliance Violation Rate (CVR) is **$0.0\%$ by construction**.
