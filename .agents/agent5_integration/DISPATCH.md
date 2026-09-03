## 2026-09-02T18:51:04Z

You are the Integration Lead for Milestone 5 (Final Phase).
Your working directory is: /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent5_integration

Read the authoritative requirements and project documents:
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/ORIGINAL_REQUEST.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/PROJECT.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent1_r1/handoff.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent2_r2/handoff.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent3_r3/handoff.md
- /Users/spandankewte/Downloads/razorpay-revenue-recovery/.agents/agent4_r4_r5/handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All verifications and implementations must be genuine. An auditor will independently verify the entire codebase.

Your Responsibilities:
1. Verify all merged contracts across the 4 milestones:
   - Ingestion & Event Boundary (R1)
   - Guardrails & Decision Engine (R2)
   - Causal Simulation & ML Lineage (R3)
   - Execution Reliability & Packaging (R4, R5)
2. Execute the complete `pytest` test suite across the entire repository (`.venv/bin/pytest -v`). Confirm 100% passing tests with zero regressions.
3. Execute Monte Carlo benchmark / policy evaluation (`.venv/bin/python scripts/run_monte_carlo.py`) and verify policy evaluation metrics.
4. Validate the full end-to-end recovery pipeline flow: from raw webhook ingestion -> inbox -> failure diagnosis -> decision optimization -> execution intent -> gateway call -> rich audit logging -> reconciliation / replay safety.
5. Validate package installation and importability (`.venv/bin/pip3 install --no-build-isolation -e .` and dashboard/module imports).
6. Document the complete verification results, test run outputs, benchmark metrics, and final system stability status.

Deliverables:
- Maintain `.agents/agent5_integration/progress.md`.
- Write comprehensive final report to `.agents/agent5_integration/handoff.md`.
- Send completion message when done.
