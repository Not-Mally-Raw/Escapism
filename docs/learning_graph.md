# Topological Learning & Dependency Graph
### System: AI Revenue Recovery (Track 03 — Flaw B: Mandate & UPI AutoPay Debits)

This graph specifies the strict build sequence and conceptual dependencies required to construct the revenue recovery engine. No higher-level component may be implemented until all its prerequisite nodes are fully defined and tested.

```mermaid
flowchart TD
    %% Stage 0: Knowledge Base
    subgraph S0 ["Stage 0: Ground Truth Knowledge Base"]
        K1["docs/knowledge_base/rbi_npci_regulations.md<br/>(4-Attempt Cap, Spacing, Non-Peak, AFA, FPC)"]
        K2["docs/knowledge_base/error_taxonomy.md<br/>(UPI U/Z Codes vs e-NACH 01-07/AP Codes)"]
        K3["docs/skills.md<br/>(Pydantic v2, Idempotency, Pytest Invariants)"]
    end

    %% Stage 1: Domain Data Models
    subgraph S1 ["Stage 1: Core Type System & Domain Schemas"]
        M1["src/core/types.py<br/>(Enums: ActionSpace, FailureClass, PaymentRail)"]
        M2["src/core/models.py<br/>(Pydantic v2: MandateState, TransactionRecord, AuditEntry)"]
        M3["src/core/config.py<br/>(Tunable Priors, Cost Tables, Confidence Threshold Theta)"]
    end

    %% Stage 2: Deterministic Guardrails (Zero Hallucination)
    subgraph S2 ["Stage 2: Deterministic Guardrail Engine"]
        G1["src/guardrails/attempt_limiter.py<br/>(Strict k <= 4 Invariant)"]
        G2["src/guardrails/spacing_validator.py<br/>(24h / 72h / 168h Spacing Backoff)"]
        G3["src/guardrails/window_mask.py<br/>(Non-Peak Execution Mask: IST Windows)"]
        G4["src/guardrails/contact_gate.py<br/>(RBI Fair Practices Code: 8AM-7PM Local Time)"]
        G5["src/guardrails/afa_enforcer.py<br/>(Amount > ₹15k Masks Out Silent Retry)"]
        G6["src/guardrails/legal_hold_filter.py<br/>(e-NACH Code 07 Instant Freeze)"]
        G7["src/guardrails/consent_gate.py<br/>(Per-Channel Consent Hard Mask, Fail-Closed)"]
        GE["src/guardrails/engine.py<br/>(Unified Guardrail Pre-Action Masker)"]
    end

    %% Stage 3: Ingestion & Diagnostic Classifier
    subgraph S3 ["Stage 3: Ingestion & Diagnostic Pipeline"]
        I1["src/ingestion/webhook_verifier.py<br/>(HMAC SHA-256 Signature Verification)"]
        I2["src/ingestion/idempotency.py<br/>(Atomic Event-ID Deduplication)"]
        D1["src/diagnostic/classifier.py<br/>(Dual-Rail Taxonomy Parser: UPI & e-NACH)"]
    end

    %% Stage 4: Decision & Optimization Layer
    subgraph S4 ["Stage 4: Constrained Decision Planner"]
        P1["src/decision/action_pruner.py<br/>(Applies Guardrail Engine as Hard Action Mask)"]
        P2["src/decision/net_recovery_model.py<br/>(Expected Value Optimization: P(Success)*Amount - Cost)"]
        P3["src/decision/agent.py<br/>(LLM Context Reasoner with Abort-Compliant Threshold)"]
        P4["[FUTURE] Failure-class-specific message tone<br/>(Citing: market_context.md §3.3 — tone varies by FailureClass)"]
    end

    %% Stage 5: Execution & Simulation Layer
    subgraph S5 ["Stage 5: Execution Simulator & Dispatcher"]
        E1["src/execution/payment_link_client.py<br/>(Razorpay Payment Link API Client/Mock)"]
        E2["src/execution/mandate_scheduler.py<br/>(Scheduled Debit Task Dispatcher)"]
        E3["src/execution/audit_logger.py<br/>(Append-Only Tamper-Evident State Logger)"]
        E4["[FUTURE] Webhook-state reconciliation job<br/>(Citing: market_context.md §3.2 — nightly drift detection)"]
    end

    %% Stage 6: Synthetic Data Generator
    subgraph S6 ["Stage 6: Ground-Truth Synthetic Dataset Generator"]
        SYN1["src/simulation/latent_state_model.py<br/>(Liquidity Cycles & Response Dynamics)"]
        SYN2["src/simulation/batch_generator.py<br/>(500-Case Labeled Dataset with Ground Truth)"]
    end

    %% Stage 7: Evaluation & Benchmark Harness
    subgraph S7 ["Stage 7: Quantitative Benchmark & Verification"]
        T1["tests/unit/test_guardrails.py<br/>(Exhaustive Invariant Proof: CVR = 0.0%)"]
        T2["tests/unit/test_diagnostic.py<br/>(Taxonomy & Ambiguity Precision/Recall)"]
        EV1["evals/metrics.py<br/>(NRR, FER, CVR, Multi-Class Confusion Matrix)"]
        EV2["evals/run_batch.py<br/>(End-to-End Batch Benchmark Runner)"]
        DASH["evals/dashboard.py<br/>(Visual Audit & Metric Summary CLI)"]
    end

    %% Dependencies
    K1 & K2 & K3 --> M1 & M2 & M3
    M1 & M2 & M3 --> G1 & G2 & G3 & G4 & G5 & G6 & G7
    G1 & G2 & G3 & G4 & G5 & G6 & G7 --> GE
    GE --> T1

    M1 & M2 --> I1 & I2 & D1
    D1 --> T2

    GE & D1 --> P1
    M3 & P1 --> P2
    P2 --> P3

    P3 --> E1 & E2 & E3
    M2 & K2 --> SYN1 --> SYN2

    SYN2 & E3 & P3 & GE --> EV1 --> EV2
    T1 & T2 & EV2 --> DASH
```

---

## 2. Construction Sequence & Milestones

1. **Milestone 0 — Knowledge Base & Schema Lock:** Formalize all regulatory numbers, error codes, Pydantic v2 schemas, and typed invariants in `docs/knowledge_base/`.
2. **Milestone 1 — Standalone Guardrail Engine:** Build deterministic guardrail filters with 100% test coverage proving zero compliance violations before building any agent.
3. **Milestone 2 — Webhook Ingestion & Diagnostic Classifier:** Implement signature verification, deduplication, and dual-rail taxonomy mapping.
4. **Milestone 3 — Constrained Action Optimization:** Combine deterministic guardrail action masking with expected net recovery scoring and LLM contextual reasoning.
5. **Milestone 4 — Synthetic Benchmark & Ground-Truth Simulator:** Generate 500 labeled failure cases with salary cycles and customer response dynamics.
6. **Milestone 5 — Evaluation Harness & Proof Dashboard:** Run the end-to-end evaluation suite to compute NRR, FER, CVR (0.0%), and confusion matrices.
