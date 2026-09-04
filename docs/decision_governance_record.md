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
- **Test 1 (Prohibitive Digital Costs):** When digital action costs were adversarially inflated to ₹999,999, 100% of non-mandatory candidate cases safely fell through to `ABORT_COMPLIANT`. Exactly the mandatory compliance cases (100% of legal hold `07`/`AP03` and uncatalogued fail-closed codes) correctly routed to human review, proving the compliance boundary is impenetrable by cost tuning.
- **Test 2 (Prohibitive Human Costs):** When human costs were inflated and digital was free, digital actions dominated the feasible set, but the mandatory compliance cases still routed to human review, proving the system fails closed on compliance regardless of extreme cost skew.
- **Test 3 (CATE Adversarial Validation):** Dedicated adversarial tests verify that when CATE is active (`use_uplift=True`), passing `custom_costs` actively steers intervention rankings rather than bypassing the causal estimator or crashing.

## 4. Value-of-Information (VOI) Analysis & Roadmap
Instead of building ungrounded uncertainty-aware optimizers (e.g., Upper Confidence Bounds, contextual bandits) prematurely, we have quantified the sensitivity of our AI Orchestrator's edge to our core assumptions.

1. **Multiplier Table `m(a)`:** ±30% perturbations in channel multipliers caused the largest variance in the headline NRR. Resolving the true empirical lift of WhatsApp vs. SMS is the **highest priority** for future production data collection.
2. **Action-Conditioned Recovery `P(S|a)`:** Currently, Track 1 outputs action-agnostic probabilities. Moving to contextual modeling will provide the second-highest expected value.
3. **Cost Table `C(a)`:** Perturbing digital costs by ±50% (e.g., ₹0.80 to ₹1.20) had negligible impact on NRR, as the magnitude of recovered revenue (₹500+) dominates marginal API costs. Precision here is low-priority.

*Conclusion: Sophisticated stochastic control machinery is explicitly deferred. The expected value of resolving the base empirical channel multipliers vastly outweighs the value of algorithmic complexity.*

## 5. Model Lineage & The Three-Profile Progression
Over the course of development and rigorous adversarial auditing, the baseline recovery propensity estimator evolved across three distinct metric profiles, reflecting continuous methodological hardening rather than non-deterministic drift:

1. **Profile 1 (Legacy Synthetic Exploration - 80.1% Acc, 0.875 ROC-AUC, Dataset `40f623dd...`):**
   - *Design:* Early synthetic generation calibrated to 2.0% `LEGAL_HOLD` prevalence.
   - *Limitation:* Lacked omnichannel merchant/customer diversity and causal counterfactual logging.
2. **Profile 2 (Causal Shift & Policy Contamination - 72.1% Acc, 0.761 ROC-AUC, Dataset `4f4e09e2...`):**
   - *Design:* Expanded to 20 merchants and 200 customers with causal action logging.
   - *Limitation:* The target label `ground_truth_recoverable` was assigned to `observed_outcome` under an $\epsilon$-greedy treatment policy. The model was inadvertently estimating $P(\text{Recovery} \mid S, \pi(S))$, causing treatment lift to be double-counted when multiplied by $m(a)$ downstream.
3. **Profile 3 (Certified Unconfounded Baseline - 74.4% Acc, 0.730 ROC-AUC, ECE 0.0372, Dataset `90b2d59a...`):**
   - *Design:* Strict potential outcomes DGP where $Y_0 = \text{Bernoulli}(\mu_0(S))$ represents pure unconfounded passive recovery under `NOOP`.
   - *Guarantee:* Training is 100% deterministic (`random_seed=42`). Bit-for-bit identical metrics are reproduced across successive runs. Full hash lineage is locked between `data/synthetic_batch_5000.jsonl`, `metadata.json`, and the model card.

## 6. Policy Benchmark & SNIPS Offline Evaluation Governance
The 3-policy offline evaluation (`scripts/run_monte_carlo.py`) uses Self-Normalized Inverse Propensity Scoring (SNIPS) over logged observational data to eliminate the self-referential Monte Carlo scoring flaw.

### Macro Aggregates vs. Segment-Level Truth
A critical distinction established during external audits is the reconciliation between macro aggregates and compliance-segment economics:

| Policy | SNIPS NRR (₹) | 95% CI (₹) | Match Rate | Delta vs Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **Policy 1: Do Nothing (NOOP)** | ₹18,606,781.78 | [₹14.00M, ₹23.36M] | 12.3% | Baseline |
| **Policy 2: Naive Blind Retry** | ₹23,463,331.22 | [₹17.90M, ₹29.49M] | 4.7% | +₹4,856,549 (+26.1%) |
| **Policy 3: AI Orchestrator** | **₹29,154,368.01** | [₹24.89M, ₹33.81M] | 43.7% | **+₹5,691,037 (+24.3%) vs Blind**<br>**+₹10,547,586 (+56.7%) vs NOOP** |

### The Segment-Level Proof
While Blind Retry beats doing nothing in aggregate (because blindly retrying transient liquidity failures recovers gross revenue), it is **strictly net-negative on compliance-sensitive segments**:
- **`HARD_TERMINAL`:** Blind Retry nets **-₹267,527** (incurring regulatory fines on cancelled/closed mandates with ₹0 recovery). AI Orchestrator nets **₹0.00** by deterministically executing `ABORT_COMPLIANT`.
- **`LEGAL_HOLD`:** Blind Retry nets **-₹51,505** (incurring statutory fines on litigation accounts). AI Orchestrator nets **₹0.00** by short-circuiting to `ESCALATE_HUMAN`.
- **`AMBIGUOUS_DECLINE`:** Blind Retry recovers only ₹121,970 due to repeated gateway declines. AI Orchestrator recovers **₹2,239,999** (+₹2.12M uplift) by triggering 2FA Payment Links.
- **`SOFT_LIQUIDITY`:** AI Orchestrator recovers **₹18,259,939** vs. Blind Retry's ₹15,522,246 (+₹2.74M uplift) by timing WhatsApp nudges past salary credit boundaries.

Total penalties averted across 638 compliance-sensitive cases: **₹319,032**. Total net revenue uplift: **+₹5.69M (+24.3%) over Blind Retry**.
