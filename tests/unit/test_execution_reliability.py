"""
Unit and Integration Tests for Milestone 4 (R4 & R5): Execution Reliability & Packaging.

Verifies:
1. Replay-safe dispatch: recording intent in SQLite before API call and reusing existing intent on replay.
2. Idempotency key preservation across retries.
3. Bounded exponential backoff delay calculation and retry scheduling.
4. Clean transition to DEAD_LETTER queue on reaching max retries.
5. Deterministic outcome reconciliation for interrupted executions.
6. Expanded audit log serialization (raw event ID, diagnostic, feasible action set, candidate scores, model version hash, gateway receipt).
7. MockRazorpayClient and RazorpayClient boundary contracts.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio

from src.core.models import MandateStateRecord
from src.core.types import ActionType, FailureClass, PaymentRail, ConsentStatus
from src.execution.razorpay_client import MockRazorpayClient, RazorpayClient, get_execution_client
from src.execution.worker import (
    compute_backoff_delay,
    execute_pipeline,
    process_event,
    reconcile_interrupted_executions,
    record_execution_intent,
    INITIAL_BACKOFF_SECONDS,
    BACKOFF_FACTOR,
    MAX_BACKOFF_SECONDS,
    MAX_RETRIES,
)
from src.ml.inference import get_model_version_hash

TEST_DB_PATH = "test_execution_reliability.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Set up a fresh test database with schema before each test."""
    monkeypatch.setattr("src.execution.worker.DB_PATH", TEST_DB_PATH)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        with open("src/ingestion/schema.sql", "r") as f:
            await db.executescript(f.read())

    yield

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def create_sample_payload(event_id: str, code: str = "Z9", amount: str = "1500.00") -> dict:
    """Helper to create a canonical webhook payload dict."""
    return {
        "state": {
            "case_id": f"case_{event_id}",
            "mandate_id": f"man_{event_id}",
            "merchant_id": "mer_test_001",
            "customer_id": "cust_test_001",
            "rail": "UPI_AUTOPAY",
            "amount_inr": amount,
            "attempt_count": 1,
            "failure_code": code,
            "failure_class": "SOFT_LIQUIDITY",
            "failure_timestamp": datetime.now(timezone.utc).isoformat(),
            "channel_consent": {
                "WHATSAPP": "OPTED_IN",
                "SMS": "OPTED_IN",
                "PAYMENT_LINK": "OPTED_IN",
            },
        },
        "raw_error_text": "Insufficient funds in bank account",
    }


# =============================================================================
# 1. Replay Safety & Idempotency Key Preservation
# =============================================================================

@pytest.mark.asyncio
async def test_replay_safety_reuses_intent_without_duplicate_external_call():
    """
    R4 Req 1: Worker re-dispatch with identical event ID reuses existing completed intent
    without generating duplicate external API calls.
    """
    event_id = "evnt_replay_001"
    payload = create_sample_payload(event_id)
    raw_payload_str = json.dumps(payload)

    mock_client = MockRazorpayClient()
    mock_client.execute_action = AsyncMock(wraps=mock_client.execute_action)

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        # 1. First execution: executes pipeline and writes intent + audit + seen_events
        audit1 = await execute_pipeline(raw_payload_str, event_id, db, client=mock_client)
        assert mock_client.execute_action.call_count == 1
        first_receipt = audit1["gateway_receipt"]

        # Verify execution intent is recorded with COMPLETED status
        async with db.execute(
            "SELECT intent_id, status, idempotency_key, receipt_json FROM execution_intents WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == f"intent_{event_id}"
            assert row[1] == "COMPLETED"
            assert row[2] == event_id
            assert json.loads(row[3]) == first_receipt

        # 2. Re-dispatch / Replay: same event ID executed again
        audit2 = await execute_pipeline(raw_payload_str, event_id, db, client=mock_client)

        # External call MUST NOT have been called again (call count remains 1)
        assert mock_client.execute_action.call_count == 1, "Duplicate external call was dispatched on replay!"
        assert audit2["gateway_receipt"] == first_receipt, "Cached receipt was not preserved across replay!"


@pytest.mark.asyncio
async def test_idempotency_key_enforced_across_retries():
    """
    R4 Req 2: Enforce idempotency keys (x-razorpay-event-id / event_id) across retries
    to prevent duplicate gateway operations.
    """
    event_id = "evnt_idempotency_check_999"
    payload = create_sample_payload(event_id)
    raw_payload_str = json.dumps(payload)

    captured_keys = []

    class CapturingClient:
        async def execute_action(self, selected_action: str, idempotency_key: str, **kwargs):
            captured_keys.append(idempotency_key)
            return {
                "id": f"plink_{idempotency_key}",
                "status": "created",
                "idempotency_key": idempotency_key,
                "mode": "mock",
            }

    client = CapturingClient()

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await execute_pipeline(raw_payload_str, event_id, db, client=client)

    assert len(captured_keys) == 1
    assert captured_keys[0] == event_id


# =============================================================================
# 2. Bounded Exponential Backoff & DLQ Transitions
# =============================================================================

def test_bounded_exponential_backoff_calculation():
    """
    R4 Req 4: Verify exponential backoff growth and ceiling bounds.
    """
    assert compute_backoff_delay(0) == 0.0
    assert compute_backoff_delay(1) == INITIAL_BACKOFF_SECONDS  # 1.0 * (2^0) = 1.0
    assert compute_backoff_delay(2) == INITIAL_BACKOFF_SECONDS * BACKOFF_FACTOR  # 1.0 * 2^1 = 2.0
    assert compute_backoff_delay(3) == INITIAL_BACKOFF_SECONDS * (BACKOFF_FACTOR ** 2)  # 1.0 * 4 = 4.0
    assert compute_backoff_delay(4) == INITIAL_BACKOFF_SECONDS * (BACKOFF_FACTOR ** 3)  # 1.0 * 8 = 8.0
    # Large retry count capped at MAX_BACKOFF_SECONDS (60.0)
    assert compute_backoff_delay(10) == MAX_BACKOFF_SECONDS


@pytest.mark.asyncio
async def test_transient_failure_schedules_backoff_retry():
    """
    R4 Req 4: Transient failure increments retry_count, updates last_error,
    schedules next_retry_at, and leaves inbox in PENDING status.
    """
    event_id = "evnt_transient_001"
    payload = create_sample_payload(event_id)
    raw_payload_str = json.dumps(payload)

    class FailingClient:
        async def execute_action(self, *args, **kwargs):
            raise ConnectionError("Gateway network connection timeout (simulated)")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await db.execute(
            "INSERT INTO inbox (event_id, raw_payload, status, retry_count) VALUES (?, ?, 'PENDING', 0)",
            (event_id, raw_payload_str),
        )
        await db.commit()

        # Process event with failing client
        await process_event(event_id, raw_payload_str, db, client=FailingClient())

        # Check inbox state
        async with db.execute(
            "SELECT status, retry_count, last_error, next_retry_at FROM inbox WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "PENDING"
            assert row[1] == 1  # Incremented to 1
            assert "ConnectionError" in row[2]
            assert row[3] is not None  # next_retry_at is scheduled in future

        # DLQ must remain empty since retry limit (3) not reached
        async with db.execute("SELECT COUNT(*) FROM dead_letter_queue WHERE event_id = ?", (event_id,)) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0


@pytest.mark.asyncio
async def test_terminal_failure_transitions_to_dead_letter_queue():
    """
    R4 Req 4: When retry_count reaches MAX_RETRIES (3), transition status to DEAD_LETTER
    and insert record into dead_letter_queue table.
    """
    event_id = "evnt_terminal_exhausted_001"
    payload = create_sample_payload(event_id)
    raw_payload_str = json.dumps(payload)

    class PersistentFailureClient:
        async def execute_action(self, *args, **kwargs):
            raise TimeoutError("Persistent upstream gateway failure")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        # Pre-seed inbox at retry_count = 2 (so next attempt is attempt 3 = MAX_RETRIES)
        await db.execute(
            "INSERT INTO inbox (event_id, raw_payload, status, retry_count) VALUES (?, ?, 'PENDING', 2)",
            (event_id, raw_payload_str),
        )
        await db.commit()

        # Attempt 3 fails
        await process_event(event_id, raw_payload_str, db, client=PersistentFailureClient())

        # Verify inbox status is DEAD_LETTER
        async with db.execute(
            "SELECT status, retry_count, last_error FROM inbox WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "DEAD_LETTER"
            assert row[1] == 3
            assert "Terminal failure" in row[2]

        # Verify dead_letter_queue has recorded the event
        async with db.execute(
            "SELECT event_id, error_type, error_message, attempt_count FROM dead_letter_queue WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            dlq_row = await cursor.fetchone()
            assert dlq_row is not None
            assert dlq_row[0] == event_id
            assert dlq_row[1] == "TimeoutError"
            assert "Persistent upstream gateway failure" in dlq_row[2]
            assert dlq_row[3] == 3


# =============================================================================
# 3. Deterministic Outcome Reconciliation
# =============================================================================

@pytest.mark.asyncio
async def test_deterministic_outcome_reconciliation_for_interrupted_executions():
    """
    R4 Req 3: Support deterministic outcome reconciliation for interrupted executions.
    If worker crashed after dispatching to gateway but before finalizing DB transaction,
    reconciliation detects existing gateway receipt, marks intent RECONCILED, updates seen_events,
    and transitions inbox to PROCESSED.
    """
    event_id = "evnt_interrupted_crash_001"
    intent_id = f"intent_{event_id}"
    receipt = {
        "id": "plink_crash_test_123",
        "action": "PAYMENT_LINK",
        "status": "created",
        "idempotency_key": event_id,
        "mode": "mock",
    }

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        # Simulate interrupted state:
        # 1. inbox was set to PROCESSING
        await db.execute(
            "INSERT INTO inbox (event_id, raw_payload, status) VALUES (?, '{\"test\": true}', 'PROCESSING')",
            (event_id,),
        )
        # 2. execution_intents was recorded as DISPATCHED with receipt
        await db.execute(
            """
            INSERT INTO execution_intents (intent_id, event_id, action, idempotency_key, status, receipt_json)
            VALUES (?, ?, 'PAYMENT_LINK', ?, 'DISPATCHED', ?)
            """,
            (intent_id, event_id, event_id, json.dumps(receipt)),
        )
        await db.commit()

        # Run reconciliation
        reconciled_count = await reconcile_interrupted_executions(db)
        assert reconciled_count == 1

        # Verify intent transitioned to RECONCILED
        async with db.execute(
            "SELECT status, receipt_json FROM execution_intents WHERE intent_id = ?",
            (intent_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "RECONCILED"
            assert json.loads(row[1]) == receipt

        # Verify inbox transitioned to PROCESSED
        async with db.execute(
            "SELECT status FROM inbox WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "PROCESSED"

        # Verify seen_events is populated
        async with db.execute(
            "SELECT 1 FROM seen_events WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            seen_row = await cursor.fetchone()
            assert seen_row is not None


# =============================================================================
# 4. Expanded Audit Log Serialization
# =============================================================================

@pytest.mark.asyncio
async def test_expanded_audit_log_fields():
    """
    R4 Req 5: Expand audit_log records to durably store:
    - raw event ID (event_id / raw_event_id)
    - diagnostic output (failure_class, confidence, evidence)
    - feasible action set (feasible_action_set)
    - candidate scores (candidate_scores with multipliers, costs, lift_ev_inr, etc.)
    - model version hash (model_version_hash matching metadata.json)
    - gateway receipt (gateway_receipt / action_result)
    """
    event_id = "evnt_audit_expansion_001"
    payload = create_sample_payload(event_id, code="Z9", amount="2500.00")
    raw_payload_str = json.dumps(payload)

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await execute_pipeline(raw_payload_str, event_id, db)

        async with db.execute(
            "SELECT audit_json FROM audit_log WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        audit = json.loads(row[0])

        # 1. Raw Event ID
        assert audit["event_id"] == event_id
        assert audit["raw_event_id"] == event_id

        # 2. Diagnostic Output
        assert "diagnostic" in audit
        diag = audit["diagnostic"]
        assert diag["failure_class"] == "SOFT_LIQUIDITY"
        assert "confidence" in diag
        assert isinstance(diag["evidence"], list)

        # 3. Feasible Action Set
        assert "feasible_action_set" in audit
        assert isinstance(audit["feasible_action_set"], list)
        assert len(audit["feasible_action_set"]) > 0

        # 4. Candidate Scores
        assert "candidate_scores" in audit
        assert isinstance(audit["candidate_scores"], list)
        if len(audit["candidate_scores"]) > 0:
            score_entry = audit["candidate_scores"][0]
            assert "action" in score_entry
            assert "multiplier" in score_entry
            assert "cost_inr" in score_entry
            assert "lift_ev_inr" in score_entry
            assert "cleared_threshold" in score_entry

        # 5. Model Version Hash
        expected_hash = get_model_version_hash()
        assert "model_version_hash" in audit
        assert audit["model_version_hash"] == expected_hash
        assert len(audit["model_version_hash"]) > 0

        # 6. Gateway Receipt
        assert "gateway_receipt" in audit
        assert audit["gateway_receipt"] is not None
        assert "idempotency_key" in audit["gateway_receipt"]


# =============================================================================
# 5. Mock vs Live Client Boundary Disclosures
# =============================================================================

@pytest.mark.asyncio
async def test_mock_razorpay_client_boundaries():
    """
    R5 Req 7: Verify MockRazorpayClient defaults, idempotency caching, and status lookups.
    """
    client = MockRazorpayClient()
    key = "idem_key_mock_001"

    res1 = await client.execute_action("PAYMENT_LINK", idempotency_key=key, amount_inr=Decimal("500.00"))
    assert res1["mode"] == "mock"
    assert res1["status"] == "created"
    assert res1["idempotency_key"] == key

    # Replay with same key returns identical receipt
    res2 = await client.execute_action("PAYMENT_LINK", idempotency_key=key, amount_inr=Decimal("500.00"))
    assert res1 == res2

    # Status check lookup
    status = await client.fetch_payment_link_status(res1["id"])
    assert status["id"] == res1["id"]

    action_status = await client.fetch_action_status(key)
    assert action_status == res1


def test_razorpay_client_requires_credentials_for_live_mode(monkeypatch):
    """
    R5 Req 7: RazorpayClient fails closed if credentials are not provided.
    """
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)

    with pytest.raises(ValueError, match="RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required"):
        RazorpayClient()


def test_get_execution_client_defaults_to_mock(monkeypatch):
    """
    R5 Req 7: get_execution_client() returns MockRazorpayClient by default.
    """
    monkeypatch.delenv("RAZORPAY_EXECUTION_MODE", raising=False)
    client = get_execution_client()
    assert isinstance(client, MockRazorpayClient)
