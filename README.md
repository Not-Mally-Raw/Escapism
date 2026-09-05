# Escapism: Autonomous Revenue Recovery Engine
### Compliance-Gated Machine Learning for Mandate & UPI AutoPay Subscriptions
*Command Center for Failed Payments · PS3 · Track 03 · Flaw B: Mandate & UPI AutoPay Debit Recovery*

> *Every month, subscription debits burn capital in blind retries, statutory penalties, and uncoordinated outreach. Escapism replaces guesswork with deterministic regulatory gating and calibrated expected value optimization.*

---

![Tests Passing](https://img.shields.io/badge/Tests-169%2F169%20Passing-00FF88?style=flat-square)
![Compliance Violation Rate](https://img.shields.io/badge/CVR-0.000%25%20(Proven)-00FF88?style=flat-square)
![Net Recovered Revenue](https://img.shields.io/badge/NRR-₹29.15M%20(+24.3%25)-FF6600?style=flat-square)
![Inference Latency](https://img.shields.io/badge/P50%20Latency-0.598ms-00BFFF?style=flat-square)
![False Escalation Rate](https://img.shields.io/badge/FER-4.2%25-00BFFF?style=flat-square)
![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-white?style=flat-square)

---

## Executive Summary: The Core Empirical Finding

Subscription recovery in India is constrained by stringent Reserve Bank of India (RBI) and National Payments Corporation of India (NPCI) directives. When recurring debits fail across UPI AutoPay and e-NACH rails, industry-standard billing platforms resort to **"Blind Retries"**—firing uncoordinated debit attempts until success or banking suspension.

Using **Self-Normalized Inverse Propensity Scoring (SNIPS)** over 5,000 audited mandate lifecycles, this engine proves that **Blind Retries are actively net-negative in compliance-sensitive segments**:
* **HARD_TERMINAL** (Account closed / frozen): Blind retries lose **-₹267,527** in wasted gateway fees and regulatory penalties.
* **LEGAL_HOLD** (Court injunction / stop-order): Blind retries lose **-₹51,505** in statutory debit violations.

By implementing a deterministic **"Law Before Math"** governor, the **Razorpay V6 Engine** structurally zeros out compliance penalties while applying calibrated ML Lift-EV optimization on viable recoveries.

| Policy | Net Revenue Recovered (NRR) | 95% Confidence Interval | Compliance Fines Incurred | Uplift vs Blind Retry |
| :--- | :---: | :---: | :---: | :---: |
| **Policy 1: Passive Baseline (NOOP)** | ₹18,606,782 | [₹17.82M – ₹19.41M] | ₹0 | -20.7% |
| **Policy 2: Naive Blind Retry** | ₹23,463,331 | [₹22.58M – ₹24.31M] | -₹319,032 | 0.0% (Baseline) |
| **Policy 3: V6 Autonomous Engine** | **₹29,154,368** | **[₹28.24M – ₹30.08M]** | **₹0** | **+₹5.69M (+24.3%)** |

---

## 3-Step Ingestion & Deployment

Get the entire V6 Engine, API Gateway, and Recovery Console running in under 60 seconds:

```bash
# Step 1: Clone repository and activate environment
git clone https://github.com/Not-Mally-Raw/Razorpay-Escapism-Track-03.git
cd Razorpay-Escapism-Track-03
python3 -m venv .venv && source .venv/bin/activate

# Step 2: Install dependencies in editable mode
pip install -e .

# Step 3: Launch the V6 Engine & Interfaces
python3 src/api/server.py
```

### Access Points
* **Console Interface:** [http://localhost:8000](http://localhost:8000) — Full keyboard-driven Recovery Console UI (`F1`–`F8` navigation, live telemetry, and instant simulation).
* **Product Overview & ROI Calculator:** [http://localhost:8000/landing](http://localhost:8000/landing) — Interactive enterprise presentation, live ARR recovery calculator, and architecture breakdown.
* **Reproduce SNIPS Benchmark:**
  ```bash
  python3 scripts/run_monte_carlo.py
  ```
  Executes 1,000 bootstrap iterations over logged synthetic outcomes using Self-Normalized Inverse Propensity Scoring (SNIPS) with full 95% CI calculation.

---

## V6 Engine Pipeline Architecture

The V6 Engine separates **legal authorization** from **economic optimization** into six discrete, fail-closed cylinders:

<div align="center">
  <img src="./docs/v6_engine_architecture.png" alt="Razorpay V6 Engine Architecture" width="820" style="border: 1px solid #333; border-radius: 8px;" />
</div>

---

## The 6 Cylinders of the V6 Engine

### V1 · Intake & Idempotency (`src/ingestion/gateway.py`)
* **Cryptographic Ingestion:** `POST /webhook/razorpay` verifies incoming webhooks using constant-time `hmac.compare_digest()` against the merchant secret (`X-Razorpay-Signature`).
* **Deduplication Gate:** Validates unique `x-razorpay-event-id` against the `seen_events` ledger in SQLite WAL mode. Duplicate deliveries receive an immediate HTTP 202 without re-triggering execution.
* **Durable Ingestion:** Persists clean events into an append-only `inbox` queue with `status=PENDING` before any processing begins.

### V2 · Diagnostic Cascade (`src/decision/classifier.py`)
* **Tier 1 (Deterministic Lookup):** High-speed O(1) evaluation covering 16 standard bank failure codes (`Z9`, `U28`, `07`, `01`–`06`). Handles **82% of all volume at 0ms latency** with 100% confidence and zero LLM cost.
* **Tier 2 (Missing-Text Gate):** Catches ambiguous bank codes (`U19`, `U30`) lacking raw bank telemetry, classifying them as `AMBIGUOUS_DECLINE` without wasting model tokens.
* **Tier 3 (Cascaded LLM Diagnostic):** For unknown or unstructured failure strings, an LLM extracts semantic root cause with **OWASP LLM01:2025** safeguards: strict PII scrubbing (PAN, VPA, phone, account), prompt injection boundary isolation, and rigid Pydantic schema validation.
* **Fail-Closed Guard:** Any unhandled exception or unverified token immediately falls back to `ESCALATE_HUMAN`—no unknown error is ever blindly retried.

### V3 · Compliance Kernel / Governor (`src/guardrails/`)
> **"Law Before Math":** Probabilistic models are strictly forbidden from deciding whether an action is legal. The Compliance Kernel computes the feasible action set A_feasible before the optimizer evaluates EV.
* **Gate 0 (Legal Hold Short-Circuit):** Injunction codes (`07`, `AP03`) or unrecognized decline strings bypass scoring entirely and route to manual review.
* **M1 (NPCI Attempt Limiter):** Hard caps debit attempts at k <= 4. Attempts 4+ disqualify automated debit retries.
* **M2 (Spacing Validator):** Mandates minimum cooling intervals: delta_t2 >= 24h, delta_t3 >= 72h, delta_t4 >= 168h. Fail-closed on missing timestamps.
* **M3 (RBI AFA Enforcer):** Subscriptions > ₹15,000 strictly disqualify `SILENT_RETRY`. Recovery is restricted to two-factor paths (`PIN_PROMPTED_RETRY`, `PAYMENT_LINK`).
* **M4 & M5 (Window & Contact Mask):** Restricts automated debits to NPCI non-peak clearing cycles and customer outreach to RBI-approved hours (08:00–19:00 local).
* **M6 & M7 (Consent & Notice Enforcer):** Gated by DPDP Act customer consent (`OPTED_IN` only) and verifies that an RBI-mandated pre-debit notification was dispatched >= 24h prior.
* **Result:** **Compliance Violation Rate (CVR) = 0.000% by construction.**

### V4 · ML Propensity Pipeline (`src/ml/pipeline.py`)
* **Three-Profile Lineage:** Calibrated across three rigorous validation profiles, culminating in **Profile 3 (Certified Production Baseline)** trained exclusively on unconfounded passive recovery outcomes (Y0 ~ Bernoulli(mu_0(S))).
* **Deterministic Training:** 100% reproducible training loop (`random_seed=42`) with cryptographic SHA256 integrity linking dataset, joblib weights, and model metadata.
* **Performance Metrics (Held-Out N=1,000):**
  * **Accuracy:** 74.4% · **ROC-AUC:** 0.7300 · **PR-AUC:** 0.5223
  * **Expected Calibration Error (ECE):** 0.0372 (well-calibrated across all 10 deciles)
  * **Inference Latency:** P50 = 0.598ms · P95 = 0.743ms
* **Causal Uplift Research:** Includes a multi-arm T-Learner gradient-boosted uplift model (`uplift.py`). In accordance with conservative governance, static multiplier Lift-EV is certified as production default until customer arm logging reaches balance.

### V5 · Lift-EV Optimizer (`src/decision/optimizer.py`)
* **Lift-EV Objective Formulation:**
  $$\text{Lift-EV}(a \mid S) = \hat{P}(S) \cdot \Delta P(a) \cdot \text{Amount} - C(a)$$
  Where $\Delta P(a) = m(a) - 1.0$, $m(a)$ is the empirical channel uplift multiplier, and $C(a)$ is the modeled channel cost.
* **Realistic Cost & Multiplier Table:**
  * `SILENT_RETRY`: Multiplier 1.00 · Cost ₹0.05
  * `PIN_PROMPTED_RETRY`: Multiplier 1.05 · Cost ₹0.10
  * `SMS_NUDGE`: Multiplier 1.10 · Cost ₹0.50
  * `PAYMENT_LINK`: Multiplier 1.15 · Cost ₹0.75
  * `WHATSAPP_NUDGE`: Multiplier 1.20 · Cost ₹0.80
  * `ESCALATE_HUMAN`: Cost ₹50.00 (Hurdle: theta_human = ₹25.00)
* **Hurdle Gating:** Digital actions require Lift-EV >= theta_digital = ₹1.00. If all actions yield negative EV, the engine aborts to preserve capital.

### V6 · Replay-Safe Dispatch & Policy Evaluation (`src/execution/worker.py`)
* **Two-Phase Commit Boundary:** Durable execution intents (`record_execution_intent`) are committed to SQLite before any API call is dispatched. Replay on crash resumes safely without duplicate payments.
* **Omnichannel Dispatch:** Seamlessly dispatches WhatsApp webhooks, SMS gateways, and Razorpay Payment Link APIs with idempotent request headers.
* **Dead Letter Queue (DLQ):** Exponential backoff ($t = \min(1.0 \times 2^{r-1}, 60\text{s})$) with automatic dead-letter transitions after 3 failed gateway attempts.
* **Audit Ledger:** Append-only SQLite audit log recording raw event ID, state vector, diagnostic reason, feasible action set, candidate EV matrix, model SHA256, and gateway receipts.

---

## Rigorous Model Lineage

| Attribute | Profile 1 (Exploration) | Profile 2 (Causal Shift) | Profile 3 (Certified Production) |
| :--- | :---: | :---: | :---: |
| **Dataset SHA-256** | `40f623dd...` | `4f4e09e2...` | `90b2d59a562ca61c31da64a9386d34e9...` |
| **Model Artifact SHA-256** | `8b3a12cd...` | `c92e10fb...` | `170bac42dbd8e16a2aa5391a847f98b9...` |
| **Target Formulation** | Policy-conditioned | Confounded treatment | **Unconfounded Passive Baseline (Y0)** |
| **Accuracy / ROC-AUC** | 80.1% / 0.875 | 72.1% / 0.761 | **74.4% / 0.7300** |
| **Expected Calibration Error** | 0.0812 | 0.0540 | **0.0372 (Certified Well-Calibrated)** |
| **Deployment Status** | Superseded | Archived | **Active Production Default** |

---

## Comprehensive Verification Suite

The repository contains an automated test battery with 100% pass rate:

```bash
.venv/bin/pytest -v
```

```
============================== test session starts ==============================
platform darwin -- Python 3.13.1, pytest-8.3.4, pluggy-1.5.0
rootdir: /Users/spandankewte/Downloads/razorpay-revenue-recovery
collected 169 items

tests/unit/test_api_server.py ..................                          [ 10%]
tests/unit/test_batch_generator.py ........                               [ 15%]
tests/unit/test_causal_evaluator.py .......                               [ 19%]
tests/unit/test_classifier.py ....................                        [ 31%]
tests/unit/test_data_leakage.py ....                                     [ 33%]
tests/unit/test_decision_optimizer.py .........................           [ 48%]
tests/unit/test_distributions.py ........                                 [ 53%]
tests/unit/test_features.py ..........                                    [ 59%]
tests/unit/test_guardrails.py ....................                        [ 71%]
tests/unit/test_model_pipeline.py ......                                  [ 74%]
tests/unit/test_razorpay_client.py ..........                             [ 80%]
tests/unit/test_uplift.py ......                                          [ 84%]
tests/unit/test_worker.py ...........................                     [100%]

============================== 169 passed in 4.52s ==============================
```

---

## Repository Organization

```
razorpay-revenue-recovery/
├── docs/                                  # Architectural specifications & model cards
│   ├── v6_engine_architecture.png         # High-resolution V6 Architecture Diagram (Retina)
│   ├── v6_engine_architecture.svg         # Clean vector source diagram (XML validated)
│   ├── architecture.md                    # In-depth architectural treatise & mathematical formulas
│   └── models/
│       └── recovery_propensity_model_card.md # Audited Profile 3 model governance card
├── src/
│   ├── ingestion/
│   │   └── gateway.py                     # Webhook intake, HMAC auth, deduplication, SQLite inbox
│   ├── decision/
│   │   ├── classifier.py                  # 3-tier failure classification cascade (0ms O(1) + LLM)
│   │   └── optimizer.py                   # Lift-EV candidate scoring matrix & threshold gating
│   ├── guardrails/                        # Deterministic compliance kernel (M1–M7 policies)
│   ├── ml/
│   │   ├── pipeline.py                    # Inference pipeline, feature encoding, calibration
│   │   ├── train.py                       # Profile 3 training harness & calibration verification
│   │   └── models/                        # Serialized model artifacts (.joblib) & metadata.json
│   ├── execution/
│   │   ├── worker.py                      # Replay-safe background consumer & two-phase commit intents
│   │   └── razorpay_client.py             # Mock & live Razorpay API client
│   └── api/
│       ├── server.py                      # FastAPI server exposing telemetry, simulation, endpoints
│       └── static/
│           ├── index.html                 # Escapism Recovery Console UI (Keyboard-driven F1–F8)
│           └── landing.html               # High-converting enterprise marketing landing page
├── scripts/
│   └── run_monte_carlo.py                 # SNIPS offline policy evaluation benchmark (1,000 runs)
└── tests/                                 # 169 unit, integration, and chaos tests
```

---

## Regulatory Alignment & Compliance Reference

* **NPCI Circular NPCI/2024-25/NACH/008:** Restricts mandate debit retry frequency to a maximum of 4 attempts and mandates exponential retry backoff.
* **RBI Circular DPSS.CO.PD No. 1310/02.14.008/2020-21:** Governs AutoPay limits, requiring pre-debit notices >= 24h prior to execution and mandatory Additional Factor of Authentication (AFA) for transactions exceeding ₹15,000.
* **Digital Personal Data Protection (DPDP) Act 2023:** Enforces strict consent gating before sending omnichannel reminders across WhatsApp and SMS channels.

---

## License
Apache-2.0 License. Designed and engineered for high-volume recurring subscription businesses.
