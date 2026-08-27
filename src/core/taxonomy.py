"""
Canonical Return Code Taxonomy & FailureClass Mappings.
Single Source of Truth for NPCI UPI AutoPay & e-NACH Return Codes.
Citing: docs/knowledge_base/error_taxonomy.md
"""
from typing import Dict, List, Set, Tuple
from src.core.types import FailureClass

# 🟢 Verified NPCI / e-NACH Return Code to FailureClass Mapping
CODE_TO_FAILURE_CLASS: Dict[str, FailureClass] = {
    # UPI AutoPay (U-series & Z-series)
    "Z9": FailureClass.SOFT_LIQUIDITY,
    "U19": FailureClass.AMBIGUOUS_DECLINE,
    "U30": FailureClass.AMBIGUOUS_DECLINE,
    "U69": FailureClass.SOFT_LIQUIDITY,
    "U28": FailureClass.TECHNICAL_RETRYABLE,
    "Z7": FailureClass.TECHNICAL_RETRYABLE,
    "Z8": FailureClass.HARD_TERMINAL,
    # e-NACH Execution (Presentation) Codes
    "01": FailureClass.HARD_TERMINAL,
    "02": FailureClass.HARD_TERMINAL,
    "04": FailureClass.SOFT_LIQUIDITY,
    "05": FailureClass.HARD_TERMINAL,
    "06": FailureClass.HARD_TERMINAL,
    "07": FailureClass.LEGAL_HOLD,
    # e-NACH Registration Codes
    "AP01": FailureClass.HARD_TERMINAL,
    "AP02": FailureClass.HARD_TERMINAL,
    "AP03": FailureClass.LEGAL_HOLD,
    "AP04": FailureClass.HARD_TERMINAL,
    "AP05": FailureClass.HARD_TERMINAL,
}

# Alias for backward compatibility
CODE_TO_CLASS = CODE_TO_FAILURE_CLASS

# Derived Reverse Mapping: FailureClass -> List of Codes
CLASS_TO_CODES: Dict[FailureClass, List[str]] = {
    fc: [code for code, f_class in CODE_TO_FAILURE_CLASS.items() if f_class == fc]
    for fc in FailureClass
}

# All cataloged valid codes
ALL_CODES: List[str] = list(CODE_TO_FAILURE_CLASS.keys())

# Known ambiguous codes that require semantic inspection if error text is present
AMBIGUOUS_CODES: Set[str] = {"U19", "U30"}

# Strict legal hold / litigation freeze codes
LEGAL_HOLD_CODES: Set[str] = {"07", "AP03"}

# Synthetic malformed test codes for robustness & fail-closed testing
MALFORMED_CODES: List[str] = ["GARBAGE_99", "UNKNOWN_CODE", "XXX"]

# Deterministic lookup table for unambiguous cataloged return codes
# Maps code -> (FailureClass, Reason String) for 0ms, 0-token deterministic bypass
DETERMINISTIC_TAXONOMY_LOOKUP: Dict[str, Tuple[FailureClass, str]] = {
    # Soft / Liquidity
    "Z9": (FailureClass.SOFT_LIQUIDITY, "Deterministic lookup: Z9 mapped to SOFT_LIQUIDITY (insufficient funds)"),
    "04": (FailureClass.SOFT_LIQUIDITY, "Deterministic lookup: 04 mapped to SOFT_LIQUIDITY (balance insufficient)"),
    "U69": (FailureClass.SOFT_LIQUIDITY, "Deterministic lookup: U69 mapped to SOFT_LIQUIDITY (collect request expired / timeout)"),
    # Technical Retryable
    "U28": (FailureClass.TECHNICAL_RETRYABLE, "Deterministic lookup: U28 mapped to TECHNICAL_RETRYABLE (bank switch down)"),
    "Z7": (FailureClass.TECHNICAL_RETRYABLE, "Deterministic lookup: Z7 mapped to TECHNICAL_RETRYABLE (rate limit exceeded)"),
    # Hard / Terminal
    "Z8": (FailureClass.HARD_TERMINAL, "Deterministic lookup: Z8 mapped to HARD_TERMINAL (transaction limit exceeded)"),
    "01": (FailureClass.HARD_TERMINAL, "Deterministic lookup: 01 mapped to HARD_TERMINAL (account closed)"),
    "02": (FailureClass.HARD_TERMINAL, "Deterministic lookup: 02 mapped to HARD_TERMINAL (no such account)"),
    "05": (FailureClass.HARD_TERMINAL, "Deterministic lookup: 05 mapped to HARD_TERMINAL (not arranged for auto-debit)"),
    "06": (FailureClass.HARD_TERMINAL, "Deterministic lookup: 06 mapped to HARD_TERMINAL (payment stopped by drawer)"),
    "AP01": (FailureClass.HARD_TERMINAL, "Deterministic lookup: AP01 mapped to HARD_TERMINAL (account blocked / frozen)"),
    "AP02": (FailureClass.HARD_TERMINAL, "Deterministic lookup: AP02 mapped to HARD_TERMINAL (account closed)"),
    "AP04": (FailureClass.HARD_TERMINAL, "Deterministic lookup: AP04 mapped to HARD_TERMINAL (account inoperative)"),
    "AP05": (FailureClass.HARD_TERMINAL, "Deterministic lookup: AP05 mapped to HARD_TERMINAL (no such account number)"),
    # Legal Hold (Structural hard freeze)
    "07": (FailureClass.LEGAL_HOLD, "Deterministic lookup: 07 mapped to LEGAL_HOLD (court order / litigation)"),
    "AP03": (FailureClass.LEGAL_HOLD, "Deterministic lookup: AP03 mapped to LEGAL_HOLD (regulatory freeze)"),
}
