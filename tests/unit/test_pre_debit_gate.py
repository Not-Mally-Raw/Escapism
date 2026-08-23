import pytest
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from src.core.models import MandateStateRecord
from src.core.types import PaymentRail, FailureClass, ActionType
from src.guardrails.engine import compute_feasible_action_set

IST = ZoneInfo("Asia/Kolkata")

def _make_state(pre_debit_sent: bool) -> MandateStateRecord:
    return MandateStateRecord(
        case_id="case_001",
        mandate_id="man_001",
        merchant_id="mer_001",
        customer_id="cust_001",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("1000.00"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 22, 12, 0, 0, tzinfo=IST),
        last_attempt_timestamp=None,
        afa_required=False,
        pre_debit_notice_sent=pre_debit_sent,
        customer_timezone="Asia/Kolkata"
    )

def test_pre_debit_notice_gates_retries():
    """Proves that retries are strictly blocked if pre-debit notice wasn't sent."""
    state_no_notice = _make_state(pre_debit_sent=False)
    actions, notices = compute_feasible_action_set(state_no_notice)
    
    assert ActionType.SILENT_RETRY not in actions
    assert ActionType.PIN_PROMPTED_RETRY not in actions
    assert ActionType.SEND_PRE_DEBIT_NOTICE in notices

def test_pre_debit_notice_permits_retries():
    """Proves that retries are permitted once pre-debit notice was sent."""
    state_with_notice = _make_state(pre_debit_sent=True)
    actions, notices = compute_feasible_action_set(state_with_notice)
    
    assert ActionType.SILENT_RETRY in actions
    assert ActionType.PIN_PROMPTED_RETRY in actions
    assert ActionType.SEND_PRE_DEBIT_NOTICE not in notices
