"""Pytest Configuration and Shared Test Fixtures."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import pytest

from src.core.models import MandateStateRecord
from src.core.types import FailureClass, PaymentRail

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def base_mandate_record() -> MandateStateRecord:
    """Fixture providing a standard valid mandate record."""
    return MandateStateRecord(
        case_id="case_test_001",
        mandate_id="token_test_12345",
        merchant_id="mer_test_001",
        customer_id="cust_test_001",
        rail=PaymentRail.UPI_AUTOPAY,
        amount_inr=Decimal("1499.00"),
        attempt_count=1,
        failure_code="Z9",
        failure_class=FailureClass.SOFT_LIQUIDITY,
        failure_timestamp=datetime(2026, 8, 22, 9, 0, 0, tzinfo=IST),
        last_attempt_timestamp=datetime(2026, 8, 22, 9, 0, 0, tzinfo=IST),
        afa_required=False,
        pre_debit_notice_sent=True,
        customer_timezone="Asia/Kolkata",
    )
