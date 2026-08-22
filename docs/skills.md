# Engineering Standards, Patterns & Skills Specification
### System: AI Revenue Recovery (Track 03 — Flaw B: Mandate & UPI AutoPay Debits)

This document establishes the architecture patterns, validation frameworks, testing invariants, and metric formulations required for the implementation.

---

## 1. State Management & Webhook Idempotency

Razorpay and bank switches deliver webhook events on an **at-least-once** model with exponential backoff retries over a 24-hour window. A naive recovery agent that fires actions on raw webhook arrival will double-debit customers or exhaust attempt quotas within minutes.

### 1.1 Cryptographic Signature Verification
Every inbound webhook payload must be validated using HMAC SHA-256 before any parsing occurs:

```python
import hmac
import hashlib

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifies X-Razorpay-Signature header against the raw request body.
    Constant-time comparison prevents timing attack vulnerabilities.
    """
    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signature_header)
```

### 1.2 Atomic Event Deduplication & Replay Protection
1. **Event ID Deduplication:** 🟢 **VERIFIED** — Every webhook contains a unique `event_id` (e.g., `event_K9xZ...`). The ingestion layer queries an atomic set / key-value store (`SETNX` with 48-hour TTL). If the key exists, the event is immediately acknowledged with HTTP 200 and dropped as a no-op.
2. **Timestamp Drift Gate:** 🔴 **MODELED ASSUMPTION** — Webhooks with a generation timestamp older than 300 seconds ($5\text{ minutes}$) without an active retry header are rejected to prevent replay attacks. *Note: Razorpay's exact retry-header semantics were not independently verified against primary docs; this is a defensive default, not a confirmed spec behavior.*
3. **Mandate Lock:** 🟡 **DERIVED LOGIC** — When evaluating a retry sequence, the engine acquires an atomic distributed lock on `mandate_id` for the duration of the state transition to prevent concurrent race conditions.

---

## 2. Data Validation & Domain Modeling (Pydantic v2)

All domain entities, API boundaries, and state payloads are strictly defined using **Pydantic v2**. 

### 2.1 Immutability & Type Safety Rules
* Domain states are immutable snapshots (`ConfigDict(frozen=True)`).
* All monetary values are represented as positive integers in paise or decimal floats with explicit currency validation.
* All timestamps use timezone-aware `datetime` objects normalized to Indian Standard Time (IST, UTC+05:30).
* Every enum represents a closed, finite domain.

### 2.2 Core Type Hierarchy Example (Python Definition)

```python
from enum import StrEnum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PaymentRail(StrEnum):
    UPI_AUTOPAY = "UPI_AUTOPAY"
    ENACH = "ENACH"

class FailureClass(StrEnum):
    SOFT_LIQUIDITY = "SOFT_LIQUIDITY"
    HARD_TERMINAL = "HARD_TERMINAL"
    TECHNICAL_RETRYABLE = "TECHNICAL_RETRYABLE"
    AMBIGUOUS_DECLINE = "AMBIGUOUS_DECLINE"
    LEGAL_HOLD = "LEGAL_HOLD"

class ActionType(StrEnum):
    # Primary Mutually-Exclusive Recovery Interventions
    SILENT_RETRY = "SILENT_RETRY"
    PIN_PROMPTED_RETRY = "PIN_PROMPTED_RETRY"
    PAYMENT_LINK = "PAYMENT_LINK"
    WHATSAPP_NUDGE = "WHATSAPP_NUDGE"
    SMS_NUDGE = "SMS_NUDGE"
    RE_MANDATE_FLOW = "RE_MANDATE_FLOW"
    COOLDOWN_WAIT = "COOLDOWN_WAIT"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    ABORT_COMPLIANT = "ABORT_COMPLIANT"
    
    # Mandatory Co-Occurring Regulatory Notifications (RBI Obligations)
    # Note: These are compliance obligations, not recovery interventions.
    # They co-occur with primary actions rather than competing in the feasible set.
    SEND_PRE_DEBIT_NOTICE = "SEND_PRE_DEBIT_NOTICE"      # Must fire >=24h before any debit execution
    SEND_POST_TXN_NOTICE = "SEND_POST_TXN_NOTICE"        # Must fire after every attempt (success or failure)

class MandateStateRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    case_id: str = Field(description="Unique synthetic case reference")
    mandate_id: str
    rail: PaymentRail
    amount_inr: float = Field(gt=0.0)
    attempt_count: int = Field(ge=1, le=4)
    failure_code: str
    failure_class: FailureClass
    failure_timestamp: datetime
    afa_required: bool
    ground_truth_recoverable: bool
```

---

## 3. Testing & Compliance Invariant Verification (Pytest)

The Compliance Violation Rate (CVR) must be **$0.0\%$ by construction**. The test suite uses exhaustive parameterized property-based tests via `pytest` to verify that no execution path can violate any regulatory boundary.

### 3.1 Required Pytest Invariant Test Matrix

| Test Suite File | Tested Invariant | Verification Condition |
|---|---|---|
| `test_attempt_limiter.py` | NPCI Max 4 Attempts | Assert attempting at $k=4$ with prior failure raises `IllegalActionException` or prunes all retry actions from feasible set. |
| `test_spacing_validator.py` | NPCI Spacing (24h/72h/168h) | Parameterize $\Delta t \in [0, 23\text{h}]$ for $k=2$; assert all executions are rejected and queued. |
| `test_window_mask.py` | NPCI Non-Peak IST Windows | Parameterize execution timestamps across all 24 hours. Assert hours in $[10:00, 13:00)$ and $[17:00, 21:30)$ are masked out. |
| `test_contact_gate.py` | RBI FPC 8AM–7PM Gate | Parameterize contact dispatch times. Assert dispatches at 07:59 or 19:01 are held until 08:00 AM local time. |
| `test_afa_enforcer.py` | RBI ₹15,000 AFA Rule | Test amounts $\le 15000$ (allow `SILENT_RETRY`) and $> 15000$ (strictly mask out `SILENT_RETRY`). |
| `test_legal_hold_filter.py` | e-NACH Code `07` | Given failure code `07`, assert `A_feasible == {ActionType.ESCALATE_HUMAN}` with zero automated outreach. |

---

## 4. Quantitative Evaluation Formulation

The evaluation harness processes a labeled batch of $N$ synthetic failure records and outputs an objective score card.

### 4.1 Net Recovery Rate (NRR)

$$\text{NRR}_{\text{INR}} = \sum_{i \in \text{Recovered}} \text{Amount}_i$$

$$\text{NRR}_{\%} = \frac{\sum_{i \in \text{Recovered}} \text{Amount}_i}{\sum_{i=1}^{N} \text{Amount}_i} \times 100$$

### 4.2 False Escalation Rate (FER)
Measures the proportion of human-escalated cases that were actually recoverable via compliant automation, scored against the hidden `ground_truth_recoverable` label:

$$\text{FER} = \frac{|\{i : A_i = \text{ESCALATE\_HUMAN} \land \text{ground\_truth\_recoverable}_i = \text{True}\}|}{|\{i : A_i = \text{ESCALATE\_HUMAN}\}|}$$

* **Target:** $\text{FER} \le 5.0\%$.

### 4.3 Compliance Violation Rate (CVR)
Tracks any action executed outside legal bounds:

$$\text{CVR} = \frac{|\{(i,k) : A_{i,k} \text{ violates any regulatory constraint}\}|}{|\{(i,k) : \text{Action Executed}\}|} \equiv 0.000\%$$

* **Target:** Exactly **$0.000\%$** (Hard test failure if $> 0$).

### 4.4 Diagnostic Confusion Matrix & Legal-Hold Recall
The multi-class confusion matrix evaluates predicted failure class vs. ground truth. Legal-Hold Recall is tracked as a standalone zero-tolerance metric:

$$\text{Recall}_{\text{Legal}} = \frac{\text{True Positives}_{\text{Legal}}}{\text{True Positives}_{\text{Legal}} + \text{False Negatives}_{\text{Legal}}} \equiv 1.000$$

### 4.5 Abort-Compliant Decision Rule
When the maximum expected net recovery across all legally permitted actions falls below the confidence threshold $\theta_{\text{confidence}}$:

$$\max_{A \in A_{\text{feasible}}(S)} \mathbb{E}[\text{Net Recovery}(S, A)] < \theta_{\text{confidence}} \implies A^* = \text{ABORT\_COMPLIANT}$$
