# Repository Architecture & File Tree Specification
### System: AI Revenue Recovery (Track 03 — Flaw B: Mandate & UPI AutoPay Debits)

This document outlines the complete directory layout, module responsibilities, and structural hierarchy for the repository.

```
razorpay-revenue-recovery/
├── README.md                               # Project overview, architecture diagrams, and quickstart
├── pyproject.toml                          # Poetry/Pip build config & dependency management
├── pytest.ini                              # Pytest test suite configuration
├── .env.example                            # Example environment variables (Razorpay secrets, LLM keys)
│
├── docs/                                   # Architectural and regulatory documentation
│   ├── learning_graph.md                   # Topological build dependency graph (Mermaid)
│   ├── skills.md                           # Engineering standards, state, validation & metrics
│   ├── project_structure.md                # Exhaustive repository file tree (this file)
│   └── knowledge_base/                     # Ground truth reference documents
│       ├── rbi_npci_regulations.md         # 4-attempt cap, spacing, non-peak, AFA & FPC rules
│       └── error_taxonomy.md               # UPI U/Z-series & e-NACH return code mappings
│
├── src/                                    # Core application source code
│   ├── __init__.py
│   │
│   ├── core/                               # Foundational domain schemas and configuration
│   │   ├── __init__.py
│   │   ├── types.py                        # Finite Enums (ActionType, FailureClass, PaymentRail)
│   │   ├── models.py                       # Pydantic v2 domain schemas (MandateRecord, AuditEntry)
│   │   └── config.py                       # Tunable parameters (Cost table, Theta, priors)
│   │
│   ├── guardrails/                         # Deterministic Pre-Action Invariant Filters
│   │   ├── __init__.py
│   │   ├── engine.py                       # Master Guardrail Engine (Computes feasible action mask)
│   │   ├── attempt_limiter.py              # Enforces NPCI max 4 attempts rule (k <= 4)
│   │   ├── spacing_validator.py            # Enforces 24h / 72h / 168h spacing intervals
│   │   ├── window_mask.py                  # Enforces IST non-peak execution windows
│   │   ├── contact_gate.py                 # Enforces RBI Fair Practices Code 8AM-7PM contact hours
│   │   ├── afa_enforcer.py                 # Enforces ₹15,000 AFA threshold on silent retries
│   │   └── legal_hold_filter.py            # Enforces immediate human escalation on e-NACH Code 07
│   │
│   ├── diagnostic/                         # Error Code Analysis & Root-Cause Classification
│   │   ├── __init__.py
│   │   ├── classifier.py                   # Maps raw bank codes to structured FailureClass
│   │   ├── upi_autopay_parser.py           # Dedicated UPI AutoPay U-series / Z-series parser
│   │   ├── enach_parser.py                 # Dedicated e-NACH presentation / registration parser
│   │   └── ambiguity_handler.py            # Handles low-confidence declines (U19, U30)
│   │
│   ├── decision/                           # Strategy Optimization & Action Selection
│   │   ├── __init__.py
│   │   ├── action_pruner.py                # Hard-masks action space using Guardrail Engine
│   │   ├── net_recovery_model.py           # Calculates expected net recovery given priors and costs
│   │   ├── agent.py                        # LLM reasoning planner for contextual intervention
│   │   └── fallback_policy.py              # Executes ABORT_COMPLIANT when E[Yield] < Theta
│   │
│   ├── ingestion/                          # Webhook Processing & Idempotency Gateway
│   │   ├── __init__.py
│   │   ├── webhook_verifier.py             # HMAC SHA-256 signature verification (X-Razorpay-Signature)
│   │   ├── idempotency.py                  # Atomic Event-ID deduplication and replay protection
│   │   └── event_router.py                 # Routes verified webhook events to diagnostic pipeline
│   │
│   ├── execution/                          # Action Dispatcher & Audit Logging
│   │   ├── __init__.py
│   │   ├── dispatcher.py                   # Dispatches selected actions to mock/live clients
│   │   ├── payment_link_client.py          # Razorpay Payment Links API client
│   │   ├── mandate_scheduler.py            # Schedules bank-rail retry tasks into non-peak slots
│   │   └── audit_logger.py                 # Append-only structured audit trail logger
│   │
│   └── simulation/                         # Synthetic Data & Ground Truth Generation
│       ├── __init__.py
│       ├── latent_state_model.py           # Models customer salary cycles & response dynamics
│       ├── batch_generator.py              # Generates 500-case synthetic evaluation batch
│       └── distributions.py                # Calibrated failure code probability distributions
│
├── data/                                   # Generated datasets and test batches
│   ├── synthetic_batch_500.jsonl           # Primary labeled benchmark dataset (hidden ground truth)
│   └── test_cases_edge.jsonl               # Specialized edge cases (Code 07, boundary amounts)
│
├── evals/                                  # Benchmark Evaluation Harness & Metrics
│   ├── __init__.py
│   ├── metrics.py                          # NRR, FER, CVR, Confusion Matrix & Legal Recall
│   ├── run_batch.py                        # CLI harness executing recovery across a batch
│   └── dashboard.py                        # Terminal/Markdown summary dashboard generator
│
└── tests/                                  # Exhaustive Test Suite
    ├── __init__.py
    ├── conftest.py                         # Pytest fixtures, mock webhooks, and sample mandates
    │
    ├── unit/                               # Unit tests for individual components
    │   ├── test_guardrails.py              # Invariant tests: 4-attempt, spacing, windows, AFA
    │   ├── test_diagnostic.py              # Taxonomy mapping & ambiguity handling tests
    │   ├── test_idempotency.py             # Signature verification & deduplication tests
    │   ├── test_net_recovery.py            # Expected yield optimization calculation tests
    │   └── test_audit_logger.py            # Audit log completeness and schema tests
    │
    └── integration/                        # End-to-end integration workflows
        ├── test_recovery_lifecycle.py      # Full loop: Webhook -> Guardrails -> Action -> Audit
        └── test_compliance_invariants.py   # Exhaustive batch test asserting CVR == 0.000%
```

---

## Module Responsibilities Summary

1. **`src/guardrails/`**: Implements 100% deterministic code filters. Contains no machine learning or LLM calls. Acts as a strict pre-filter for all candidate actions.
2. **`src/diagnostic/`**: Disentangles UPI AutoPay and e-NACH error taxonomies, mapping raw bank switch signals into clean domain failure classes.
3. **`src/decision/`**: The intelligence layer. Takes the pruned feasible action set, computes expected monetary yield minus intervention and churn costs, and selects optimal next-best action.
4. **`src/ingestion/`**: Enforces production-grade API boundary security, signature validation, and deduplication to handle at-least-once webhook delivery.
5. **`src/simulation/`**: Generates high-fidelity synthetic benchmark datasets with embedded ground truth labels, salary cycle dynamics, and realistic response models.
6. **`evals/`**: Provides the evaluation harness to benchmark recovery performance, generating verifiable proof of correctness for judges.
