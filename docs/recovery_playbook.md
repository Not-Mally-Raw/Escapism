# Recovery Playbook: AI Orchestrator Examples

## Case 1: SOFT_LIQUIDITY Success (Digital Channel Lift)
**Case ID:** `case_0390` | **Amount:** ₹604.37 | **Class:** `SOFT_LIQUIDITY`
- **P̂(S) Base Recovery:** 0.1705
- **Selected Action:** `WHATSAPP_NUDGE`
- **Lift-EV Calculation:** ₹19.81 (Cost: ₹0.80)
- **System Rationale:** Selected 'WHATSAPP_NUDGE' with optimal Lift-EV of ₹19.81 (P̂=0.1705, m=1.20, Cost=₹0.80), clearing threshold θ_digital=₹1.00.

## Case 2: LEGAL_HOLD (Mandatory Escalation)
**Case ID:** `case_4462` | **Amount:** ₹15000.01 | **Class:** `LEGAL_HOLD`
- **P̂(S) Base Recovery:** 0.0000
- **Selected Action:** `ESCALATE_HUMAN`
- **System Rationale:** Mandatory regulatory escalation: Failure code 'AP03' or failure class 'LEGAL_HOLD' requires human intervention. EV scoring bypassed by compliance invariant.

## Case 3: AFA-Gated (SILENT_RETRY properly masked)
**Case ID:** `case_2476` | **Amount:** ₹17035.43 | **Class:** `SOFT_LIQUIDITY`
- **P̂(S) Base Recovery:** 0.1555
- **Selected Action:** `WHATSAPP_NUDGE`
- **Lift-EV Calculation:** ₹529.00 (Cost: ₹0.80)
- **System Rationale:** Selected 'WHATSAPP_NUDGE' with optimal Lift-EV of ₹529.00 (P̂=0.1555, m=1.20, Cost=₹0.80), clearing threshold θ_digital=₹1.00.

## Case 4: ABORT_COMPLIANT (Expected Value too low)
**Case ID:** `case_0749` | **Amount:** ₹15000.0 | **Class:** `HARD_TERMINAL`
- **P̂(S) Base Recovery:** 0.0001
- **Selected Action:** `ABORT_COMPLIANT`
- **Lift-EV Calculation:** ₹-0.07 (Cost: ₹0.00)
- **System Rationale:** Optimal candidate 'COOLDOWN_WAIT' yielded Lift-EV of ₹-0.08, failing threshold θ_digital=₹1.00. Safely aborting automated intervention.

