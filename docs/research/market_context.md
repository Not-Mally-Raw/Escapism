# Market Context & Adjacent-Domain Patterns
### Status: RESEARCH REFERENCE — Documentation Only
### Sourcing Key: 🟢 Verified Source Cited | 🟡 Adjacent-Domain Pattern (concept only) | 🔴 Unverified (excluded from this file)

> **Scope rule:** This file contains only verified macro-context statistics and
> adjacent-domain patterns approved for conceptual adaptation. Vendor-reported
> performance numbers, unverified practitioner anecdotes, and out-of-scope
> material have been discarded. Nothing in this file is India-specific payment
> data unless explicitly labeled as such.

---

## §1 Verified Macro Context (US Market — Not India-Specific)

These statistics provide scale context for the global debt-recovery problem.
They are **US data only** and must never be cited as evidence for Indian
payment recovery rates, volumes, or regulatory mechanics.

🟢 **US household debt: \$18.8 trillion, Q1 2026.**
Source: Federal Reserve Bank of New York, Quarterly Report on Household Debt and Credit.

🟢 **US auto loan delinquency: 5.6%, Q1 2026 — series record above 2008 peak.**
Source: Federal Reserve Bank of New York, Quarterly Report on Household Debt and Credit.

🟢 **CFPB debt-collection complaints: ~387,400 in 2025, +86% YoY.**
Debt collection was the second-most-complained-about financial product category.
Source: CFPB 2025 Consumer Response Annual Report.

---

## §2 Comparative Regulatory Reference (SEPA — EU, Not India)

This comparison exists solely to illustrate that India's NPCI/RBI mandate
framework operates under **tighter and faster** constraints than EU equivalents.
It is not evidence for any performance claim.

🟢 **SEPA Direct Debit regulatory shape (EU):**
- 8-week unconditional dispute window (customer can reverse a debit with no reason given).
- Up to 13 months with a stated reason.
- 14-day mandatory pre-notification before debit execution.

**Comparison to this project's operating environment (India — NPCI/RBI):**
- ≥24h pre-debit notification (shorter notice window, but mandatory per RBI e-mandate framework).
- NPCI maximum 4 presentation attempts per mandate cycle (hard cap, no EU equivalent).
- 24h / 72h / 168h escalating spacing between retry attempts (no EU equivalent).
- ₹15,000 AFA threshold on silent retries (no EU equivalent).
- 8AM–7PM contact-hours restriction (applied voluntarily as conservative standard).

The net effect: India's constraints are **more granular and more prescriptive**
than SEPA's. A system that treats Indian mandate recovery as a subset of
global retry logic will miss constraints that don't exist in any other
jurisdiction. This is the regulatory basis for the project's rules-first
architecture.

---

## §3 Adjacent-Domain Patterns (Conceptual Adaptation Only)

Each pattern below is drawn from a domain outside Indian payment recovery.
**Self-reported performance numbers from these domains are not evidence for
this project and do not appear here.** Only the structural pattern is retained.

---

### §3.1 Three-Tier Sorting Pattern

🟡 **Source domain:** Healthcare Revenue Cycle Management (AnnexMed case study).

**Pattern:** Inbound claims are sorted into three tiers before any human
touches them:

| Tier | Description | Analogue in This Project |
|---|---|---|
| **Resolved** | Fully automated — no human needed | Guardrail engine returns a feasible action set; decision layer selects and executes without escalation |
| **Assembled** | Routed to human, but with pre-assembled context and recommended action | `ESCALATE_HUMAN` with `DiagnosticOutput` attached — the human receives failure class, confidence, evidence, and feasible actions already computed |
| **Judgment** | Requires genuine human judgment on novel/complex cases | Legal-hold cases (code `07`/`AP03`) and genuinely ambiguous declines below the heuristic threshold |

**Useful framing for the defense document:**

> "The sorting is the product. The question isn't 'does AI handle
> everything?' — it's: what percentage never reaches a human, what
> percentage reaches one with work already assembled, and what data
> decided the split."

This is a sharper restatement of the project's existing architecture:
`compute_feasible_action_set()` → decision layer → `ESCALATE_HUMAN`.

**What is NOT imported:** Any specific percentage split or recovery-rate
number from the healthcare domain.

---

### §3.2 Webhook-State Reconciliation Drift

🟡 **Source domain:** SaaS/fintech practitioner discussions (unverified
individual claims; only the structural pattern is retained).

**Pattern:** In production payment systems, application state can drift
from payment-processor state due to missed webhooks, out-of-order delivery,
or partial failures. The recommended mitigation is a **nightly reconciliation
job** that:

1. Pulls the current state of all active mandates/subscriptions from the
   payment processor API.
2. Compares against the application's internal state records.
3. **Softly flags** mismatches for review rather than hard-locking accounts
   or overriding mid-retry state.

**Relevance to this project:** This is a future concern for Stage 5
(execution/reconciliation). The current architecture's idempotency gate
(`src/ingestion/idempotency.py`, planned) handles duplicate delivery, but
does not yet address state drift from missed events. This reconciliation
job is **not in current scope** — it is noted here as a named architectural
gap for the production roadmap.

**Cross-reference:** The adversarial threat model in
`docs/research/flaw_b_dossier.md §D.3` identifies the double-charge race
condition. Webhook-state reconciliation is the complementary concern: not
"two processes act on the same state" but "the state itself is wrong because
an event was lost."

---

### §3.3 Failure-Class-Specific Communication Tone

🟡 **Source domain:** Debt-collection and SaaS dunning practitioner
discussions (no verified source; structural pattern only).

**Pattern:** The *tone* of recovery communication should vary by failure
class, not just the timing and channel:

| Failure Class | Tone Concern |
|---|---|
| **Soft / Liquidity** (`Z9`, `04`) | Same-day contact on a liquidity failure can add customer stress. A brief delay (e.g., 24–48h) with a neutral "your payment didn't go through" message reduces churn risk compared to an urgent "action required" message. |
| **Ambiguous Decline** (`U19`, `U30`) | An unexplained generic decline needs more explanatory context than a liquidity decline — the customer may not know why it failed, and the message should acknowledge that uncertainty rather than implying fault. |
| **Technical Retryable** (`U28`, `Z7`) | Customer may not need to be contacted at all — the system can silently retry after the transient issue resolves. Unnecessary customer contact on a bank-side timeout creates false alarm fatigue. |

**Relevance to this project:** The current architecture handles *which*
actions are feasible and *when* they can fire, but does not yet model
message tone as a function of `FailureClass`. This is a future enhancement
to the diagnosis → decision handoff, not current scope.

---

### §3.4 Consent-Revocation Propagation

🟡 **Source domain:** US debt-collection compliance (TSI operational
description).

**Pattern:** When a customer revokes consent for a specific communication
channel (e.g., opts out of SMS), that revocation must propagate immediately
as a **hard mask** on the action space — equivalent to the existing
time-window and contact-hours checks, not merely a soft preference.

**Relevance to this project:** The current `contact_gate.py` enforces
time-of-day restrictions, and the guardrail engine enforces AFA/spacing/
attempt-cap constraints. However, neither `MandateStateRecord` nor the
guardrail engine currently models per-customer, per-channel consent state.

**Architectural gap (future fix, not current scope):**
- Add a `channel_consent` field (or equivalent) to `MandateStateRecord`
  representing the customer's current opt-in/opt-out state per channel.
- The guardrail engine should discard `WHATSAPP_NUDGE`, `SMS_NUDGE`, or
  `PAYMENT_LINK` from the feasible set if the customer has revoked consent
  for that channel.
- This is a hard mask (fail-closed: if consent state is unknown, the
  channel is blocked), not a soft preference.

---

### §3.5 Modeled-Target vs. Measured-Result Discipline

🟡 **Source domain:** SF AI Labs (restaurant-dispute automation strategy
document).

**Pattern:** When reporting projected performance improvements, the source
document explicitly labels its claims:

> "The time reduction is a modeled automation target from the strategy work
> rather than a measured production result."

**Relevance to this project:** This is directly analogous to the project's
existing 🟢/🟡/🔴 tagging system:

| This Project's Tag | SF AI Labs Equivalent |
|---|---|
| 🟢 Verified Source Cited | Measured production result |
| 🟡 Own Analysis / Derived | Modeled automation target |
| 🔴 Modeled Assumption | Strategy-phase estimate |

The discipline is identical: **never present a modeled target in the same
tone as a measured result.** This project already enforces this (e.g., all
failure-class distribution percentages in the dossier are tagged 🔴). The
SF AI Labs framing reinforces that this is an industry-recognized practice,
not an idiosyncrasy of this project.

---

## §4 Discarded Material (Confirmation of Exclusion)

The following categories of input material were reviewed and **excluded
entirely** from this document:

- ❌ Reverse-logistics / retail-returns / computer-vision / dynamic resale pricing
- ❌ LeadClarify missed-call / inbound-lead recovery
- ❌ Generic medical-billing marketing content
- ❌ All vendor-reported performance numbers (TSI, KredosAI, CollectX, AnnexMed percentages)
- ❌ All unverified Reddit practitioner figures (3% drift, 5-8% MRR, ~70% payday recovery, etc.)
- ❌ Competing Track-03 GitHub submissions (architecture/numbers not imported)
- ❌ Any suggestion of multi-sub-agent architectures or scope expansion

No residual mention of discarded material appears in §1–§3.
