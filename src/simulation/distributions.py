"""
Success-Probability Priors and Causal Data Generating Process.
Mapped EXACTLY from error_taxonomy.md §3 and PS3_Locked_System_Specification.md §2.4/2.5.
🔴 Modeled assumption values, used for ground-truth simulation.
"""
from typing import Dict, Any, List
import datetime
import numpy as np

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
    """[DEPRECATED] Gets the exact prior probability of success based on taxonomy.
    Retained for backward compatibility with existing tests.
    """
    if attempt_number not in [2, 3, 4]:
        return 0.0
        
    class_dist = PRIORS.get(failure_class, PRIORS["HARD_TERMINAL"])
    
    if failure_class == "SOFT_LIQUIDITY" and is_post_salary:
        return class_dist["post_salary"][attempt_number]
        
    return class_dist["baseline"].get(attempt_number, 0.0)


NOOP_ACTION = "NOOP"
TREATMENT_ACTIONS: List[str] = [
    'SILENT_RETRY',
    'PIN_PROMPTED_RETRY',
    'SMS_NUDGE',
    'PAYMENT_LINK',
    'WHATSAPP_NUDGE',
    'RE_MANDATE_FLOW',
    'COOLDOWN_WAIT',
]
LOGGED_ACTIONS: List[str] = [NOOP_ACTION] + TREATMENT_ACTIONS

def mu_0(state_dict: Dict[str, Any]) -> float:
    """
    Control outcome surface P(recovery | state, no_action).
    """
    fc = state_dict.get('failure_class', '')
    attempt = state_dict.get('attempt_count', 1)
    ts = state_dict.get('failure_timestamp')
    if ts is None:
        ts = datetime.datetime.now()
        
    base_rates = {
        'SOFT_LIQUIDITY': 0.40,
        'TECHNICAL_RETRYABLE': 0.85,
        'AMBIGUOUS_DECLINE': 0.15,
        'HARD_TERMINAL': 0.0,
        'LEGAL_HOLD': 0.0
    }
    
    base = base_rates.get(fc, 0.0)
    
    day = ts.day
    is_salary_cycle = (1 <= day <= 5) or (28 <= day <= 31)
    if is_salary_cycle and fc == 'SOFT_LIQUIDITY':
        base += 0.25
        
    base *= (1.0 - 0.15 * max(0, attempt - 1))
    
    return float(np.clip(base, 0.0, 1.0))

W_ACTION = {
    'SILENT_RETRY': np.array([0.05, -0.10, 0.02, -0.05, 0.10, 0.01]),
    'PIN_PROMPTED_RETRY': np.array([0.04, -0.08, 0.03, -0.04, 0.08, 0.02]),
    'SMS_NUDGE': np.array([0.02, -0.05, 0.05, -0.02, 0.05, 0.05]),
    'PAYMENT_LINK': np.array([0.01, -0.15, 0.10, -0.01, 0.02, -0.01]),
    'WHATSAPP_NUDGE': np.array([0.03, -0.08, 0.08, -0.04, 0.08, 0.03]),
    'RE_MANDATE_FLOW': np.array([0.01, -0.05, 0.03, -0.02, 0.02, 0.00]),
    'COOLDOWN_WAIT': np.array([0.00, -0.02, 0.01, -0.01, 0.00, 0.00]),
}

def tau(state_dict: Dict[str, Any], action: str) -> float:
    """
    True CATE (treatment effect).
    """
    fc = state_dict.get('failure_class', '')
    if fc in ('HARD_TERMINAL', 'LEGAL_HOLD'):
        return 0.0
        
    if action == NOOP_ACTION:
        return 0.0

    if action not in TREATMENT_ACTIONS:
        return 0.0
        
    ts = state_dict.get('failure_timestamp')
    if ts is None:
        ts = datetime.datetime.now()
        
    amount = float(state_dict.get('amount_inr', 0.0))
    attempt = float(state_dict.get('attempt_count', 1.0))
    rail = state_dict.get('rail', '')
    
    hour = float(ts.hour) / 24.0
    amt = amount / 50000.0
    day = float(ts.day)
    day_feat = min(day, 30.0 - day) / 15.0
    att = attempt / 4.0
    upi = 1.0 if 'UPI' in str(rail) else 0.0
    dow = float(ts.weekday()) / 6.0
    
    x = np.array([hour, amt, day_feat, att, upi, dow])
    
    w = W_ACTION.get(action, np.zeros(6))
    linear_effect = w @ x
    
    interaction = 0.02 * x[0] * (1.0 - x[1])
    
    effect = linear_effect + interaction
    
    return float(np.clip(effect, -0.05, 0.30))
