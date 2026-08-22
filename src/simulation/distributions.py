"""
Success-Probability Priors.
Mapped EXACTLY from error_taxonomy.md §3 and PS3_Locked_System_Specification.md §2.4/2.5.
🔴 Modeled assumption values, used for ground-truth simulation.
"""
from typing import Dict, Any

# P(Success) mapped by [Attempt 2, Attempt 3, Attempt 4]
PRIORS: Dict[str, Dict[str, Any]] = {
    "SOFT_LIQUIDITY": {
        "baseline": {2: 0.45, 3: 0.55, 4: 0.25},
        "post_salary": {2: 0.70, 3: 0.80, 4: 0.25}
    },
    "TECHNICAL_RETRYABLE": {
        "baseline": {2: 0.90, 3: 0.95, 4: 0.95}
    },
    "AMBIGUOUS_DECLINE": {
        "baseline": {2: 0.20, 3: 0.15, 4: 0.05}
    },
    # Using UX_FRICTION for U69 (Soft/UX Friction)
    "UX_FRICTION": {
        "baseline": {2: 0.65, 3: 0.40, 4: 0.20}
    },
    "HARD_TERMINAL": {
        "baseline": {2: 0.0, 3: 0.0, 4: 0.0}
    },
    "LEGAL_HOLD": {
        "baseline": {2: 0.0, 3: 0.0, 4: 0.0}
    }
}

def get_ground_truth_probability(failure_class: str, attempt_number: int, is_post_salary: bool = False) -> float:
    """Gets the exact prior probability of success based on taxonomy."""
    if attempt_number not in [2, 3, 4]:
        return 0.0
        
    class_dist = PRIORS.get(failure_class, PRIORS["HARD_TERMINAL"])
    
    if failure_class == "SOFT_LIQUIDITY" and is_post_salary:
        return class_dist["post_salary"][attempt_number]
        
    return class_dist["baseline"].get(attempt_number, 0.0)
