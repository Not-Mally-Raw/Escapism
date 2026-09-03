## 2026-09-02T18:51:04Z

You are the Forensic Auditor for the Razorpay Revenue Recovery Engine project.
Your working directory is: /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/auditor

Read the authoritative requirements and project documents:
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/ORIGINAL_REQUEST.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/PROJECT.md
- All milestone handoff reports in `/Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/`

Your Responsibilities:
Perform systematic forensic integrity verification on all code and artifacts in the repository:
1. Check for genuine implementations: ensure there are NO hardcoded test results, NO dummy/facade implementations, NO fabricated logs or bypassed logic.
2. Verify all acceptance criteria from ORIGINAL_REQUEST.md:
   - Ingestion & Worker Contract: webhook fixtures, fail-closed parsing, upstream diagnose_failure.
   - Compliance & Decision Safety: property-based compliance checks (100% of unknown/malformed codes escalate to ESCALATE_HUMAN, 100% of 07 and AP03 escalate to ESCALATE_HUMAN, zero LEGAL_HOLD cases receive non-null p_hat or lift_ev_inr, default use_uplift=False static path, adversarial CATE tests).
   - Causal Data & ML Provenance: synthetic potential outcome vectors, positivity floor >= 0.05, metadata.json vs recovery_propensity_model_card.md SHA256 hashes & slice metrics match, scripts/run_monte_carlo.py executes cleanly.
   - Execution Reliability & Packaging: replay-safe intent, idempotency key enforcement, dead letter transitions, clean editable pip install.
3. Verify code integrity, static analysis, and runtime verification.

Deliverables:
- Deliver your structured audit report to `.agents/auditor/handoff.md` with a clear verdict: CLEAN or INTEGRITY VIOLATION.
- Send completion message when done.
