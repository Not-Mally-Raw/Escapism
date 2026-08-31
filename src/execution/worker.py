import asyncio
import json
import logging
from datetime import datetime
import aiosqlite
from pydantic import ValidationError

# Verify Domain Imports
from src.core.models import MandateStateRecord
from src.diagnosis.classifier import diagnose_failure
from src.decision.optimizer import optimize_decision
from src.execution.razorpay_client import get_execution_client

logger = logging.getLogger(__name__)

DB_PATH = "webhook.db"
WORKER_ID = "worker-01"

async def execute_pipeline(payload: dict, event_id: str, db: aiosqlite.Connection):
    state_dict = payload.get("state")
    if not state_dict:
        state_dict = payload
    
    state = MandateStateRecord(**state_dict)
    
    # 1. Run Tracks 1, 2, and 3 (In-memory, fast)
    diagnostic = diagnose_failure(
        bank_code=state.failure_code,
        raw_error_text=payload.get("raw_error_text")
    )
    
    state = state.model_copy(update={"failure_class": diagnostic.failure_class})
    decision = optimize_decision(state)
    
    # 2. External API Call (Slow, OUTSIDE any DB transaction)
    # Pass event_id to Razorpay to handle crashes between this line and the DB commit
    client = get_execution_client()
    action_result = await client.execute_action(
        decision.selected_action.value, 
        idempotency_key=event_id,
        amount_inr=state.amount_inr,
    )
    
    audit_data = {
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "state": state.model_dump(mode="json"),
        "action": decision.selected_action.value,
        "action_result": action_result,
        "worker_id": WORKER_ID
    }

    # 3. Short, Fast DB Transaction
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "INSERT INTO audit_log (event_id, audit_json) VALUES (?, ?)", 
            (event_id, json.dumps(audit_data))
        )
        await db.execute(
            "INSERT INTO seen_events (event_id) VALUES (?)", 
            (event_id,)
        )
        await db.execute(
            "UPDATE inbox SET status='PROCESSED' WHERE event_id=?", 
            (event_id,)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

async def process_event(event_id: str, raw_payload: str, db: aiosqlite.Connection):
    try:
        payload = json.loads(raw_payload)
        await execute_pipeline(payload, event_id, db)
    except Exception as e:
        logger.exception(f"Failed to process event: {event_id}")
        await db.execute("UPDATE inbox SET status = 'FAILED', last_error = ? WHERE event_id = ?", (str(e), event_id))
        await db.commit()

async def run_decision_agent():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        while True:
            async with db.execute("SELECT event_id, raw_payload FROM inbox WHERE status = 'PENDING' LIMIT 1") as cursor:
                row = await cursor.fetchone()
            
            if row:
                event_id, raw_payload = row
                async with db.execute("UPDATE inbox SET status = 'PROCESSING' WHERE event_id = ? AND status = 'PENDING'", (event_id,)) as cursor:
                    if cursor.rowcount == 0:
                        continue # Claimed by another worker
                await db.commit()
                
                await process_event(event_id, raw_payload, db)
            else:
                await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(run_decision_agent())
