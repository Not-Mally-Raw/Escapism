"""
Diagnostic Layer Subsystem.
Provides 3-tier semantic diagnosis and ambiguity resolution for payment failures.
"""
from src.diagnosis.ambiguity_handler import (
    AMBIGUITY_THRESHOLD_HEURISTIC,
    resolve_ambiguity,
)
from src.diagnosis.classifier import (
    DETERMINISTIC_TAXONOMY_LOOKUP,
    diagnose_failure,
    sanitize_error_text,
)
from src.diagnosis.models import DiagnosticOutput

__all__ = [
    "DiagnosticOutput",
    "AMBIGUITY_THRESHOLD_HEURISTIC",
    "resolve_ambiguity",
    "diagnose_failure",
    "sanitize_error_text",
    "DETERMINISTIC_TAXONOMY_LOOKUP",
]
