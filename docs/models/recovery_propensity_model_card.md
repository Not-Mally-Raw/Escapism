# Model Card: Recovery Propensity Estimator (`src/ml/`)
### Model Version: `1.0.0` | Sourcing Key: 🟢 Verified / Measured | 🟡 Literature-Derived | 🔴 Modeled Assumption / Illustrative

---

## 1. Model Overview & Architecture

- **Model Type:** Scikit-learn Pipeline (`ColumnTransformer` + `LogisticRegression`)
- **Task:** Binary probability estimation of payment recovery propensity: \( P(\text{recovery} = 1 \mid \mathbf{x}) \in [0.0, 1.0] \).
- **Target Definition:** `GroundTruthLabel.ground_truth_recoverable` (boolean). Evaluates whether a failed recurring mandate would successfully recover under optimal retry/nudge presentation.
- **Input Representation:** Fixed 14-dimensional feature vector extracted exclusively from observable `MandateStateRecord` domain attributes.
- **Serialization:** `src/ml/models/recovery_propensity_pipeline.joblib` (SHA-256: `170bac42fea7c50bab4fc6aa5305d703f7a065c451cf7e1acfa8dd5802ad9205`) and `src/ml/models/metadata.json`.

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

## 3. Architecture Selection & Trade-Off Matrix

> [!NOTE]
> **Methodological Disclosure:**
> We did not train the alternative architectures on this dataset to produce a head-to-head empirical comparison — the selection of Logistic Regression was made on documented ML-literature properties (probabilistic calibration behavior, exact coefficient auditability, sample efficiency at $N=5,000$) rather than an empirical bake-off. This is disclosed rather than implied, consistent with this project's sourcing discipline.

| Architecture Option | Probabilistic Calibration | SR 11-7 Auditability | Empirical Latency (P50 / P95) | Selection Assessment |
|---|---|---|---|---|
| **Logistic Regression (Selected)** | 🟢 **ECE = 0.0372** (measured from this project's run; direct sigmoid log-odds) | 🟢 **Exact linear coefficients** (direct odds ratios, monotonic, fully inspectable) | 🟢 **0.598 ms / 0.743 ms** (measured on Apple Silicon over $N=1,000$ calls) | **CHOSEN:** Optimal for EV ranking math, zero calibration drift, microsecond latency. |
| **Gradient Boosted Trees (XGBoost / LightGBM)** | 🟡 **Requires post-hoc calibration** (literature: tree leaf outputs are non-calibrated margin scores) | 🟡 **SHAP approximations** (non-linear interactions obscure exact regulatory boundaries) | 🔴 *~5–20 ms* (illustrative literature range; not benchmarked on this system) | **DEFERRED:** Additional complexity without calibration guarantees for EV formula. |
| **Deep Neural Network (MLP)** | 🟡 **Poor calibration** (literature: overconfident on unregularized modern softmax) | 🟡 **Black box** (gradient attribution methods required for auditability) | 🔴 *~10–50 ms* (illustrative literature range; not benchmarked on this system) | **REJECTED:** Sample inefficient for $N=5,000$ tabular features; high audit overhead. |
| **Direct LLM Zero-Shot Probability** | 🟡 **Non-calibrated verbally** (literature: LLM token likelihoods do not reflect true base rates) | 🟡 **Non-deterministic prompt drift** (stochastic output variation under identical state) | 🔴 *~800–3000 ms* (illustrative literature range; API roundtrip overhead) | **REJECTED:** LLMs are reserved for semantic diagnosis (Track 2), never numeric scoring. |

---

## 4. The Guardrail-Precedence Invariant

> [!IMPORTANT]
> **A model misprediction is NEVER a regulatory compliance exposure.**
>
> In this architecture, Problem A (legal compliance) is physically and logically separated from Problem B (revenue optimization):
> 1. The deterministic **Guardrail Engine (`src/guardrails/engine.py`)** runs *first*. For any legal hold (code `07` or `AP03`), the guardrail engine unconditionally collapses the feasible action set to `{ActionType.ESCALATE_HUMAN}`.
> 2. The ML model is only consulted to rank actions *within the already-pruned feasible set*.
>
> If this ML model were to assign a high recovery probability (e.g., \( P = 0.90 \)) to a `LEGAL_HOLD` case, that would be a **model-quality defect**, not a compliance violation, because the guardrail engine has already structurally eliminated all automated recovery actions from the feasible set upstream.

---

## 5. Data Provenance & Class Balance (Option A)

### 5.1 Calibrated Failure-Class Population Breakdown (5,000 Records)
The 5,000-case dataset (`data/synthetic_batch_5000.jsonl`, SHA-256: `90b2d59a5d9610bb4e5cb77e0e5c96f7ac3990c559ab9066d9d76089620678df`) uses calibrated failure-class weights derived from `docs/research/flaw_b_dossier.md §C.3`:

| Failure Class | Full Dataset \( N \) | Population % | Test Set Support (\( N \)) | Statistically Sufficient (\( N \ge 20 \)) |
|---|---|---|---|---|
| `SOFT_LIQUIDITY` | **3,016** | **60.32%** | \( N = 603 \) | Yes |
| `AMBIGUOUS_DECLINE` | **699** | **13.98%** | \( N = 140 \) | Yes |
| `TECHNICAL_RETRYABLE` | **647** | **12.94%** | \( N = 129 \) | Yes |
| `HARD_TERMINAL` | **535** | **10.70%** | \( N = 107 \) | Yes |
| `LEGAL_HOLD` | **103** | **2.06%** | \( N = 21 \) | **Yes (\( N \ge 20 \) satisfied)** |

### 5.2 Statistical Imbalance Strategy: Option (A)
- **Rare-Class Quota:** `LEGAL_HOLD` cases (codes `07`, `AP03`) are explicitly set at exactly \( N = 103 \) instances (2.06% of the dataset), yielding \( N = 21 \) cases in the 20% held-out test set (\( N \ge 20 \) satisfied).
- **Loss Function Setting:** The model is trained with `class_weight=None` to avoid artificial double-weighting penalties on top of sample-level representation.
- **Honesty Note:** The 2.06% prevalence of `LEGAL_HOLD` in this dataset is an explicit **evaluation-stability adjustment**, not an empirical claim of real-world base rate.

---

## 6. Feature Engineering & Banned Fields (PCI-DSS)

### 6.1 Observable Features

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

### 6.2 Banned Fields & Anti-Leakage Invariants
- **Anti-Leakage (Anti-Circularity):** Any presence of `ground_truth_recoverable` or related ground-truth label fields in the inference dictionary raises an immediate `ValueError`.
- **PCI-DSS & Privacy Protection:** Raw Primary Account Numbers (PAN), CVVs, customer VPAs, bank account numbers, and customer phone numbers are strictly prohibited from entering the feature matrix.

---

## 7. Quantitative Performance & Evaluation

### 7.1 Hyperparameter Tuning (5-Fold Stratified CV on Train Split)

| Regularization Parameter \( C \) | Mean CV ROC-AUC | Std CV ROC-AUC | Selection |
|---|---|---|---|
| \( C = 0.01 \) | 0.7168 | \(\pm 0.0200\) | |
| \( C = 0.10 \) | 0.7268 | \(\pm 0.0214\) | |
| \( C = 0.50 \) | 0.7274 | \(\pm 0.0208\) | |
| **\( C = 1.00 \)** | **0.7277** | **\(\pm 0.0205\)** | **Selected Optimal** |
| \( C = 5.00 \) | 0.7277 | \(\pm 0.0204\) | |
| \( C = 10.00 \) | 0.7276 | \(\pm 0.0203\) | |

### 7.2 Held-Out Test Evaluation (\( N=1,000 \))

- **Accuracy:** `74.40%`
- **ROC-AUC:** `0.7300`
- **PR-AUC:** `0.5223`
- **Macro F1:** `0.5808`
- **Weighted F1:** `0.6938`
- **Brier Score Loss:** `0.1738` (well-calibrated across probabilistic recovery spectra)
- **Expected Calibration Error (ECE, 10 bins):** `0.0372` (< 3.8% calibration error)
- **Confusion Matrix:**
  - True Negative (TN): `684`
  - False Positive (FP): `32`
  - False Negative (FN): `224`
  - True Positive (TP): `60`

### 7.3 Per-Failure-Class Slice Breakdown (Held-Out Test Set)

| Failure Class | Sample Size (\( N \)) | Mean Predicted \( P \) | Slice F1 Score | Sizing Flag |
|---|---|---|---|---|
| `AMBIGUOUS_DECLINE` | \( N = 140 \) | `0.1009` | `0.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `HARD_TERMINAL` | \( N = 107 \) | `0.0057` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `LEGAL_HOLD` | \( N = 21 \) | `0.0174` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `SOFT_LIQUIDITY` | \( N = 603 \) | `0.3069` | `0.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `TECHNICAL_RETRYABLE` | \( N = 129 \) | `0.5654` | `0.7186` | Statistically sufficient (\( N \ge 20 \)) |

**Sanity Check Result:**
Across all \( N=21 \) held-out `LEGAL_HOLD` test instances, maximum predicted probability is `0.0269` and mean is `0.0174` (both strictly \( < 0.05 \)).

### 7.4 Empirical Inference Latency Benchmark (Measured on Apple Silicon, \( N=1,000 \) Calls)

- **Mean Latency:** `0.618 ms`
- **Median Latency (P50):** `0.598 ms`
- **P95 Latency:** `0.743 ms`
- **P99 Latency:** `0.856 ms`
- **Min / Max Latency:** `0.574 ms / 2.388 ms`

---

## 8. Model Monitoring & Retraining Triggers (SR 11-7)

- **Responsible Owner:** Lead ML Engineer / Revenue Recovery Operations
- **Monitoring Cadence:** Weekly automated drift analysis on live inference logs.
- **Formal Retraining Triggers:**
  1. **Population Stability Index (PSI) Drift:** Feature distribution PSI \( > 0.25 \) across a 14-day rolling window.
  2. **Calibration Degradation:** Rolling Brier Score degradation \( > 0.05 \) relative to the validation baseline.
  3. **Regulatory Change:** Any amendment to NPCI attempt caps, spacing windows, or AFA thresholds triggers an immediate feature pipeline review and model retraining.
