"""
Integration Tests for Ingestion Boundary and Worker Inbox Normalization (Milestone 1 / R1).
Tests full flow: Webhook Gateway -> SQLite Inbox -> Worker Processing -> Audit Log & Deduplication.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import aiosqlite
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from src.core.types import ActionType, FailureClass
from src.execution.worker import process_event
from src.ingestion.gateway import DB_PATH, WEBHOOK_SECRET, app

TEST_DB_PATH = "test_ingestion_boundary.db"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    monkeypatch.setattr("src.ingestion.gateway.DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr("src.execution.worker.DB_PATH", TEST_DB_PATH)

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        with open("src/ingestion/schema.sql", "r", encoding="utf-8") as f:
            await db.executescript(f.read())

    yield

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.mark.asyncio
async def test_e2e_canonical_fixture_ingestion_and_worker_processing():
    """
    R1 Full Ingestion Test:
    1. Post checked-in sanitized webhook fixture to Gateway.
    2. Verify HMAC validation and inbox persistence.
    3. Worker pulls from inbox, parses canonical payload, diagnoses failure, and executes recovery.
    4. Verify durable audit log and processed state.
    """
    fixture_path = FIXTURES_DIR / "webhook_mandate_debit_failed.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_fixture = f.read()

    event_id = "evt_e2e_fixture_001"
    raw_body = raw_fixture.encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()

    headers = {
        "X-Razorpay-Signature": signature,
        "Content-Type": "application/json",
        "x-razorpay-event-id": event_id,
    }

    # 1. Post to Webhook Gateway
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
        assert response.status_code == 202

    # 2. Verify in SQLite inbox table
    async with aiosqlite.connect(TEST_DB_PATH) as db:
        async with db.execute("SELECT event_id, raw_payload, status FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == event_id
            assert row[2] == "PENDING"

        # 3. Worker fetches and processes event
        await process_event(row[0], row[1], db)

        # 4. Verify inbox transition to PROCESSED
        async with db.execute("SELECT status, last_error FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            status_row = await cursor.fetchone()
            assert status_row[0] == "PROCESSED"
            assert status_row[1] is None

        # 5. Verify seen_events idempotency entry
        async with db.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)) as cursor:
            assert await cursor.fetchone() is not None

        # 6. Verify structured audit_log entry
        async with db.execute("SELECT audit_json FROM audit_log WHERE event_id = ?", (event_id,)) as cursor:
            audit_row = await cursor.fetchone()
            assert audit_row is not None
            audit_data = json.loads(audit_row[0])
            assert audit_data["event_id"] == event_id
            assert audit_data["state"]["amount_inr"] == "2500.00"
            assert audit_data["state"]["failure_code"] == "Z9"
            assert audit_data["state"]["failure_class"] == FailureClass.SOFT_LIQUIDITY.value
            assert audit_data["diagnostic"]["failure_class"] == FailureClass.SOFT_LIQUIDITY.value
            assert audit_data["action"] in [a.value for a in ActionType]


@pytest.mark.asyncio
async def test_legal_hold_fixture_worker_mandatory_escalation():
    """
    Verify legal hold fixture is processed by worker and mandatory escalation occurs.
    """
    fixture_path = FIXTURES_DIR / "webhook_legal_hold_failed.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        raw_fixture = f.read()

    event_id = "evt_legal_hold_001"
    raw_body = raw_fixture.encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()

    headers = {
        "X-Razorpay-Signature": signature,
        "Content-Type": "application/json",
        "x-razorpay-event-id": event_id,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
        assert response.status_code == 202

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        async with db.execute("SELECT event_id, raw_payload FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        await process_event(row[0], row[1], db)

        async with db.execute("SELECT audit_json FROM audit_log WHERE event_id = ?", (event_id,)) as cursor:
            audit_row = await cursor.fetchone()
            assert audit_row is not None
            audit_data = json.loads(audit_row[0])
            assert audit_data["state"]["failure_class"] == FailureClass.LEGAL_HOLD.value
            assert audit_data["action"] == ActionType.ESCALATE_HUMAN.value


@pytest.mark.asyncio
async def test_worker_fails_closed_on_malformed_inbox_payload():
    """
    Verify worker marks inbox status as FAILED and captures structured error message
    when inbox contains a corrupted payload.
    """
    event_id = "evt_corrupted_payload"
    corrupted_payload = "{\"entity\": \"event\", \"broken\": true"

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await db.execute(
            "INSERT INTO inbox (event_id, raw_payload, status) VALUES (?, ?, 'PENDING')",
            (event_id, corrupted_payload),
        )
        await db.commit()

        # Worker attempts processing
        await process_event(event_id, corrupted_payload, db)

        # Status must be FAILED with last_error populated
        async with db.execute("SELECT status, last_error FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "FAILED"
            assert row[1] is not None
            assert "MalformedPayloadError" in row[1] or "Invalid JSON" in row[1]
