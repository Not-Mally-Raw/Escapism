# Decision Governance Record: Track 3 Optimizer Parameters

## Executive Summary
This document formalizes the analytical stress-testing that governed the parameter selection for the Track 3 Decision Optimizer. It outlines the alternatives considered, the empirical evidence from synthetic batch testing, and the rationale for the final locked parameters. This ensures the live decision engine relies on robust, defensible heuristics while more sophisticated uncertainty modeling (LCB, contextual bandits) is deferred until grounded production data is available.

## 1. Threshold Gating Sweep (θ_digital)
**Decision:** Locked `THETA_DIGITAL = ₹1.00`.
**Alternatives Tested:** ₹0.00, ₹1.00, ₹5.00, ₹10.00, ₹25.00.
**Evidence:** 
- A threshold of ₹0.00 recovered marginally more cases but allowed interventions with statistically negligible lift, risking long-term customer fatigue for pennies.
- A threshold of ₹5.00+ erroneously aborted viable `SOFT_LIQUIDITY` recovery opportunities on low-ticket mandates (e.g., ₹500 transactions), disproportionately harming recovery rates for micro-merchants.
- ₹1.00 provided the optimal balance: it cleanly filtered out zero-value or phantom interventions while preserving >95% of the genuine recovery lift on low-amount mandates.

## 2. The Human Escalation Flood (Variant B vs C)
**Decision:** `ESCALATE_HUMAN` is treated as a mandatory compliance route (Variant C), explicitly excluded from competing in the open Lift-EV calculation.
**Evidence:** 
- In Variant B (unconstrained competition), the high presumed success rate of human intervention caused `ESCALATE_HUMAN` to win ~73% of all cases.
- This would instantly overwhelm any realistic merchant call center capacity.
- By isolating human escalation to strict compliance guardrails (e.g., `LEGAL_HOLD`), the system protects human bandwidth while relying on digital channels for scale.

## 3. Adversarial Cost Table Proofs
**Decision:** The Lift-EV formula strictly respects relative cost differentials without requiring dynamic shrinkage.
**Evidence:**
- **Test 1 (Prohibitive Digital Costs):** When digital action costs were adversarially inflated to ₹999,999, 100% of non-mandatory cases safely fell through to `ABORT_COMPLIANT`. Mandatory legal cases (345 out of 5,000) correctly routed to human review, proving the compliance boundary is impenetrable by cost tuning.
- **Test 2 (Prohibitive Human Costs):** When human costs were inflated and digital was free, digital actions dominated the feasible set, but the mandatory 345 cases still routed to human review, proving the system fails closed on compliance regardless of extreme cost skew.

## 4. Value-of-Information (VOI) Analysis & Roadmap
Instead of building ungrounded uncertainty-aware optimizers (e.g., Upper Confidence Bounds, contextual bandits) prematurely, we have quantified the sensitivity of our AI Orchestrator's edge to our core assumptions.

1. **Multiplier Table `m(a)`:** ±30% perturbations in channel multipliers caused the largest variance in the headline NRR. Resolving the true empirical lift of WhatsApp vs. SMS is the **highest priority** for future production data collection.
2. **Action-Conditioned Recovery `P(S|a)`:** Currently, Track 1 outputs action-agnostic probabilities. Moving to contextual modeling will provide the second-highest expected value.
3. **Cost Table `C(a)`:** Perturbing digital costs by ±50% (e.g., ₹0.80 to ₹1.20) had negligible impact on NRR, as the magnitude of recovered revenue (₹500+) dominates marginal API costs. Precision here is low-priority.

*Conclusion: Sophisticated stochastic control machinery is explicitly deferred. The expected value of resolving the base empirical channel multipliers vastly outweighs the value of algorithmic complexity.*
