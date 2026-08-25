"""
Generates labeled synthetic records conforming to SimulationRecord.
"""
import random
from decimal import Decimal
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import json

from src.core.types import PaymentRail, FailureClass, ConsentStatus
from src.core.models import MandateStateRecord
from src.simulation.models import SimulationRecord
from src.simulation.latent_state_model import is_post_salary_cycle
from src.simulation.distributions import get_ground_truth_probability

IST = ZoneInfo("Asia/Kolkata")

def _generate_channel_consent() -> dict[str, ConsentStatus]:
    """
    Generates synthetic per-channel customer consent state.

    🔴 MODELED ASSUMPTION:
    In Indian consumer subscription context, WhatsApp and SMS have high opt-in rates
    with a realistic minority opting out or having indeterminate/unverified consent:
    - WHATSAPP: 80% OPTED_IN, 15% OPTED_OUT, 5% UNKNOWN
    - SMS: 75% OPTED_IN, 15% OPTED_OUT, 10% UNKNOWN
    - PAYMENT_LINK: 85% OPTED_IN, 10% OPTED_OUT, 5% UNKNOWN
    """
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

CODE_TO_CLASS = {
    "Z9": FailureClass.SOFT_LIQUIDITY,
    "U19": FailureClass.AMBIGUOUS_DECLINE,
    "U30": FailureClass.AMBIGUOUS_DECLINE,
    "U69": FailureClass.SOFT_LIQUIDITY,
    "U28": FailureClass.TECHNICAL_RETRYABLE,
    "Z7": FailureClass.TECHNICAL_RETRYABLE,
    "Z8": FailureClass.HARD_TERMINAL,
    "01": FailureClass.HARD_TERMINAL,
    "02": FailureClass.HARD_TERMINAL,
    "04": FailureClass.SOFT_LIQUIDITY,
    "05": FailureClass.HARD_TERMINAL,
    "06": FailureClass.HARD_TERMINAL,
    "07": FailureClass.LEGAL_HOLD,
    "AP01": FailureClass.HARD_TERMINAL,
    "AP02": FailureClass.HARD_TERMINAL,
    "AP03": FailureClass.LEGAL_HOLD,
    "AP04": FailureClass.HARD_TERMINAL,
    "AP05": FailureClass.HARD_TERMINAL,
}

ALL_CODES = list(CODE_TO_CLASS.keys())
MALFORMED_CODES = ["GARBAGE_99", "UNKNOWN_CODE", "XXX"]

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

def generate_record(code_override: str = None, idx: int = 0) -> SimulationRecord:
    code = code_override or random.choice(ALL_CODES + MALFORMED_CODES)
    
    if code in MALFORMED_CODES:
        failure_class = random.choice(list(FailureClass))
    else:
        failure_class = CODE_TO_CLASS[code]
        
    amount = _generate_amount()
    attempt_count = random.randint(1, 4)
    failure_ts, last_attempt_ts = _generate_timestamps(attempt_count)
    
    rail = PaymentRail.UPI_AUTOPAY if code.startswith("U") or code.startswith("Z") else PaymentRail.ENACH
    
    if attempt_count == 4:
        ground_truth = False 
    else:
        is_post_sal = is_post_salary_cycle(failure_ts)
        dist_class = "UX_FRICTION" if code == "U69" else failure_class.value
        if code in MALFORMED_CODES:
            p_success = 0.0 
        else:
            p_success = get_ground_truth_probability(dist_class, attempt_count + 1, is_post_sal)
        ground_truth = random.random() < p_success

    state = MandateStateRecord(
        case_id=f"case_{idx:04d}",
        mandate_id=f"man_{idx:04d}",
        merchant_id="mer_default_001",
        customer_id="cust_default_001",
        rail=rail,
        amount_inr=amount,
        attempt_count=attempt_count,
        failure_code=code,
        failure_class=failure_class,
        failure_timestamp=failure_ts,
        last_attempt_timestamp=last_attempt_ts,
        afa_required=(amount > 15000),
        pre_debit_notice_sent=random.choice([True, False]),
        customer_timezone="Asia/Kolkata",
        channel_consent=_generate_channel_consent(),
    )
    
    return SimulationRecord(
        state=state,
        ground_truth_recoverable=ground_truth
    )

def generate_batch(size: int, seed: int = 42) -> list[SimulationRecord]:
    """
    Generates a deterministic synthetic batch of SimulationRecords.
    
    🔴 MODELED ASSUMPTION (Option A):
    Rare classes such as LEGAL_HOLD (codes '07', 'AP03') are guaranteed
    adequate representation (minimum 2% of the dataset, >= 100 cases for N=5000)
    for evaluation metric stability on held-out test splits.
    """
    random.seed(seed)
    records = []
    
    # 1. Guaranteed representation of every single code at least once
    guaranteed_codes = ALL_CODES + MALFORMED_CODES
    idx = 0
    for code in guaranteed_codes:
        records.append(generate_record(code_override=code, idx=idx))
        idx += 1
        
    # 2. Guaranteed minimum quota for rare LEGAL_HOLD class (>= 2% or 100 for N=5000)
    target_legal_hold = max(2, int(size * 0.02)) if size >= 500 else 1
    current_legal_hold = sum(1 for r in records if r.state.failure_class == FailureClass.LEGAL_HOLD)
    
    legal_codes = ["07", "AP03"]
    while current_legal_hold < target_legal_hold and len(records) < size:
        code = random.choice(legal_codes)
        records.append(generate_record(code_override=code, idx=idx))
        idx += 1
        current_legal_hold += 1

    # 3. Fill the rest of the batch
    while len(records) < size:
        records.append(generate_record(idx=idx))
        idx += 1
        
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
            
    edge_cases = generate_batch(20, seed=99)
    with open("data/test_cases_edge.jsonl", "w") as f:
        for r in edge_cases:
            f.write(r.model_dump_json() + "\n")
