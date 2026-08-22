"""
Exhaustive Compliance Invariant Integration Tests.
Proves that the Compliance Violation Rate (CVR) is strictly 0.000% across >= 500 generated states,
and verifies exact regression calculations against the locked specification.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import random
from zoneinfo import ZoneInfo
import pytest

from src.core.models import MandateStateRecord
from src.core.types import ActionType, FailureClass, PaymentRail
from src.guardrails.engine import compute_feasible_action_set
from src.guardrails.spacing_validator import get_min_spacing_delta
from src.guardrails.window_mask import next_valid_execution_window

IST = ZoneInfo("Asia/Kolkata")


def test_compliance_invariants_500_states():
    """
    Exhaustively tests >= 500 randomized boundary states to verify regulatory invariants:
    1. INVARIANT A: If amount > 15,000 INR -> SILENT_RETRY is NEVER in feasible actions.
    2. INVARIANT B: If attempt_count >= 4 -> No auto-debit retries in feasible actions.
    3. INVARIANT C: If failure_code == '07' -> Actions are strictly {ActionType.ESCALATE_HUMAN}.
    4. Compliance Violation Count == 0 (CVR = 0.000%).
    """
    random.seed(42)

    failure_codes = ["Z9", "U19", "U30", "U69", "U28", "01", "04", "07", "AP01", "AP03"]
    failure_classes = [
        FailureClass.SOFT_LIQUIDITY,
        FailureClass.HARD_TERMINAL,
        FailureClass.TECHNICAL_RETRYABLE,
        FailureClass.AMBIGUOUS_DECLINE,
        FailureClass.LEGAL_HOLD,
    ]

    compliance_violations = 0
    total_evaluations = 500

    base_time = datetime(2026, 8, 22, 12, 0, 0, tzinfo=IST)

    for i in range(total_evaluations):
        # Generate varied states covering all boundary extremes
        amount = Decimal(str(random.choice([100, 500, 14999, 15000, 15001, 25000, 100000])))
        attempt_count = random.choice([1, 2, 3, 4])
        code = random.choice(failure_codes)
        fail_class = FailureClass.LEGAL_HOLD if code in {"07", "AP03"} else random.choice(failure_classes)
        last_attempt = base_time - timedelta(hours=random.randint(1, 200))
        eval_time = base_time + timedelta(hours=random.randint(0, 48))

        state = MandateStateRecord(
            case_id=f"case_synth_{i:04d}",
            mandate_id=f"token_synth_{i:04d}",
            merchant_id="mer_synth_001",
            customer_id=f"cust_synth_{i:04d}",
            rail=PaymentRail.UPI_AUTOPAY if code.startswith(("Z", "U")) else PaymentRail.ENACH,
            amount_inr=amount,
            attempt_count=attempt_count,
            failure_code=code,
            failure_class=fail_class,
            failure_timestamp=last_attempt,
            last_attempt_timestamp=last_attempt,
            afa_required=(amount > Decimal("15000.00")),
            ground_truth_recoverable=True,
            pre_debit_notice_sent=random.choice([True, False]),
            customer_timezone="Asia/Kolkata",
        )

        primary_actions, notifications = compute_feasible_action_set(state, current_time=eval_time)

        # Invariant 1: Legal Hold isolation
        if code == "07" or fail_class == FailureClass.LEGAL_HOLD:
            if primary_actions != {ActionType.ESCALATE_HUMAN} or len(notifications) != 0:
                compliance_violations += 1

        # Invariant 2: ₹15,000 AFA Rule
        if amount > Decimal("15000.00"):
            if ActionType.SILENT_RETRY in primary_actions:
                compliance_violations += 1

        # Invariant 3: Attempt Cap (k <= 4)
        if attempt_count >= 4:
            if ActionType.SILENT_RETRY in primary_actions or ActionType.PIN_PROMPTED_RETRY in primary_actions:
                compliance_violations += 1

    assert compliance_violations == 0, f"Detected {compliance_violations} compliance violations!"


def test_regression_worked_example_spec_4_1():
    """
    Regression Test against the worked example in Locked System Specification §4.1:
    - Failure TS: 2026-08-15 09:12:00 IST, attempt_count = 1
    - Next Spacing (k=2 -> +24h): 2026-08-16 09:12:00 IST
    - Non-Peak Window Check: 09:12:00 is in [00:00, 10:00) IST -> next_valid_window == 2026-08-16 09:12:00 IST
    """
    failure_ts = datetime(2026, 8, 15, 9, 12, 0, tzinfo=IST)

    # Next attempt is retry 1 (attempt 2) -> requires +24h spacing
    min_delta = get_min_spacing_delta(2)
    assert min_delta == timedelta(hours=24)

    earliest_retry_ts = failure_ts + min_delta
    assert earliest_retry_ts == datetime(2026, 8, 16, 9, 12, 0, tzinfo=IST)

    # Calculate next non-peak window
    valid_window_ts = next_valid_execution_window(earliest_retry_ts)
    assert valid_window_ts == datetime(2026, 8, 16, 9, 12, 0, tzinfo=IST)


def test_regression_peak_hour_delay_calculation():
    """
    Regression Test: A failure whose +24h retry falls inside a peak hour gap:
    - Failure TS: 2026-08-15 11:30:00 IST (Morning Peak)
    - Next Spacing (+24h): 2026-08-16 11:30:00 IST (Morning Peak [10:00, 13:00))
    - Must automatically advance to 2026-08-16 13:00:00 IST!
    """
    failure_ts = datetime(2026, 8, 15, 11, 30, 0, tzinfo=IST)
    earliest_retry_ts = failure_ts + timedelta(hours=24)  # 2026-08-16 11:30:00 IST

    valid_window_ts = next_valid_execution_window(earliest_retry_ts)
    assert valid_window_ts == datetime(2026, 8, 16, 13, 0, 0, tzinfo=IST)
