# Compliance Proof Appendix

This document maps the hard regulatory invariants (NPCI/RBI mandates) enforced by this architecture to the specific integration/unit tests that prove they cannot be violated.

## 1. NPCI Attempt Cap (Max 4 Attempts)
- **Constraint:** NPCI strictly limits the number of presentation attempts for a single mandate cycle to 4.
- **Enforcement:** `src/guardrails/attempt_limiter.py`
- **Proof:** `tests/unit/test_attempt_limiter.py::test_attempt_cap_boundaries` validates that on `attempt_count >= 4`, `SILENT_RETRY` is definitively removed from the feasible set, leaving only escalation or nudges.

## 2. RBI AFA Limit (₹15,000 Threshold)
- **Constraint:** Any recurring debit over ₹15,000 requires an Additional Factor of Authentication (AFA). Silent retries are strictly forbidden.
- **Enforcement:** `src/guardrails/afa_enforcer.py`
- **Proof:** `tests/unit/test_afa_enforcer.py::test_afa_threshold_exact_boundaries` proves that if `amount_inr > 15000.0`, `SILENT_RETRY` is stripped from the feasible set.

## 3. Mandatory 24h/72h Retry Spacing
- **Constraint:** Mandate retries must be spaced by minimum time windows to prevent harassment and system overload.
- **Enforcement:** `src/guardrails/spacing_validator.py` and `src/guardrails/window_mask.py`
- **Proof:** `tests/unit/test_spacing_validator.py::test_spacing_intervals_exact_boundaries` and `tests/unit/test_window_mask.py::test_window_mask_exact_boundaries` prove that if the minimum required time window hasn't elapsed, `SILENT_RETRY` is correctly masked out.

## 4. Contact Hours Restriction (8 AM - 7 PM)
- **Constraint:** Customer communication (WhatsApp, SMS, Calls) is strictly prohibited outside daylight hours to prevent harassment.
- **Enforcement:** `src/guardrails/contact_gate.py`
- **Proof:** `tests/unit/test_contact_gate.py::test_contact_hours_local_boundaries` tests precise timezone and hour boundaries, confirming that `WHATSAPP_NUDGE`, `SMS_NUDGE`, and `PAYMENT_LINK` are strictly removed from the feasible set outside of the 8 AM - 7 PM window.

## 5. Privilege Restriction & Hard Terminal Codes
- **Constraint:** Untrusted external error text fed to an LLM must never be able to hijack the compliance engine. Hard-terminal failures (like mandate cancellation or legal holds) must fail-closed deterministically.
- **Enforcement:** `src/guardrails/legal_hold_filter.py`
- **Proof:** `tests/unit/test_legal_hold_filter.py::test_legal_hold_codes` proves the guardrail engine checks the **raw failure code** directly, entirely bypassing the LLM's classification for critical hard-terminal checks. Furthermore, `tests/integration/test_compliance_invariants.py::test_compliance_invariants_500_states` randomly fuzzes state inputs and verifies no invalid action is ever permitted.
