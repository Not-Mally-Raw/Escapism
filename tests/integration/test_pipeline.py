import asyncio
import json
import hmac
import hashlib
import os
import pytest
import aiosqlite
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.ingestion.gateway import app, WEBHOOK_SECRET, DB_PATH
from src.execution.worker import process_event

TEST_DB_PATH = "test_webhook.db"

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    monkeypatch.setattr("src.ingestion.gateway.DB_PATH", TEST_DB_PATH)
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

@pytest.mark.asyncio
async def test_successful_pipeline_execution():
    event_id = "evnt_test_123"
    valid_payload = {
        "state": {
            "case_id": "c1", "mandate_id": "m1", "merchant_id": "mer1", "customer_id": "cust1",
            "rail": "UPI_AUTOPAY", "amount_inr": "500", "attempt_count": 1, "failure_code": "01",
            "failure_class": "HARD_TERMINAL", "failure_timestamp": "2026-08-15T16:59:59+05:30",
            "channel_consent": {}
        }
    }
    
    raw_body = json.dumps(valid_payload).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "X-Razorpay-Signature": signature,
        "Content-Type": "application/json",
        "x-razorpay-event-id": event_id
    }
    
    # 1. Post to webhook
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook/razorpay",
            content=raw_body,
            headers=headers
        )
        assert response.status_code == 202
    
    # 2. Trigger worker manually
    async with aiosqlite.connect(TEST_DB_PATH) as db:
        async with db.execute("SELECT event_id, raw_payload FROM inbox WHERE status = 'PENDING'") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            
        await process_event(row[0], row[1], db)
        
        # 3. Verify audit log and seen_events
        async with db.execute("SELECT audit_json FROM audit_log WHERE event_id = ?", (event_id,)) as cursor:
            audit_row = await cursor.fetchone()
            assert audit_row is not None
            
        async with db.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)) as cursor:
            seen_row = await cursor.fetchone()
            assert seen_row is not None
            
        async with db.execute("SELECT status FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            status_row = await cursor.fetchone()
            assert status_row[0] == "PROCESSED"

@pytest.mark.asyncio
async def test_invalid_signature_rejected():
    raw_body = b'{"some": "payload"}'
    headers = {
        "X-Razorpay-Signature": "invalid_signature",
        "Content-Type": "application/json",
        "x-razorpay-event-id": "evnt_test_401"
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhook/razorpay",
            content=raw_body,
            headers=headers
        )
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_duplicate_event_id_deduplicated():
    event_id = "evnt_dup_123"
    raw_body = b'{"state": {"case_id": "c1", "amount_inr": "500", "attempt_count": 1, "failure_code": "01", "failure_timestamp": "2026-08-15T16:59:59+05:30", "channel_consent": {}}}'
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "X-Razorpay-Signature": signature,
        "Content-Type": "application/json",
        "x-razorpay-event-id": event_id
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First call succeeds
        response1 = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
        assert response1.status_code == 202
        
        # Second call with same event_id should return 202 OK without double-inserting
        response2 = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
        assert response2.status_code == 202
        
    async with aiosqlite.connect(TEST_DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM inbox WHERE event_id = ?", (event_id,)) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1 # Only inserted once
