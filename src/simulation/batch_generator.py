"""
Generates labeled synthetic records conforming to SimulationRecord and CausalSimulationRecord.
"""
import random
from decimal import Decimal
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import json
import numpy as np
from typing import Dict

from src.core.types import PaymentRail, FailureClass, ConsentStatus
from src.core.models import MandateStateRecord
from src.simulation.models import SimulationRecord, CausalSimulationRecord
from src.simulation.latent_state_model import is_post_salary_cycle
from src.simulation.distributions import get_ground_truth_probability, mu_0, tau, TREATMENT_ACTIONS, LOGGED_ACTIONS, NOOP_ACTION

IST = ZoneInfo("Asia/Kolkata")

MERCHANT_IDS = [f'mer_{i:03d}' for i in range(1, 21)]  # 20 merchants
CUSTOMER_IDS = [f'cust_{i:04d}' for i in range(1, 201)]  # 200 customers
ISSUER_BANKS = ['HDFC', 'SBI', 'ICICI', 'AXIS', 'KOTAK']
MERCHANT_CATEGORIES = ['streaming', 'insurance', 'loan_emi', 'utility', 'saas']
ERROR_SOURCES = ["customer", "bank", "razorpay"]
ERROR_REASONS = {
    FailureClass.SOFT_LIQUIDITY: ["insufficient_balance", "debit_limit_exceeded"],
    FailureClass.TECHNICAL_RETRYABLE: ["issuer_timeout", "bank_server_unavailable", "gateway_timeout"],
    FailureClass.AMBIGUOUS_DECLINE: ["issuer_declined", "reason_not_provided"],
    FailureClass.HARD_TERMINAL: ["account_closed", "mandate_cancelled", "account_blocked"],
    FailureClass.LEGAL_HOLD: ["court_order", "regulatory_freeze"],
}

def _generate_channel_consent() -> dict[str, ConsentStatus]:
    def _sample_status(p_in: float, p_out: float) -> ConsentStatus:
        r = random.random()
        if r < p_in:
            return ConsentStatus.OPTED_IN
        elif r < p_in + p_out:
            return ConsentStatus.OPTED_OUT
        else:
            return ConsentStatus.UNKNOWN

    return {
        "WHATSAPP": _sample_status(0.80, 0.15),
        "SMS": _sample_status(0.75, 0.15),
        "PAYMENT_LINK": _sample_status(0.85, 0.10),
    }

from src.core.taxonomy import (
    CODE_TO_CLASS,
    CLASS_TO_CODES,
    ALL_CODES,
    MALFORMED_CODES,
)

CLASS_WEIGHTS = [
    (FailureClass.SOFT_LIQUIDITY, 0.58),
    (FailureClass.TECHNICAL_RETRYABLE, 0.12),
    (FailureClass.AMBIGUOUS_DECLINE, 0.13),
    (FailureClass.HARD_TERMINAL, 0.10),
    (FailureClass.LEGAL_HOLD, 0.02),
    ("MALFORMED", 0.05),
]

NON_LEGAL_CLASSES = [
    FailureClass.SOFT_LIQUIDITY,
    FailureClass.HARD_TERMINAL,
    FailureClass.TECHNICAL_RETRYABLE,
    FailureClass.AMBIGUOUS_DECLINE,
]

def _sample_class_and_code() -> tuple[str, FailureClass]:
    classes, weights = zip(*CLASS_WEIGHTS)
    chosen = random.choices(classes, weights=weights, k=1)[0]
    if chosen == "MALFORMED":
        code = random.choice(MALFORMED_CODES)
        failure_class = random.choice(NON_LEGAL_CLASSES)
    else:
        failure_class = chosen
        code = random.choice(CLASS_TO_CODES[chosen])
    return code, failure_class

def _generate_amount() -> Decimal:
    choices = [
        round(random.uniform(100.0, 5000.0), 2),
        15000.00,
        15000.01,
        14999.99,
        round(random.uniform(15001.0, 50000.0), 2)
    ]
    return Decimal(str(random.choice(choices)))

def _generate_timestamps(attempt_count: int) -> tuple[datetime, datetime | None]:
    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=IST)
    if attempt_count == 1:
        return now, None
        
    spacing_hours_options = [
        timedelta(hours=23, minutes=59, seconds=59),
        timedelta(hours=24),
        timedelta(hours=72),
        timedelta(hours=168),
        timedelta(hours=random.uniform(2, 20)), 
        timedelta(hours=random.uniform(25, 48))
    ]
    spacing = random.choice(spacing_hours_options)
    
    base_times = [
        time(7, 59, 59), time(8, 0, 0), time(18, 59, 59), time(19, 0, 0), 
        time(9, 59, 59), time(10, 0, 0), time(12, 59, 59), time(13, 0, 0), 
        time(16, 59, 59), time(17, 0, 0), time(21, 29, 59), time(21, 30, 0)
    ]
    chosen_time = random.choice(base_times)
    
    failure_ts = now.replace(
        hour=chosen_time.hour, 
        minute=chosen_time.minute, 
        second=chosen_time.second, 
        microsecond=0
    ) - timedelta(days=random.randint(0, 10))
    
    last_attempt_ts = failure_ts - spacing
    return failure_ts, last_attempt_ts


def generate_causal_record(code_override: str = None, idx: int = 0) -> CausalSimulationRecord:
    if code_override:
        code = code_override
        if code in MALFORMED_CODES:
            failure_class = random.choice(list(FailureClass))
        else:
            failure_class = CODE_TO_CLASS[code]
    else:
        code, failure_class = _sample_class_and_code()
        
    amount = _generate_amount()
    attempt_count = random.randint(1, 4)
    failure_ts, last_attempt_ts = _generate_timestamps(attempt_count)
    
    rail = PaymentRail.UPI_AUTOPAY if code.startswith("U") or code.startswith("Z") else PaymentRail.ENACH
    
    merchant_id = random.choice(MERCHANT_IDS)
    customer_id = random.choice(CUSTOMER_IDS)
    issuer_bank = random.choice(ISSUER_BANKS)
    merchant_category = random.choice(MERCHANT_CATEGORIES)
    error_source = random.choice(ERROR_SOURCES)
    error_reason = random.choice(ERROR_REASONS.get(failure_class, ["unknown_failure"]))
    error_description = f"{error_source} failure: {error_reason.replace('_', ' ')}"

    state = MandateStateRecord(
        case_id=f"case_{idx:04d}",
        mandate_id=f"man_{idx:04d}",
        merchant_id=merchant_id,
        customer_id=customer_id,
        rail=rail,
        amount_inr=amount,
        attempt_count=attempt_count,
        failure_code=code,
        failure_class=failure_class,
        error_description=error_description,
        error_source=error_source,
        error_reason=error_reason,
        issuer_bank=issuer_bank,
        merchant_category=merchant_category,
        failure_timestamp=failure_ts,
        last_attempt_timestamp=last_attempt_ts,
        afa_required=(amount > 15000),
        pre_debit_notice_sent=random.choice([True, False]),
        customer_timezone="Asia/Kolkata",
        channel_consent=_generate_channel_consent(),
    )
    
    fc_val = failure_class.value if hasattr(failure_class, 'value') else str(failure_class)
    rail_val = rail.value if hasattr(rail, 'value') else str(rail)
    
    state_dict = {
        'failure_class': fc_val, 
        'attempt_count': attempt_count, 
        'failure_timestamp': failure_ts, 
        'amount_inr': float(amount), 
        'rail': rail_val, 
        'day_of_week': failure_ts.weekday()
    }

    base_p = mu_0(state_dict)
    
    true_cate_dict: Dict[str, float] = {}
    for action in LOGGED_ACTIONS:
        true_cate_dict[action] = tau(state_dict, action)
        
    epsilon = 0.2
    
    if random.random() < epsilon:
        observed_action = random.choice(LOGGED_ACTIONS)
    else:
        observed_action = max(LOGGED_ACTIONS, key=lambda a: true_cate_dict[a])
        
    best_action = max(LOGGED_ACTIONS, key=lambda a: true_cate_dict[a])
    
    if observed_action == best_action:
        propensity = (1.0 - epsilon) + (epsilon / len(LOGGED_ACTIONS))
    else:
        propensity = epsilon / len(LOGGED_ACTIONS)
        
    p_outcome = float(np.clip(base_p + true_cate_dict[observed_action], 0.0, 1.0))
    
    if code in MALFORMED_CODES:
        p_outcome = 0.0
        
    observed_outcome = random.random() < p_outcome

    return CausalSimulationRecord(
        state=state,
        observed_action=observed_action,
        observed_outcome=observed_outcome,
        propensity=propensity,
        true_cate=true_cate_dict,
        ground_truth_recoverable=observed_outcome
    )

def generate_record(code_override: str = None, idx: int = 0) -> SimulationRecord:
    causal = generate_causal_record(code_override=code_override, idx=idx)
    return SimulationRecord(
        state=causal.state, 
        ground_truth_recoverable=causal.observed_outcome
    )

def generate_batch(size: int, seed: int = 42) -> list[SimulationRecord]:
    random.seed(seed)
    np.random.seed(seed)
    records = []
    
    guaranteed_codes = ALL_CODES + MALFORMED_CODES
    idx = 0
    for code in guaranteed_codes:
        records.append(generate_record(code_override=code, idx=idx))
        idx += 1

    while len(records) < size:
        records.append(generate_record(idx=idx))
        idx += 1

    target_legal_hold = max(2, int(size * 0.02)) if size >= 500 else 1
    current_legal_hold = sum(1 for r in records if r.state.failure_class == FailureClass.LEGAL_HOLD)
    if current_legal_hold < target_legal_hold:
        legal_codes = ["07", "AP03"]
        for i in range(len(records) - (target_legal_hold - current_legal_hold), len(records)):
            code = random.choice(legal_codes)
            records[i] = generate_record(code_override=code, idx=i)
        
    random.shuffle(records)
    return records[:size]

def generate_causal_batch(size: int, seed: int = 42) -> list[CausalSimulationRecord]:
    random.seed(seed)
    np.random.seed(seed)
    records = []
    
    guaranteed_codes = ALL_CODES + MALFORMED_CODES
    idx = 0
    for code in guaranteed_codes:
        records.append(generate_causal_record(code_override=code, idx=idx))
        idx += 1

    while len(records) < size:
        records.append(generate_causal_record(idx=idx))
        idx += 1

    target_legal_hold = max(2, int(size * 0.02)) if size >= 500 else 1
    current_legal_hold = sum(1 for r in records if r.state.failure_class == FailureClass.LEGAL_HOLD)
    if current_legal_hold < target_legal_hold:
        legal_codes = ["07", "AP03"]
        for i in range(len(records) - (target_legal_hold - current_legal_hold), len(records)):
            code = random.choice(legal_codes)
            records[i] = generate_causal_record(code_override=code, idx=i)
        
    random.shuffle(records)
    return records[:size]

if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)
    
    batch_50 = generate_batch(50, seed=42)
    with open("data/synthetic_batch_50.jsonl", "w") as f:
        for r in batch_50:
            f.write(r.model_dump_json() + "\n")
            
    batch_500 = generate_batch(500, seed=100)
    with open("data/synthetic_batch_500.jsonl", "w") as f:
        for r in batch_500:
            f.write(r.model_dump_json() + "\n")

    batch_5000 = generate_batch(5000, seed=42)
    with open("data/synthetic_batch_5000.jsonl", "w") as f:
        for r in batch_5000:
            f.write(r.model_dump_json() + "\n")
            
    causal_batch_5000 = generate_causal_batch(5000, seed=42)
    with open("data/causal_batch_5000.jsonl", "w") as f:
        for r in causal_batch_5000:
            f.write(r.model_dump_json() + "\n")
            
    edge_cases = generate_batch(20, seed=99)
    with open("data/test_cases_edge.jsonl", "w") as f:
        for r in edge_cases:
            f.write(r.model_dump_json() + "\n")
