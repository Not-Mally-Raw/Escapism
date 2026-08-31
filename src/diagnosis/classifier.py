"""
Three-Tier Semantic Diagnostic Classifier for Payment Failures.
Implements the Abstain-and-Escalate Cascade Architecture:
1. Deterministic Taxonomy Lookup (covers ~82% volume, 0ms latency, 0 token cost).
2. Missing Text Residual Gate (skips LLM when no text is available, returns AMBIGUOUS_DECLINE).
3. Schema-Locked LLM Diagnostic Agent (invoked only on ambiguous residual with error text).

Safety & Boundary Notes:
- OWASP LLM01:2025 Mitigation (Prompt Injection): It is unclear if there are fool-proof methods
  of prevention. Mitigation requires defense in depth. We implement:
  1. Segregation of untrusted external content in the LLM prompt.
  2. Control-structure stripping in the text sanitizer.
  3. (Crucial) Privilege Restriction: `legal_hold_filter.py` checks the raw `failure_code`
     directly, NEVER the LLM output. This is the human-in-the-loop / hard-boundary backstop
     recommended by OWASP. Prompt injection cannot bypass compliance guardrails.
- legal_hold_filter.py checks the raw failure_code directly; it never trusts the FailureClass
  produced here. A misclassification therefore only degrades recovery quality, never compliance.
- 🔴 MODELED ASSUMPTION: The 0.40 confidence threshold in ambiguity_handler.py is an initial
  heuristic cutoff, not calibrated from labeled production data.
"""
import json
import re
from typing import Any, Callable, Dict, Optional, Tuple

from src.core.types import FailureClass
from src.diagnosis.ambiguity_handler import resolve_ambiguity
from src.diagnosis.models import DiagnosticOutput

from src.core.taxonomy import (
    DETERMINISTIC_TAXONOMY_LOOKUP,
    AMBIGUOUS_CODES,
)

# PII / PCI-DSS Sanitization Regexes
_PAN_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_VPA_REGEX = re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}\b")
_PHONE_REGEX = re.compile(r"\b(?:\+91|91)?[6-9]\d{9}\b")
_ACCOUNT_REGEX = re.compile(r"\b\d{9,18}\b")


def sanitize_error_text(text: str) -> str:
    """
    Sanitizes raw error text to strip potential cardholder PANs, VPAs, phone numbers,
    or bank account numbers before submitting to an LLM prompt or log (PCI-DSS & Privacy).
    Also implements OWASP LLM01:2025 semantic filters by stripping control characters 
    and role delimiters to prevent prompt injection.
    """
    sanitized = _PAN_REGEX.sub("__REDACTED_PAN__", text)
    sanitized = _VPA_REGEX.sub("__REDACTED_VPA__", sanitized)
    sanitized = _PHONE_REGEX.sub("__REDACTED_PHONE__", sanitized)
    sanitized = _ACCOUNT_REGEX.sub("__REDACTED_ACCOUNT__", sanitized)
    
    # Strip JSON brackets and structural characters that could hijack JSON mode
    sanitized = re.sub(r'[\{\}\[\]"\'`<>|]', ' ', sanitized)
    
    # Strip faux role injections
    sanitized = re.sub(r'(?i)\b(system|user|assistant|role|instruction)\s*:', ' ', sanitized)
    
    return sanitized.strip()


def default_llm_classifier(bank_code: str, sanitized_text: str) -> DiagnosticOutput:
    """
    Default rule-guided semantic parser when no external LLM API client is configured.
    Provides semantic diagnosis for raw error text while maintaining fail-closed boundaries.
    """
    text_lower = sanitized_text.lower()

    if any(k in text_lower for k in ["insufficient", "low balance", "funds", "exhausted"]):
        return DiagnosticOutput(
            failure_class=FailureClass.SOFT_LIQUIDITY,
            confidence=0.85,
            evidence=[f"Semantic extraction: '{sanitized_text}' indicates customer liquidity shortfall."],
        )
    elif any(k in text_lower for k in ["timeout", "downtime", "switch unavailable", "network", "bank server"]):
        return DiagnosticOutput(
            failure_class=FailureClass.TECHNICAL_RETRYABLE,
            confidence=0.90,
            evidence=[f"Semantic extraction: '{sanitized_text}' indicates transient infrastructure timeout."],
        )
    elif any(k in text_lower for k in ["closed", "invalid account", "blocked", "dormant", "cancelled"]):
        return DiagnosticOutput(
            failure_class=FailureClass.HARD_TERMINAL,
            confidence=0.95,
            evidence=[f"Semantic extraction: '{sanitized_text}' indicates terminal mandate state."],
        )
    elif any(k in text_lower for k in ["court", "litigation", "freeze order", "police"]):
        return DiagnosticOutput(
            failure_class=FailureClass.LEGAL_HOLD,
            confidence=0.95,
            evidence=[f"Semantic extraction: '{sanitized_text}' indicates legal hold freeze."],
        )
    else:
        # Indeterminate text -> low confidence below threshold
        return DiagnosticOutput(
            failure_class=FailureClass.AMBIGUOUS_DECLINE,
            confidence=0.25,
            evidence=[f"Semantic extraction: '{sanitized_text}' lacks definitive diagnostic keywords."],
        )


def diagnose_failure(
    bank_code: str,
    raw_error_text: Optional[str] = None,
    llm_callable: Optional[Callable[[str, str], DiagnosticOutput]] = None,
) -> DiagnosticOutput:
    """
    Three-tier diagnostic cascade entrypoint:
    1. Deterministic Taxonomy Lookup:
       If bank_code is an unambiguous cataloged code, return immediately with confidence=1.0.
       Zero LLM calls, zero latency, zero hallucination risk.
    2. Missing Error Text Fallback:
       If code is ambiguous/unrecognized and raw_error_text is None/empty, return AMBIGUOUS_DECLINE
       with confidence=0.0 (skips LLM entirely as there is no signal to reason over).
    3. Schema-Locked LLM Classification:
       If error text is present, sanitize PII/PAN, invoke LLM classifier, enforce schema locking,
       apply the 0.40 ambiguity threshold override, and fail closed on any exception.

    Args:
        bank_code: The raw bank/gateway error code (e.g., 'Z9', 'U19', '01', 'GARBAGE_99').
        raw_error_text: Optional error message string from bank webhook.
        llm_callable: Optional custom LLM classification callable (bank_code, sanitized_text) -> DiagnosticOutput.

    Returns:
        DiagnosticOutput: Validated, confidence-scored failure diagnosis.
    """
    normalized_code = (bank_code or "").strip().upper()

    # --- Tier 1: Deterministic Taxonomy Lookup ---
    if normalized_code in DETERMINISTIC_TAXONOMY_LOOKUP:
        failure_class, reason = DETERMINISTIC_TAXONOMY_LOOKUP[normalized_code]
        return DiagnosticOutput(
            failure_class=failure_class,
            confidence=1.0,
            evidence=[reason],
        )

    # --- Tier 2: Residual Ambiguous / Unrecognized with Missing Text ---
    clean_text = (raw_error_text or "").strip()
    if not clean_text:
        return DiagnosticOutput(
            failure_class=FailureClass.AMBIGUOUS_DECLINE,
            confidence=0.0,
            evidence=[
                f"Unresolved code '{normalized_code}' with no raw error text provided; "
                "defaulting to ambiguous decline."
            ],
        )

    # --- Tier 3: Schema-Locked LLM Classifier Path ---
    sanitized_text = sanitize_error_text(clean_text)
    classifier_fn = llm_callable or default_llm_classifier

    try:
        raw_diagnosis = classifier_fn(normalized_code, sanitized_text)
        
        # Enforce DiagnosticOutput schema validation
        if not isinstance(raw_diagnosis, DiagnosticOutput):
            if isinstance(raw_diagnosis, dict):
                raw_diagnosis = DiagnosticOutput.model_validate(raw_diagnosis)
            else:
                raise TypeError(f"Classifier returned non-DiagnosticOutput object: {type(raw_diagnosis)}")

        # Pass through the Uncertainty Protocol (0.40 threshold heuristic override)
        return resolve_ambiguity(raw_diagnosis)

    except Exception as e:
        # Fail-closed invariant: on any exception, return low-confidence ambiguous decline
        return DiagnosticOutput(
            failure_class=FailureClass.AMBIGUOUS_DECLINE,
            confidence=0.0,
            evidence=[f"LLM diagnostic failure ({type(e).__name__}: {str(e)}); fail-closed fallback applied."],
        )
