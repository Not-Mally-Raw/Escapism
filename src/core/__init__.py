"""Core domain models, types, and canonical taxonomy."""
from src.core.types import ActionType, FailureClass, PaymentRail, ConsentStatus, EnforcementLevel
from src.core.models import MandateStateRecord, AttemptLogEntry
from src.core.taxonomy import (
    CODE_TO_FAILURE_CLASS,
    CODE_TO_CLASS,
    CLASS_TO_CODES,
    ALL_CODES,
    AMBIGUOUS_CODES,
    LEGAL_HOLD_CODES,
    MALFORMED_CODES,
    DETERMINISTIC_TAXONOMY_LOOKUP,
)

__all__ = [
    "ActionType",
    "FailureClass",
    "PaymentRail",
    "ConsentStatus",
    "EnforcementLevel",
    "MandateStateRecord",
    "AttemptLogEntry",
    "CODE_TO_FAILURE_CLASS",
    "CODE_TO_CLASS",
    "CLASS_TO_CODES",
    "ALL_CODES",
    "AMBIGUOUS_CODES",
    "LEGAL_HOLD_CODES",
    "MALFORMED_CODES",
    "DETERMINISTIC_TAXONOMY_LOOKUP",
]
