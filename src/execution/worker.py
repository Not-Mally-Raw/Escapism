"""
Razorpay Revenue Recovery Execution Worker.

Responsibilities:
- Ingest canonical events from SQLite inbox.
- Evaluate guardrails and deterministic decision optimization.
- Record explicit execution intent in SQLite prior to external dispatch (replay safety).
- Enforce idempotency keys across retries.
- Support deterministic outcome reconciliation for interrupted executions.
- Bounded exponential backoff retries with clean transitions to DEAD_LETTER state upon terminal failures.
- Expand audit log records to durably store raw event ID, diagnostic output, feasible action set,
  candidate scores, model version hash, decision, and gateway receipt.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from src.core.models import MandateStateRecord
from src.core.types import ActionType
from src.diagnosis.classifier import diagnose_failure
from src.decision.optimizer import optimize_decision
from src.guardrails.engine import compute_feasible_action_set
from src.execution.razorpay_client import get_execution_client, MockRazorpayClient, RazorpayClient
from src.ingestion.adapter import RazorpayEventAdapter
from src.ingestion.models import WebhookIngestionError
from src.ml.inference import get_model_version_hash

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("WORKER_DB_PATH", "webhook.db")
WORKER_ID = os.getenv("WORKER_ID", "worker-01")
MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
INITIAL_BACKOFF_SECONDS = float(os.getenv("WORKER_INITIAL_BACKOFF", "1.0"))
BACKOFF_FACTOR = float(os.getenv("WORKER_BACKOFF_FACTOR", "2.0"))
MAX_BACKOFF_SECONDS = float(os.getenv("WORKER_MAX_BACKOFF", "60.0"))


def compute_backoff_delay(retry_count: int) -> float:
    """
    Computes bounded exponential backoff delay in seconds.
    Formula: min(INITIAL_BACKOFF * (BACKOFF_FACTOR ** (retry_count - 1)), MAX_BACKOFF)
    """
    if retry_count <= 0:
        return 0.0
    delay = INITIAL_BACKOFF_SECONDS * (BACKOFF_FACTOR ** (retry_count - 1))
    return min(delay, MAX_BACKOFF_SECONDS)


async def record_execution_intent(
    db: aiosqlite.Connection,
    event_id: str,
    action: str,
    idempotency_key: str,
    payload_dict: Optional[dict] = None,
) -> str:
    """
    Records an explicit execution intent in SQLite before dispatching external API calls.
    Returns the unique intent_id.
    """
    intent_id = f"intent_{event_id}"
    payload_json = json.dumps(payload_dict) if payload_dict else None
    
    await db.execute("BEGIN IMMEDIATE")
    try:
        await db.execute(
            """
            INSERT INTO execution_intents (intent_id, event_id, action, idempotency_key, status, payload_json)
            VALUES (?, ?, ?, ?, 'PENDING', ?)
            ON CONFLICT(intent_id) DO UPDATE SET
                action = excluded.action,
                updated_at = CURRENT_TIMESTAMP
            """,
            (intent_id, event_id, action, idempotency_key, payload_json),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return intent_id


async def execute_pipeline(
    payload: dict | str,
    event_id: str,
    db: aiosqlite.Connection,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes the full recovery pipeline with replay-safe execution intent and expanded audit logging.
    """
    # 1. Ingest and adapt canonical parsed event from raw payload or dict
    ingestion_result = RazorpayEventAdapter.parse_event(payload, event_id=event_id)
    state = ingestion_result.state
    diagnostic = ingestion_result.diagnostic

    # 2. Evaluate Guardrails & Decision Optimization (Certified Static Lift-EV default path)
    feasible_actions, _ = compute_feasible_action_set(state)
    decision = optimize_decision(state)
    selected_action_str = decision.selected_action.value
    intent_id = f"intent_{event_id}"

    # 3. Check for existing completed intent (Replay-safe check)
    action_result = None
    async with db.execute(
        "SELECT status, receipt_json FROM execution_intents WHERE intent_id = ?",
        (intent_id,),
    ) as cursor:
        intent_row = await cursor.fetchone()

    if intent_row and intent_row[0] in ("COMPLETED", "RECONCILED") and intent_row[1]:
        logger.info(f"[Worker] Intent {intent_id} already completed. Reusing cached gateway receipt.")
        action_result = json.loads(intent_row[1])
    else:
        # 4. Record Execution Intent in SQLite BEFORE external dispatch
        intent_payload = {
            "amount_inr": str(state.amount_inr),
            "action": selected_action_str,
            "case_id": state.case_id,
            "mandate_id": state.mandate_id,
        }
        await record_execution_intent(
            db=db,
            event_id=event_id,
            action=selected_action_str,
            idempotency_key=event_id,
            payload_dict=intent_payload,
        )

        # 5. External API Call (Slow, OUTSIDE any DB transaction)
        exec_client = client or get_execution_client()
        action_result = await exec_client.execute_action(
            selected_action_str,
            idempotency_key=event_id,
            amount_inr=state.amount_inr,
        )

        # Update intent to DISPATCHED
        try:
            await db.execute(
                "UPDATE execution_intents SET status = 'DISPATCHED', receipt_json = ?, updated_at = CURRENT_TIMESTAMP WHERE intent_id = ?",
                (json.dumps(action_result), intent_id),
            )
            await db.commit()
        except Exception as e:
            logger.debug(f"Failed to update intent to DISPATCHED: {e}")

    # 6. Assemble Expanded Audit Log
    model_version_hash = get_model_version_hash()
    audit_data = {
        "event_id": event_id,
        "raw_event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "state": state.model_dump(mode="json"),
        "diagnostic": diagnostic.model_dump(mode="json"),
        "feasible_action_set": sorted([a.value for a in feasible_actions]),
        "candidate_scores": [cs.model_dump(mode="json") for cs in decision.candidate_scores],
        "model_version_hash": model_version_hash,
        "action": selected_action_str,
        "action_result": action_result,
        "gateway_receipt": action_result,
        "decision": decision.model_dump(mode="json"),
        "worker_id": WORKER_ID,
        "intent_id": intent_id,
    }

    # 7. Short, Fast Atomic DB Transaction to finalize
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "INSERT INTO audit_log (event_id, audit_json) VALUES (?, ?)",
            (event_id, json.dumps(audit_data)),
        )
        await db.execute(
            """
            INSERT INTO seen_events (event_id, processed_at) VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(event_id) DO UPDATE SET processed_at = CURRENT_TIMESTAMP
            """,
            (event_id,),
        )
        await db.execute(
            "UPDATE execution_intents SET status = 'COMPLETED', receipt_json = ?, updated_at = CURRENT_TIMESTAMP WHERE intent_id = ?",
            (json.dumps(action_result), intent_id),
        )
        await db.execute(
            "UPDATE inbox SET status='PROCESSED', last_error = NULL WHERE event_id=?",
            (event_id,),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return audit_data


async def process_event(
    event_id: str,
    raw_payload: str,
    db: aiosqlite.Connection,
    client: Optional[Any] = None,
):
    """
    Processes an event from inbox with bounded exponential backoff retries and DLQ transitions.
    Unrecoverable parsing / schema errors fail closed immediately to FAILED and log to DLQ.
    """
    try:
        await execute_pipeline(raw_payload, event_id, db, client=client)
    except WebhookIngestionError as e:
        error_type = type(e).__name__
        error_msg = str(e)
        formatted_error = f"{error_type}: {error_msg}"
        logger.error(f"Non-retryable ingestion error for event {event_id}: {formatted_error}")
        try:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "UPDATE inbox SET status = 'FAILED', last_error = ? WHERE event_id = ?",
                (formatted_error, event_id),
            )
            await db.execute(
                """
                INSERT INTO dead_letter_queue (event_id, raw_payload, error_type, error_message, attempt_count)
                VALUES (?, ?, ?, ?, 1)
                """,
                (event_id, str(raw_payload), error_type, error_msg),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.exception(f"Failed to process event: {event_id} - {error_type}: {error_msg}")

        # Retrieve current retry count from inbox
        async with db.execute(
            "SELECT retry_count FROM inbox WHERE event_id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
            current_retries = row[0] if row and row[0] is not None else 0

        new_retry_count = current_retries + 1

        if new_retry_count >= MAX_RETRIES:
            # Terminal failure: Transition to DEAD_LETTER state and log to DLQ table
            logger.error(
                f"Event {event_id} exceeded maximum retries ({MAX_RETRIES}). Transitioning to DEAD_LETTER."
            )
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "UPDATE inbox SET status = 'DEAD_LETTER', retry_count = ?, last_error = ? WHERE event_id = ?",
                    (new_retry_count, f"Terminal failure [{error_type}]: {error_msg}", event_id),
                )
                await db.execute(
                    """
                    INSERT INTO dead_letter_queue (event_id, raw_payload, error_type, error_message, attempt_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (event_id, str(raw_payload), error_type, error_msg, new_retry_count),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        else:
            # Bounded exponential backoff retry scheduling
            delay = compute_backoff_delay(new_retry_count)
            next_retry = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            logger.warning(
                f"Event {event_id} failed attempt {new_retry_count}/{MAX_RETRIES}. "
                f"Retrying in {delay:.2f}s at {next_retry}."
            )
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "UPDATE inbox SET status = 'PENDING', retry_count = ?, last_error = ?, next_retry_at = ? WHERE event_id = ?",
                    (new_retry_count, f"Retry {new_retry_count} [{error_type}]: {error_msg}", next_retry, event_id),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise


async def reconcile_interrupted_executions(
    db: aiosqlite.Connection,
    client: Optional[Any] = None,
) -> int:
    """
    Deterministic outcome reconciliation for interrupted executions.
    Scans execution_intents with status PENDING or DISPATCHED, verifies status with gateway,
    and reconciles to completion or prepares for clean retry.
    Returns the number of reconciled executions.
    """
    exec_client = client or get_execution_client()
    reconciled_count = 0

    async with db.execute(
        """
        SELECT intent_id, event_id, action, idempotency_key, status, receipt_json, payload_json
        FROM execution_intents
        WHERE status IN ('PENDING', 'DISPATCHED')
        """
    ) as cursor:
        interrupted_rows = await cursor.fetchall()

    for row in interrupted_rows:
        intent_id, event_id, action, idempotency_key, status, receipt_json, payload_json = row
        logger.info(f"[Reconciliation] Reconciling interrupted intent {intent_id} (status: {status})...")

        # 1. Check if gateway has record of the action
        receipt = None
        if receipt_json:
            try:
                receipt = json.loads(receipt_json)
            except Exception:
                receipt = None

        if not receipt and hasattr(exec_client, "fetch_action_status"):
            receipt = await exec_client.fetch_action_status(idempotency_key)

        if receipt:
            # Gateway completed the action: finalize intent and inbox
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "UPDATE execution_intents SET status = 'RECONCILED', receipt_json = ?, updated_at = CURRENT_TIMESTAMP WHERE intent_id = ?",
                    (json.dumps(receipt), intent_id),
                )
                await db.execute(
                    """
                    INSERT INTO seen_events (event_id, processed_at) VALUES (?, CURRENT_TIMESTAMP)
                    ON CONFLICT(event_id) DO UPDATE SET processed_at = CURRENT_TIMESTAMP
                    """,
                    (event_id,),
                )
                await db.execute(
                    "UPDATE inbox SET status = 'PROCESSED', last_error = NULL WHERE event_id = ?",
                    (event_id,),
                )
                await db.commit()
                reconciled_count += 1
                logger.info(f"[Reconciliation] Successfully reconciled intent {intent_id}.")
            except Exception as e:
                await db.rollback()
                logger.error(f"[Reconciliation] Failed to commit reconciled intent {intent_id}: {e}")
        else:
            # Action was never executed at gateway: reset intent to PENDING for clean replay
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "UPDATE inbox SET status = 'PENDING' WHERE event_id = ? AND status = 'PROCESSING'",
                    (event_id,),
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"[Reconciliation] Failed to reset inbox for intent {intent_id}: {e}")

    return reconciled_count


async def run_decision_agent(db_path: str = DB_PATH):
    """
    Background worker process polling the inbox queue.
    Performs startup reconciliation and continuous dispatch.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        
        # 1. Startup deterministic reconciliation
        await reconcile_interrupted_executions(db)

        # 2. Main processing loop
        while True:
            now_iso = datetime.now(timezone.utc).isoformat()
            async with db.execute(
                """
                SELECT event_id, raw_payload FROM inbox
                WHERE status = 'PENDING' AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY received_at ASC
                LIMIT 1
                """,
                (now_iso,),
            ) as cursor:
                row = await cursor.fetchone()

            if row:
                event_id, raw_payload = row
                async with db.execute(
                    "UPDATE inbox SET status = 'PROCESSING' WHERE event_id = ? AND status = 'PENDING'",
                    (event_id,),
                ) as cursor:
                    if cursor.rowcount == 0:
                        continue  # Claimed by another worker process

                await db.commit()
                await process_event(event_id, raw_payload, db)
            else:
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(run_decision_agent())
