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

## 4. Data Provenance & Statistical Choice (Option A)

### 4.1 Dataset Composition (5,000 Records)
- **Source Dataset:** `data/synthetic_batch_5000.jsonl` (SHA-256: `31ac6bde15b1...`)
- **Train/Test Split:** 80% Train (\( N=4,000 \)), 20% Held-Out Test (\( N=1,000 \)), stratified by `failure_class` with fixed seed `42`.
- **Case ID Persistence:** Full train and test case IDs and split indices are serialized in `src/ml/models/metadata.json`.

### 4.2 Statistical Imbalance Strategy: Option (A)
- **Rare-Class Oversampling:** In the synthetic dataset generation, `LEGAL_HOLD` cases (codes `07`, `AP03`) are explicitly guaranteed at \( N \ge 100 \) instances (~2% of the dataset). This ensures the 20% held-out test set contains \( N=140 \) cases for statistically stable evaluation.
- **Loss Function Setting:** The model is trained with `class_weight=None`. This avoids double-weighting penalties on top of sample-level oversampling.
- **Honesty Note:** The ~2% prevalence of `LEGAL_HOLD` in this dataset is an explicit **evaluation-stability adjustment**, not an empirical claim of real-world base rate (which is modeled at ~1–2% in `docs/research/flaw_b_dossier.md §C.3`).

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
| \( C = 0.01 \) | 0.9400 | \(\pm 0.0118\) | |
| \( C = 0.10 \) | 0.9541 | \(\pm 0.0054\) | |
| \( C = 0.50 \) | 0.9560 | \(\pm 0.0039\) | |
| **\( C = 1.00 \)** | **0.9560** | **\(\pm 0.0037\)** | **Selected Optimal** |
| \( C = 5.00 \) | 0.9559 | \(\pm 0.0035\) | |
| \( C = 10.00 \) | 0.9559 | \(\pm 0.0035\) | |

### 6.2 Held-Out Test Evaluation (\( N=1,000 \))

- **Accuracy:** `92.10%`
- **ROC-AUC:** `0.9563`
- **PR-AUC:** `0.7126`
- **Macro F1:** `0.7834`
- **Weighted F1:** `0.9198`
- **Brier Score Loss:** `0.0501` (lower is better; strong probabilistic calibration)
- **Expected Calibration Error (ECE, 10 bins):** `0.0198` (< 2.0% calibration error)
- **Confusion Matrix:**
  - True Negative (TN): `859`
  - False Positive (FP): `36`
  - False Negative (FN): `43`
  - True Positive (TP): `62`

### 6.3 Per-Failure-Class Slice Breakdown (Held-Out Test Set)

| Failure Class | Sample Size (\( N \)) | Mean Predicted \( P \) | Slice F1 Score | Sizing Flag |
|---|---|---|---|---|
| `AMBIGUOUS_DECLINE` | \( N = 126 \) | `0.1001` | `0.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `HARD_TERMINAL` | \( N = 448 \) | `0.0019` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `LEGAL_HOLD` | \( N = 140 \) | `0.0045` | `1.0000` | Statistically sufficient (\( N \ge 20 \)) |
| `SOFT_LIQUIDITY` | \( N = 174 \) | `0.2619` | `0.4750` | Statistically sufficient (\( N \ge 20 \)) |
| `TECHNICAL_RETRYABLE` | \( N = 112 \) | `0.4873` | `0.7748` | Statistically sufficient (\( N \ge 20 \)) |

**Sanity Check Result:**
Across all \( N=140 \) held-out `LEGAL_HOLD` test instances, maximum predicted probability is `0.0348` and mean is `0.0045` (both strictly \( < 0.05 \)).

---

## 7. Model Monitoring & Retraining Triggers (SR 11-7)

- **Responsible Owner:** Lead ML Engineer / Revenue Recovery Operations
- **Monitoring Cadence:** Weekly automated drift analysis on live inference logs.
- **Formal Retraining Triggers:**
  1. **Population Stability Index (PSI) Drift:** Feature distribution PSI \( > 0.25 \) across a 14-day rolling window.
  2. **Calibration Degradation:** Rolling Brier Score degradation \( > 0.05 \) relative to the validation baseline.
  3. **Regulatory Change:** Any amendment to NPCI attempt caps, spacing windows, or AFA thresholds triggers an immediate feature pipeline review and model retraining.
