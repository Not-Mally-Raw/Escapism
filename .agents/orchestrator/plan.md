# Orchestrator Execution Plan

## Phase 1: Parallel Execution of Independent Modules
- **Milestone 1 (Agent 1 - Ingestion & Event Boundary)**:
  - Spawn Worker with Explorer/Reviewer cycle for R1 (`src/ingestion/`, webhook fixtures, worker event parsing normalization).
- **Milestone 2 (Agent 2 - Guardrails & Decision Engine)**:
  - Spawn Worker with Explorer/Reviewer cycle for R2 (`src/decision/`, `src/guardrails/`, `test_decision_optimizer.py`).
- **Milestone 3 (Agent 3 - Causal Simulation & ML Lineage)**:
  - Spawn Worker with Explorer/Reviewer cycle for R3 (`src/simulation/`, `src/ml/`, `scripts/run_monte_carlo.py`, `data/`, model card).

## Phase 2: Execution Engine & Packaging
- **Milestone 4 (Agent 4 - Execution Reliability & Packaging)**:
  - Depends on M1 (worker event normalization).
  - Implements R4 and R5 (`src/execution/razorpay_client.py`, retry/DLQ, idempotency, audit log, `pyproject.toml`, `requirements.txt`, docs).

## Phase 3: Integration & Full Verification
- **Milestone 5 (Integration Lead - Final Phase)**:
  - Merged contracts verification.
  - Full `pytest` execution across unit, property, integration, and e2e test suites.
  - Benchmark runs and end-to-end flow validation.
  - Final audit check and comprehensive reporting.
