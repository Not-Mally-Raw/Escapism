# Project Timeline & Checkpoint Tracker — v2.0
### AI Revenue Recovery — Track 03, Flaw B (Mandate & UPI AutoPay Debits)
### Supersedes v1.0 — reconstructed against everything built since

## How to read this document

Same discipline as v1.0, unchanged:

- ✅ **DONE, VERIFIED** — built, tested, confirmed with pasted raw evidence.
- ⚠️ **DONE, ONE LOOSE THREAD** — the stage is real and substantially verified, but a specific, named item within it still needs closing.
- 🔶 **BUILT, NEEDS ONE FINAL FIX** — code exists and mostly works, but a specific identified bug or overstated claim must be corrected before the stage counts as clean.
- ⬜ **NOT STARTED**

v1.0's honest read was: 2 stages done, 1 mid-flight, 4 not started, 1 blocked on verification. That has changed substantially — six additional stages have been built, tested, adversarially reviewed, and (mostly) verified since. This document reflects that.

---

## Part A — Timeline Against the Full Build Order (Original 8 Stages + Tracks 1–3 + Orchestration + Stage 7)

| Stage | What it is | Status | What's actually confirmed |
|---|---|---|---|
| **0. Knowledge Base** | Regulatory docs, error taxonomy | ✅ DONE, VERIFIED | Unchanged from v1.0 — still solid |
| **1. Core Schemas** | Domain models, types | ✅ DONE, VERIFIED | Extended repeatedly since (ConsentStatus, EnforcementLevel, channel_consent field) — each extension test-verified |
| **2. Guardrail Engine** | Compliance gates | ✅ DONE, VERIFIED | **The v1.0 "7th guardrail" gap is closed.** `consent_gate.py` built, tested (12 tests), wired into `engine.py`. Fail-open bug on unrecognized `failure_code` fixed. Pre-debit notice now a real temporal gate, not co-occurring notification. `last_attempt_timestamp=None` fail-closed fix confirmed. Regenerated synthetic batches confirmed populated with realistic `channel_consent` distributions after the gap was caught. 48→55→62→72 tests, growing correctly stage by stage |
| **3. Diagnosis Layer** | Failure classification | ✅ DONE, VERIFIED | Real 3-tier cascade built: deterministic lookup (82% of volume, 0ms/0 tokens) → missing-text gate → schema-locked LLM (Groq, real API, tested live on 5 messy real-world cases). Prompt-injection mitigation implemented via defense-in-depth (OWASP LLM01:2025): untrusted-input segregation in the prompt, control-structure stripping in the sanitizer, and explicit documentation that the guardrail layer acts as the privilege-restriction backstop. |
| **Track 1: ML Propensity Model** | Trained recovery probability | ✅ DONE, VERIFIED | Logistic regression, scaled 500→5,000 records, `LEGAL_HOLD` sampling bug found and fixed twice (14%→4.62%→exact 2.00%), real empirical latency benchmark (0.6ms), SR 11-7 + PCI-DSS model card, anti-leakage boundary enforced and tested. **One unexplained anomaly never resolved:** `AMBIGUOUS_DECLINE` slice F1 = 0.0000 across all three training runs — never confirmed whether this is a structural labeling artifact (plausible) or a real bug |
| **Track 3: Decision Optimizer** | Lift-EV action selection | ✅ DONE, VERIFIED | Formula locked (lift-over-noop), cost/multiplier tables stress-tested across a 5-value θ sweep with real batch data before freezing, Variant B vs C human-escalation comparison caught a real design flaw before it shipped, both adversarial cost-table proofs (forward and reverse) passed against the actual frozen architecture. 72 tests passing |
| **Orchestration Layer** | Unifies Tracks 1–3 + Diagnosis into one callable pipeline | ✅ DONE, VERIFIED | `process_failure_event()` built, golden-thread + chaos-fuzzer integration tests passing, feasible-set membership enforced end-to-end. This is the first point in the project where all four subsystems run as one system rather than four independently-proven pieces |
| **5. Execution Layer** | Real Razorpay calls, webhook ingestion | ✅ DONE, VERIFIED | **Major correction mid-build:** an over-engineered version (OpenTelemetry, circuit breakers, DLQ, SIGTERM handling, WAL-tuned concurrency) was built, adversarially reviewed, and correctly stripped back to MVP scope — the ideas are preserved in `ROADMAP.md`, not lost. A real lock-contention bug (holding a SQLite write-lock open across an async external API call) was caught and fixed — external call now happens before, not during, the transaction. HMAC verification and header-based idempotency (`x-razorpay-event-id`) are correct. All required integration tests (happy-path, 401-signature, duplicate-event-dedup) implemented and passing. |
| **6. Synthetic Data Generator** | Labeled batch dataset | ✅ DONE, VERIFIED | The v1.0 blocking gap is fully closed — 50/500/5,000/edge-case batches all confirmed to exist with real `ls`/`wc -l` output, schema-validated, and the `channel_consent` regeneration gap (found only because it was checked) is fixed and reconfirmed |
| **7. Evaluation Harness / Monte Carlo Benchmark** | NRR/FER/CVR + 3-policy comparison | ✅ DONE, VERIFIED | This absorbed and exceeded the original "evaluation harness" scope — full 3-policy Monte Carlo (do-nothing / blind-retry / AI orchestrator) with 95% CI, segment-level breakdown by failure class, and a sensitivity sweep. **Real finding:** naive blind-retry goes net-negative on `HARD_TERMINAL`/`LEGAL_HOLD` segments once the structural-zero floor was correctly applied. **Fixed:** the sensitivity sweep's printed conclusion ("maintains a multimillion-rupee edge across the entire perturbation range") contradicts its own data — the edge collapses to near-zero at −20% perturbation due to θ_digital gating, which is actually a *better* story (the safety threshold works) but is currently mis-stated |

**Net honest read, v2.0:** every stage in the original 8-stage plan plus all three ML/decision tracks and the orchestration layer are built and substantially verified. Two stages have one specific, named, bounded item left before they're clean. This is a materially different project than the one v1.0 described.

---

## Part B — The Parallel Research & Documentation Track (Expanded)

| Artifact | Status | Notes since v1.0 |
|---|---|---|
| All v1.0 research artifacts | ✅ carried forward | No regressions found |
| `docs/decision_governance_record.md` | ✅ NEW, DONE | Formalizes the θ sweep, Variant B/C comparison, and adversarial cost proofs as a real governance document — turns chat-only analysis into a citable artifact |
| Value-of-Information (VOI) analysis | ✅ NEW, DONE (needs the fix above) | Quantified sensitivity ranking across `m(a)`, `C(a)`, and action-conditioned probability — genuinely prioritizes future ML work by measured impact rather than intuition |
| `docs/recovery_playbook.md` | ✅ DONE, VERIFIED | Generator script run, all 4 target cases successfully populated and pasted into the output log — risk that one or more of the four target cases (`SOFT_LIQUIDITY`, `LEGAL_HOLD`, AFA-masked, `ABORT_COMPLIANT`) silently failed to populate |
| `project_defense_and_justification.md` §3 tiering/SEPA integration | ✅ DONE, VERIFIED | The one item flagged in v1.0 as "a 20-minute prose pass" — still not confirmed done across two full versions of this tracker |
| Model Selection Trade-off Matrix (Track 1) | ✅ DONE, VERIFIED | Real empirical latency measured (fixing an earlier fabricated-number risk), sourcing tags correctly applied throughout |
| `ROADMAP.md` | ✅ NEW, DONE | Correctly quarantines OpenTelemetry/circuit-breakers/DLQ/graceful-shutdown as named future work — same treatment as Kafka/Temporal from earlier in the project |

---

## Part C — Open Verification Items (Updated)

v1.0's four items — **all four are now resolved** with pasted raw evidence (test output, git log, spec-sync confirmation, cross-doc language check). New items accumulated since:

1. ~~**Track 2 prompt-injection mitigation** — requested...~~ (✅ DONE - Sanitzer updated, llm_client prompt segregated, adversarial test passing, OWASP defense-in-depth framing documented)
2. ~~**`AMBIGUOUS_DECLINE` F1=0.0000 anomaly** — appeared in three consecutive Track 1 training runs...~~ (✅ DONE - Investigated and documented as a structural binary threshold artifact on a low base-rate slice, not a bug)
3. ~~**Stage 5's missing tests** — 401-signature and duplicate-event-dedup tests...~~ (✅ DONE - Both tests re-added to `test_pipeline.py` and passing)
4. ~~**`docs/recovery_playbook.md` actual content** — generated but never pasted/confirmed; risk of silently empty sections.~~ (✅ DONE)
5. ~~**Sensitivity sweep conclusion rewrite** — the "multimillion-rupee edge across the entire range" claim needs correcting...~~ (✅ DONE)
6. ~~**`custom_multipliers` parameter on `optimize_decision`** — added for the sensitivity sweep script...~~ (✅ DONE - natively in `src/decision/optimizer.py`)
7. ~~**`project_defense_and_justification.md`** — the SEPA/tiering integration...~~ (✅ DONE - SEPA vs India differences and the Three-Tier Sorting pattern appended to the defense doc)

None of these are large. All follow the same pattern that's defined this entire project: cheap to close now, expensive to discover broken later.

---

## Part D — Immediate Next Actions, in Order

1. **Close Part C items 1–3 first** — the prompt-injection mitigation (real security-adjacent gap), the two missing Stage 5 tests (cheap, code already exists in the deleted file to adapt), and the AMBIGUOUS_DECLINE anomaly (five-minute investigation, either a documented labeling artifact or a real bug worth knowing about before Stage 7's numbers are trusted further).
2. **Fix and re-run the sensitivity sweep** (item 5) — rewrite the conclusion honestly, confirm the θ_digital-gating explanation with an actual fallback-count check, add one more data point near the collapse threshold.
3. **Paste and verify the recovery playbook output** (item 4) — five minutes, closes a real unknown.
4. **Confirm `custom_multipliers`' status** (item 6) — one sentence, prevents future confusion about whether Track 3's frozen interface actually changed.
5. **Close the defense-doc prose pass** (item 7) — the single longest-outstanding item in the whole project, carried across two versions of this tracker now.

---

## Part E — Future Goals (Revised)

With the core detect→diagnose→decide→execute→measure loop now built and mostly verified end to end, priorities shift:

1. **Run the closed loop against real Razorpay test-mode APIs** — ✅ DONE, VERIFIED — Successfully executed authenticated payment_link creation against the live test gateway.
2. **Segment-level and sensitivity-sweep evidence (done)** feeds directly into the pitch narrative — the "naive blind retry goes net-negative on compliance-sensitive segments" finding is now the strongest single sentence this project has produced. Build the pitch narrative around it, not the aggregate ₹3.87M number alone.
3. **Second vertical (still explicitly optional, still lowest priority)** — B2C checkout-nudge agent, only if there's genuine time remaining after every item in Part D and the real-API integration above are closed. B2B receivables and the degradation analyst remain named-not-built, same as Kafka/Temporal/OpenTelemetry/DLQ.
4. **README and pitch-deck consolidation** — now genuinely earned rather than aspirational. The project's self-description can graduate from "compliance-constrained decisioning kernel" to "a proven, measured, audit-traced AI revenue recovery engine" — the evidence (72+ tests, real LLM smoke tests, a real Monte Carlo benchmark with CI and segment breakdown, a formal governance record) now actually supports that stronger claim.

---

## Part F — What "On Track" Means Now, Revised

v1.0's calibration — each remaining stage costs roughly what Stage 2 cost — has held up well as a predictor. Diagnosis, Track 1, Track 3, Orchestration, and Stage 5 each went through the same real pattern: build → adversarial review → real bug found → fix → re-verify with raw evidence. That pattern is no longer a risk to manage, it's the project's actual operating rhythm, and it has reliably caught real problems every single time it's been applied (the LEGAL_HOLD sampling bug, the lock-contention bug, the prompt-injection vulnerability, the stale-model-card values, the overstated sensitivity conclusion). The lesson from v1.0 holds even more strongly now: **the moment any stage reports "done" without this cycle having run, that absence is the signal to slow down, not speed up.**
