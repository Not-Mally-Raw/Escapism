# Project: Razorpay Revenue Recovery Engine Stabilization & Hardening

## Architecture
- **Ingestion Boundary**: Sanitized webhook receiver and typed event adapter converting raw Razorpay payloads (`mandate.debit.failed`) into domain events with upstream failure diagnosis.
- **Decision Engine & Guardrails**: Deterministic decision optimization with default static multiplier Lift-EV path, opt-in CATE uplift, and strict property-tested safety invariants (`LEGAL_HOLD` / unknown codes -> `ESCALATE_HUMAN`).
- **Causal Simulation & ML Lineage**: Rigorous unconfounded data generation with complete potential outcomes, positivity bounds, retrained propensity model, and synchronized model card/metadata hashes.
- **Execution & Durability**: Replay-safe SQLite intent logging, idempotency key enforcement, bounded exponential backoff with DLQ transition, rich audit logs, and complete package dependency management.
- **Integration & Verification**: End-to-end flow validation, comprehensive pytest test suites (169 passed), benchmarks, and regression testing.

## Code Layout
- `src/ingestion/` & `tests/fixtures/`: Webhook fixtures & typed event adapters
- `src/decision/` & `src/guardrails/`: Decision optimizer, policy evaluator, compliance guardrails
- `src/simulation/` & `src/ml/`: Synthetic batch generator, propensity models, model training, metadata
- `src/execution/`: Razorpay client, worker retry/DLQ, execution intent, audit logging
- `tests/`: Unit, integration, property, and e2e test suites
- `docs/`: Model cards and architecture documentation

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Webhook Fixture | Sanitized `mandate.debit.failed` fixture with exact envelope nesting | M1 | R1 |
| 2 | Typed Event Adapter | Fail-closed parser validating schema, amounts, timestamps | M1 | R1 |
| 3 | Upstream Diagnosis | `diagnose_failure()` executed before `MandateStateRecord` | M1 | R1 |
| 4 | Worker Ingestion Normalization | Worker reads canonical events from inbox | M1 | R1 |
| 5 | Default Static Lift-EV | `use_uplift=False` certified default in `optimize_decision` | M2 | R2 |
| 6 | CATE Opt-In Validation | Explicit opt-in with non-inferiority evaluation | M2 | R2 |
| 7 | CATE Adversarial Tests | Dedicated tests under hostile cost tables | M2 | R2 |
| 8 | Structural Safety Invariants | `LEGAL_HOLD` and unknown codes route to `ESCALATE_HUMAN` | M2 | R2 |
| 9 | Property-based Compliance | Exhaustive property testing for safety codes | M2 | R2 |
| 10 | Unconfounded Synthetic Generator | Potential outcomes contract (`mu_0`, `tau`, `observed`) | M3 | R3 |
| 11 | Common Support & Positivity | Enforced propensity floor $\pi(a \mid S) \ge 0.05$ | M3 | R3 |
| 12 | Propensity Retraining | Retrain against unconfounded baseline outcomes | M3 | R3 |
| 13 | Training Threshold Consistency | Align assertion messages and thresholds (<0.15 vs <0.05) | M3 | R3 |
| 14 | Model Lineage Synchronization | Synchronize SHA256 hashes, metrics between metadata and model card | M3 | R3 |
| 15 | Replay-Safe Dispatch Intent | Record execution intent in SQLite before external API call | M4 | R4 |
| 16 | Idempotency Key Enforcement | `x-razorpay-event-id` header across retries | M4 | R4 |
| 17 | Deterministic Reconciliation | Outcome reconciliation for interrupted executions | M4 | R4 |
| 18 | Bounded Backoff & DLQ | Exponential backoff with `DEAD_LETTER` transition | M4 | R4 |
| 19 | Rich Audit Logging | Log raw event ID, diagnostics, scores, model hash, receipts | M4 | R4 |
| 20 | Dependency Packaging | Complete `pyproject.toml` and `requirements.txt` | M4 | R5 |
| 21 | System Boundary Documentation | Document mock execution and webhook intent dispatch | M4 | R5 |
| 22 | Contract & E2E Verification | Full pytest suite (169 passed), benchmarks, end-to-end lifecycle pass | M5 | Integration |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Event Boundary & Ingestion | R1 (`src/ingestion/`, fixtures, worker inbox normalization) | none | DONE |
| M2 | Guardrails & Decision Engine | R2 (`src/decision/`, `src/guardrails/`, decision unit tests) | none | DONE |
| M3 | Causal Simulation & ML Lineage | R3 (`src/simulation/`, `src/ml/`, `scripts/`, `data/`, model card) | none | DONE |
| M4 | Execution Reliability & Packaging | R4, R5 (`src/execution/`, retry/DLQ, packaging, docs) | M1 | DONE |
| M5 | Integration & E2E Hardening | Full verification, benchmarks, regression suites | M1, M2, M3, M4 | DONE |

## Interface Contracts
### Webhook Ingestion ↔ Worker
- Ingestion produces validated `MandateStateRecord` with `diagnosis` populated upstream.
- Worker consumes canonical events from inbox SQLite table.

### Decision Engine ↔ Worker / Execution
- `optimize_decision(state, use_uplift=False)` returns `DecisionOutput` with selected action, expected value, rationale.
- Legal holds and unknown codes bypass scoring and return `ESCALATE_HUMAN` with null `p_hat` and null `lift_ev_inr`.

### Simulation / ML ↔ Decision Engine
- Causal models trained with positivity bounds output calibrated recovery probabilities and uplift predictions.
- Metadata and model cards synchronize SHA256 provenance.

### Worker ↔ Razorpay Client / Gateway
- Execution intent logged prior to dispatch with `idempotency_key = event_id`.
- Terminal failures transition to `DEAD_LETTER` with structured audit logs.
