# Model Card: Recovery Propensity Estimator (`src/ml/`)
### Model Version: `1.0.0` | Sourcing Key: 🟢 Verified Regulation | 🟡 Derived/Heuristic | 🔴 Modeled Assumption

---

## 1. Model Overview & Architecture

- **Model Type:** Scikit-learn Pipeline (`ColumnTransformer` + `LogisticRegression`)
- **Task:** Binary probability estimation of payment recovery propensity: \( P(\text{recovery} = 1 \mid \mathbf{x}) \in [0.0, 1.0] \).
- **Target Definition:** `GroundTruthLabel.ground_truth_recoverable` (boolean). Evaluates whether a failed recurring mandate would successfully recover under optimal retry/nudge presentation.
- **Input Representation:** Fixed 14-dimensional feature vector extracted exclusively from observable `MandateStateRecord` domain attributes.
- **Serialization:** `src/ml/models/recovery_propensity_pipeline.joblib` and `src/ml/models/metadata.json`.

---

## 2. Intended Use & Operational Limits (SR 11-7 Governance)

### 2.1 Intended Use
This model is used strictly by the downstream decision engine (Stage 4) to supply the probability term \( P_i \) in the locked expected net revenue optimization equation:
$$
\text{EV}(a) = P(\text{success} \mid \text{state}, a) \cdot \text{Amount} - \text{Cost}(a)
$$
The model scores feasible recovery candidates to rank which action maximizes expected recovered rupees.

### 2.2 Operational Limitations & Out-of-Scope Usage
- **No Execution Authority:** This model has **zero authority to execute transactions, dispatch nudges, or create payment links**.
- **No Compliance Authority:** This model **cannot override, relax, or expand the feasible action set**.
- **Synthetic Training Domain:** The current model is trained exclusively on synthetic data. Real-world deployment requires calibration against live bank webhook telemetry once historical outcomes are logged.
- **Synthetic Malformed Codes Note:** Malformed codes (`GARBAGE_99`, `UNKNOWN_CODE`, `XXX`) are included in the synthetic generator purely as synthetic noise for feature-pipeline robustness; in production, all uncatalogued codes are hard-gated to `ABORT_COMPLIANT` / `ESCALATE_HUMAN` by the fail-closed guardrail (`legal_hold_filter.py §3.4`), independent of model inference.

---

## 3. The Guardrail-Precedence Invariant

> [!IMPORTANT]
> **A model misprediction is NEVER a regulatory compliance exposure.**
>
> In this architecture, Problem A (legal compliance) is physically and logically separated from Problem B (revenue optimization):
> 1. The deterministic **Guardrail Engine (`src/guardrails/engine.py`)** runs *first*. For any legal hold (code `07` or `AP03`), the guardrail engine unconditionally collapses the feasible action set to `{ActionType.ESCALATE_HUMAN}`.
> 2. The ML model is only consulted to rank actions *within the already-pruned feasible set*.
>
> If this ML model were to assign a high recovery probability (e.g., \( P = 0.90 \)) to a `LEGAL_HOLD` case, that would be a **model-quality defect**, not a compliance violation, because the guardrail engine has already structurally eliminated all automated recovery actions from the feasible set upstream.

---

## 4. Data Provenance & Class Balance (Option A)

### 4.1 Calibrated Failure-Class Population Breakdown (5,000 Records)
The 5,000-case dataset (`data/synthetic_batch_5000.jsonl`, SHA-256: `5bad7debd03f...`) uses calibrated failure-class weights derived from `docs/research/flaw_b_dossier.md §C.3`:

| Failure Class | Full Dataset \( N \) | Population Proportion | Target Calibration Band |
|---|---|---|---|
| `SOFT_LIQUIDITY` | 2,921 | **58.42%** | ~55%–65% (dominant liquidity events) |
| `AMBIGUOUS_DECLINE` | 668 | **13.36%** | ~10%–15% (indeterminate bank codes) |
| `TECHNICAL_RETRYABLE` | 644 | **12.88%** | ~10%–15% (transient switch timeouts) |
| `HARD_TERMINAL` | 536 | **10.72%** | ~5%–10% (closed/blocked accounts) |
| `LEGAL_HOLD` | 231 | **4.62%** | Guaranteed \( N \ge 100 \) for test stability |

### 4.2 Statistical Imbalance Strategy: Option (A)
- **Rare-Class Quota:** `LEGAL_HOLD` cases (codes `07`, `AP03`) are guaranteed at \( N \ge 100 \) instances (resulting in \( N=231 \) across 5,000 cases), yielding \( N=46 \) cases in the 20% held-out test set (\( N \ge 20 \) satisfied).
- **Loss Function Setting:** The model is trained with `class_weight=None` to avoid artificial double-weighting penalties on top of sample-level representation.
- **Honesty Note:** The ~4.6% prevalence of `LEGAL_HOLD` in this dataset is an explicit **evaluation-stability adjustment**, not an empirical claim of natural base rate.

---

## 5. Feature Engineering & Banned Fields (PCI-DSS)

### 5.1 Observable Features

| Feature Name | Type | Processing | Sourcing Tag |
|---|---|---|---|
| `failure_class` | Categorical | OneHot (`handle_unknown='ignore'`) | 🟢 Canonical Taxonomy |
| `rail` | Categorical | OneHot (`handle_unknown='ignore'`) | 🟢 NPCI / RBI Domain |
| `consent_whatsapp` | Categorical | OneHot (`OPTED_IN`/`OPTED_OUT`/`UNKNOWN`) | 🔴 Modeled Assumption |
| `consent_sms` | Categorical | OneHot (`OPTED_IN`/`OPTED_OUT`/`UNKNOWN`) | 🔴 Modeled Assumption |
| `consent_payment_link` | Categorical | OneHot (`OPTED_IN`/`OPTED_OUT`/`UNKNOWN`) | 🔴 Modeled Assumption |
| `attempt_count` | Numeric (1–4) | StandardScaler | 🟢 NPCI Presentation Limit |
| `amount_inr` | Numeric | StandardScaler | 🟢 Transaction Principal |
| `afa_required` | Binary (0/1) | StandardScaler | 🟢 RBI ₹15,000 Threshold |
| `time_since_last_attempt_hours` | Numeric | StandardScaler | 🟢 NPCI Spacing Interval |
| `has_last_attempt` | Binary (0/1) | StandardScaler | 🟡 Derived Indicator |
| `pre_debit_notice_sent` | Binary (0/1) | StandardScaler | 🟢 RBI Mandate Obligation |
| `is_weekend` | Binary (0/1) | StandardScaler (IST) | 🟡 Derived Temporal |
| `hour_of_day` | Numeric (0–23) | StandardScaler (IST) | 🟡 Derived Temporal |
| `consent_score` | Numeric (0–3) | StandardScaler | 🟡 Derived Consent Count |

### 5.2 Banned Fields & Anti-Leakage Invariants
- **Anti-Leakage (Anti-Circularity):** Any presence of `ground_truth_recoverable` or related ground-truth label fields in the inference dictionary raises an immediate `ValueError`.
- **PCI-DSS & Privacy Protection:** Raw Primary Account Numbers (PAN), CVVs, customer VPAs, bank account numbers, and customer phone numbers are strictly prohibited from entering the feature matrix.

---

## 6. Quantitative Performance & Evaluation

### 6.1 Hyperparameter Tuning (5-Fold Stratified CV on Train Split)

| Regularization Parameter \( C \) | Mean CV ROC-AUC | Std CV ROC-AUC | Selection |
|---|---|---|---|
| \( C = 0.01 \) | 0.8518 | \(\pm 0.0029\) | |
| \( C = 0.10 \) | 0.8673 | \(\pm 0.0037\) | |
| \( C = 0.50 \) | 0.8728 | \(\pm 0.0068\) | |
| \( C = 1.00 \) | 0.8735 | \(\pm 0.0071\) | |
| \( C = 5.00 \) | 0.8741 | \(\pm 0.0076\) | |
| **\( C = 10.00 \)** | **0.8741** | **\(\pm 0.0076\)** | **Selected Optimal** |

### 6.2 Held-Out Test Evaluation (\( N=1,000 \))

- **Accuracy:** `78.20%`
- **ROC-AUC:** `0.8707`
- **PR-AUC:** `0.7039`
- **Macro F1:** `0.7531`
- **Weighted F1:** `0.7891`
- **Brier Score Loss:** `0.1295` (well-calibrated across probabilistic recovery spectra)
- **Expected Calibration Error (ECE, 10 bins):** `0.0298` (< 3.0% calibration error)
- **Confusion Matrix:**
  - True Negative (TN): `562`
  - False Positive (FP): `151`
  - False Negative (FN): `67`
  - True Positive (TP): `220`

### 6.3 Per-Failure-Class Slice Breakdown (Held-Out Test Set)

| Failure Class | Sample Size (\( N \)) | Mean Predicted \( P \) | Slice F1 Score | Sizing Flag |
|---|---|---|---|---|
| `AMBIGUOUS_DECLINE` | \( N = 134 \) | `0.1054` | `0.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `HARD_TERMINAL` | \( N = 107 \) | `0.0007` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `LEGAL_HOLD` | \( N = 46 \) | `0.0026` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `SOFT_LIQUIDITY` | \( N = 584 \) | `0.3408` | `0.5839` | Statistically sufficient (\( N \ge 20 \)) |
| `TECHNICAL_RETRYABLE` | \( N = 129 \) | `0.6529` | `0.9399` | Statistically sufficient (\( N \ge 20 \)) |

**Sanity Check Result:**
Across all \( N=46 \) held-out `LEGAL_HOLD` test instances, maximum predicted probability is `0.0076` and mean is `0.0026` (both strictly \( < 0.05 \)).

---

## 7. Model Monitoring & Retraining Triggers (SR 11-7)

- **Responsible Owner:** Lead ML Engineer / Revenue Recovery Operations
- **Monitoring Cadence:** Weekly automated drift analysis on live inference logs.
- **Formal Retraining Triggers:**
  1. **Population Stability Index (PSI) Drift:** Feature distribution PSI \( > 0.25 \) across a 14-day rolling window.
  2. **Calibration Degradation:** Rolling Brier Score degradation \( > 0.05 \) relative to the validation baseline.
  3. **Regulatory Change:** Any amendment to NPCI attempt caps, spacing windows, or AFA thresholds triggers an immediate feature pipeline review and model retraining.
