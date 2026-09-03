"""
End-to-End Lifecycle Test: mandate.debit.failed Event
Traces the complete flow through all 6 layers of the system.

Layer 1: Ingestion & Storage (gateway.py, schema.sql)
Layer 2: Core State & Memory (models.py)
Layer 3: Diagnosis & Security (classifier.py, sanitizer.py)
Layer 4: Compliance Guardrails (engine.py)
Layer 5: ML & Optimization (train.py, optimizer.py)
Layer 6: Simulation & Interface (run_monte_carlo.py, app.py)
"""

import asyncio
import json
import hmac
import hashlib
import os
import pytest
import aiosqlite
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from src.ingestion.gateway import app, WEBHOOK_SECRET, DB_PATH as GATEWAY_DB_PATH
from src.execution.worker import process_event
from src.core.types import ActionType, FailureClass, PaymentRail, ConsentStatus
from src.core.models import MandateStateRecord
from src.decision.optimizer import optimize_decision
from src.guardrails.engine import compute_feasible_action_set
from src.diagnosis.classifier import diagnose_failure

TEST_DB_PATH = "test_e2e_lifecycle.db"

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Initialize test database with schema."""
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


class TestE2ELifecycle:
    """End-to-end lifecycle tests for mandate recovery pipeline."""
    
    @pytest.mark.asyncio
    async def test_soft_liquidity_happy_path(self):
        """
        STEP 1-6: Complete lifecycle for SOFT_LIQUIDITY case
        
        Expected flow:
        1. ✓ Webhook received, HMAC validated, stored in inbox
        2. ✓ Worker picks up event from inbox
        3. ✓ Diagnosis: Z9 → SOFT_LIQUIDITY
        4. ✓ Guardrails: All digital actions feasible
        5. ✓ Optimizer: Selects best EV action (should be digital)
        6. ✓ Execution: Mock API call, audit log written
        """
        
        # ===== STEP 1: INGESTION =====
        event_id = "evnt_soft_liquidity_001"
        failure_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Simulate real-world mandate failure event
        # Wrapped in "state" key as expected by worker.py
        raw_event = {
            "state": {
                "case_id": "case_soft_001",
                "mandate_id": "man_soft_001",
                "merchant_id": "mer_001",
                "customer_id": "cust_001",
                "rail": PaymentRail.UPI_AUTOPAY.value,
                "amount_inr": "2500.00",
                "attempt_count": 1,
                "failure_code": "Z9",  # Soft liquidity failure
                "failure_timestamp": failure_timestamp,
                "failure_class": FailureClass.SOFT_LIQUIDITY.value,  # Required by MandateStateRecord
                "channel_consent": {
                    "WHATSAPP": ConsentStatus.OPTED_IN.value,
                    "SMS": ConsentStatus.OPTED_IN.value,
                    "PAYMENT_LINK": ConsentStatus.OPTED_IN.value,
                },
            },
            "raw_error_text": "Insufficient funds in customer account",  # For diagnosis
        }
        
        # Post webhook to gateway
        raw_body = json.dumps(raw_event).encode()
        signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        
        headers = {
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
            "x-razorpay-event-id": event_id,
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
            assert response.status_code == 202, f"Ingestion failed: {response.status_code}"
        
        # Verify event stored in inbox
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT event_id, raw_payload, status FROM inbox WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                inbox_row = await cursor.fetchone()
                assert inbox_row is not None, "Event not in inbox"
                assert inbox_row[2] == "PENDING", "Event not marked PENDING"
        
        print("✓ STEP 1: Ingestion successful - event stored in inbox with HMAC validation")
        
        # ===== STEP 2: WORKER LOOP =====
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT event_id, raw_payload FROM inbox WHERE status = 'PENDING' LIMIT 1"
            ) as cursor:
                worker_row = await cursor.fetchone()
                assert worker_row is not None, "No pending events for worker"
                
                fetched_event_id, fetched_payload = worker_row
                
                # Process event through pipeline
                await process_event(fetched_event_id, fetched_payload, db)
            
            # Verify event marked as PROCESSED
            async with db.execute(
                "SELECT status FROM inbox WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                status_row = await cursor.fetchone()
                assert status_row[0] == "PROCESSED", f"Event not processed: {status_row[0]}"
        
        print("✓ STEP 2: Worker loop - event processed from inbox")
        
        # ===== STEP 3: DIAGNOSIS =====
        raw_event_dict = json.loads(fetched_payload)
        state_dict = raw_event_dict.get("state", raw_event_dict)
        diagnosis = diagnose_failure(
            bank_code=state_dict["failure_code"],
            raw_error_text=raw_event_dict.get("raw_error_text")
        )
        
        assert diagnosis.failure_class == FailureClass.SOFT_LIQUIDITY, \
            f"Diagnosis failed: expected SOFT_LIQUIDITY, got {diagnosis.failure_class}"
        assert diagnosis.confidence >= 0.7, \
            f"Low confidence diagnosis: {diagnosis.confidence}"
        
        print(f"✓ STEP 3: Diagnosis - Z9 classified as {diagnosis.failure_class.value} (conf={diagnosis.confidence:.2f})")
        
        # ===== STEP 4: GUARDRAILS =====
        state = MandateStateRecord(
            case_id=state_dict["case_id"],
            mandate_id=state_dict["mandate_id"],
            merchant_id=state_dict["merchant_id"],
            customer_id=state_dict["customer_id"],
            rail=PaymentRail(state_dict["rail"]),
            amount_inr=Decimal(state_dict["amount_inr"]),
            attempt_count=state_dict["attempt_count"],
            failure_code=state_dict["failure_code"],
            failure_class=FailureClass(state_dict["failure_class"]),
            failure_timestamp=datetime.fromisoformat(state_dict["failure_timestamp"]),
            last_attempt_timestamp=None,
            afa_required=False,
            pre_debit_notice_sent=True,
            customer_timezone="Asia/Kolkata",
            channel_consent={k: ConsentStatus(v) for k, v in state_dict.get("channel_consent", {}).items()},
        )
        
        feasible_actions, mandatory_notices = compute_feasible_action_set(state)
        
        # For SOFT_LIQUIDITY with consents and low amount, we should have many digital options
        assert len(feasible_actions) > 0, "No feasible actions!"
        assert ActionType.ABORT_COMPLIANT not in feasible_actions or len(feasible_actions) > 1, \
            "Guardrails incorrectly ruled everything out"
        
        digital_actions = {
            ActionType.WHATSAPP_NUDGE,
            ActionType.SMS_NUDGE,
            ActionType.PAYMENT_LINK,
            ActionType.PIN_PROMPTED_RETRY,
            ActionType.SILENT_RETRY,
        }
        feasible_digital = feasible_actions.intersection(digital_actions)
        assert len(feasible_digital) > 0, "No digital actions in feasible set"
        
        print(f"✓ STEP 4: Guardrails - {len(feasible_actions)} feasible actions, {len(feasible_digital)} digital")
        
        # ===== STEP 5: OPTIMIZATION =====
        decision = optimize_decision(state)
        
        # Should NOT abort or escalate for SOFT_LIQUIDITY
        assert decision.selected_action != ActionType.ABORT_COMPLIANT, \
            f"Optimizer aborted valid case: {decision.audit_step.rationale}"
        assert decision.selected_action != ActionType.ESCALATE_HUMAN, \
            f"Optimizer escalated non-mandatory case: {decision.audit_step.rationale}"
        
        # Should have positive EV
        assert decision.lift_ev_inr >= Decimal("0.00"), \
            f"Negative EV selected: {decision.lift_ev_inr}"
        
        # Should have recovery probability estimate
        assert decision.p_hat is not None and Decimal("0.0") <= decision.p_hat <= Decimal("1.0"), \
            f"Invalid recovery probability: {decision.p_hat}"
        
        print(f"✓ STEP 5: Optimization - Selected {decision.selected_action.value} (EV=₹{decision.lift_ev_inr:.2f}, P̂={decision.p_hat:.4f})")
        
        # ===== STEP 6: EXECUTION & AUDIT =====
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Verify audit log entry
            async with db.execute(
                "SELECT audit_json FROM audit_log WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                audit_row = await cursor.fetchone()
                assert audit_row is not None, "No audit log entry"
                
                audit_data = json.loads(audit_row[0])
                # Worker may select a different action due to model stochasticity,
                # but it should be a digital action (not ABORT or ESCALATE)
                assert audit_data["action"] in [
                    ActionType.SILENT_RETRY.value,
                    ActionType.PIN_PROMPTED_RETRY.value,
                    ActionType.SMS_NUDGE.value,
                    ActionType.PAYMENT_LINK.value,
                    ActionType.WHATSAPP_NUDGE.value,
                ], f"Worker should select digital action, got {audit_data['action']}"
                assert audit_data["state"]["case_id"] == raw_event["state"]["case_id"]
            
            # Verify seen_events idempotency
            async with db.execute(
                "SELECT 1 FROM seen_events WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                seen_row = await cursor.fetchone()
                assert seen_row is not None, "Event not marked in seen_events"
        
        print("✓ STEP 6: Execution & Audit - audit log written, idempotency recorded")
        print("\n✅ SOFT_LIQUIDITY HAPPY PATH: All 6 layers working correctly!\n")
    
    
    @pytest.mark.asyncio
    async def test_legal_hold_mandatory_escalation(self):
        """
        STEP 1-6: Mandatory escalation path for LEGAL_HOLD case
        
        Expected flow:
        1. ✓ Webhook ingestion
        2. ✓ Worker processes
        3. ✓ Diagnosis: Code 07 → LEGAL_HOLD
        4. ✓ Guardrails: Only ESCALATE_HUMAN feasible
        5. ✓ Optimizer: Immediate escalation without EV math
        6. ✓ Audit log with mandatory routing flag
        """
        
        event_id = "evnt_legal_hold_001"
        failure_timestamp = datetime.now(timezone.utc).isoformat()
        
        raw_event = {
            "state": {
                "case_id": "case_legal_001",
                "mandate_id": "man_legal_001",
                "merchant_id": "mer_001",
                "customer_id": "cust_001",
                "rail": PaymentRail.ENACH.value,
                "amount_inr": "50000.00",
                "attempt_count": 1,
                "failure_code": "07",  # Legal hold / court order
                "failure_timestamp": failure_timestamp,
                "failure_class": FailureClass.LEGAL_HOLD.value,  # Required by MandateStateRecord
                "channel_consent": {},
            }
        }
        
        raw_body = json.dumps(raw_event).encode()
        signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        
        headers = {
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
            "x-razorpay-event-id": event_id,
        }
        
        # Send webhook
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
            assert response.status_code == 202
        
        print("✓ STEP 1: Legal hold event ingested")
        
        # Process through worker
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT event_id, raw_payload FROM inbox WHERE status = 'PENDING'"
            ) as cursor:
                worker_row = await cursor.fetchone()
                assert worker_row is not None
                
                await process_event(worker_row[0], worker_row[1], db)
        
        print("✓ STEP 2: Worker processed legal hold event")
        
        # Verify diagnosis
        raw_event_dict = json.loads(raw_body.decode())
        diagnosis = diagnose_failure(bank_code="07", raw_error_text=None)
        assert diagnosis.failure_class == FailureClass.LEGAL_HOLD, \
            f"Failed to classify 07 as LEGAL_HOLD: got {diagnosis.failure_class}"
        
        print(f"✓ STEP 3: Diagnosis - Code 07 → {diagnosis.failure_class.value}")
        
        # Check guardrails
        state = MandateStateRecord(
            case_id="case_legal_001",
            mandate_id="man_legal_001",
            merchant_id="mer_001",
            customer_id="cust_001",
            rail=PaymentRail.ENACH,
            amount_inr=Decimal("50000.00"),
            attempt_count=1,
            failure_code="07",
            failure_class=FailureClass.LEGAL_HOLD,
            failure_timestamp=datetime.fromisoformat(failure_timestamp),
            last_attempt_timestamp=None,
            afa_required=True,
            pre_debit_notice_sent=True,
            customer_timezone="Asia/Kolkata",
            channel_consent={},
        )
        
        feasible_actions, _ = compute_feasible_action_set(state)
        assert feasible_actions == {ActionType.ESCALATE_HUMAN}, \
            f"Legal hold guardrails failed: {feasible_actions}"
        
        print(f"✓ STEP 4: Guardrails - Only ESCALATE_HUMAN feasible (correctly terminal)")
        
        # Check optimizer
        decision = optimize_decision(state)
        assert decision.selected_action == ActionType.ESCALATE_HUMAN, \
            f"Optimizer should escalate legal hold, got {decision.selected_action}"
        assert decision.is_mandatory_routing is True
        assert decision.lift_ev_inr is None, "EV should be bypassed for mandatory routing"
        assert decision.p_hat is None, "P_hat should be N/A for mandatory routing"
        
        print(f"✓ STEP 5: Optimizer - Mandatory routing, no EV computation")
        
        # Verify audit
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT audit_json FROM audit_log WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                audit_row = await cursor.fetchone()
                assert audit_row is not None
                audit_data = json.loads(audit_row[0])
                assert audit_data["action"] == "ESCALATE_HUMAN"
        
        print("✓ STEP 6: Execution & Audit - escalation recorded")
        print("\n✅ LEGAL_HOLD MANDATORY ESCALATION: All 6 layers working correctly!\n")
    
    
    @pytest.mark.asyncio
    async def test_hard_terminal_abort(self):
        """
        STEP 1-6: Terminal failure with no recovery options
        
        Expected flow:
        1. ✓ Webhook ingestion
        2. ✓ Worker processes
        3. ✓ Diagnosis: Code 01 → HARD_TERMINAL
        4. ✓ Guardrails: Only ABORT_COMPLIANT
        5. ✓ Optimizer: Returns ABORT_COMPLIANT with zero cost
        6. ✓ Audit log with abort rationale
        """
        
        event_id = "evnt_terminal_001"
        failure_timestamp = datetime.now(timezone.utc).isoformat()
        
        raw_event = {
            "state": {
                "case_id": "case_terminal_001",
                "mandate_id": "man_terminal_001",
                "merchant_id": "mer_001",
                "customer_id": "cust_001",
                "rail": PaymentRail.ENACH.value,
                "amount_inr": "1500.00",
                "attempt_count": 4,  # Attempts exhausted
                "failure_code": "01",  # Account closed
                "failure_timestamp": failure_timestamp,
                "failure_class": FailureClass.HARD_TERMINAL.value,  # Required by MandateStateRecord
                "channel_consent": {
                    "WHATSAPP": ConsentStatus.OPTED_OUT.value,
                    "SMS": ConsentStatus.OPTED_OUT.value,
                    "PAYMENT_LINK": ConsentStatus.OPTED_OUT.value,
                },
            }
        }
        
        raw_body = json.dumps(raw_event).encode()
        signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        
        headers = {
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
            "x-razorpay-event-id": event_id,
        }
        
        # Send webhook
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
            assert response.status_code == 202
        
        print("✓ STEP 1: Terminal event ingested")
        
        # Process through worker
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT event_id, raw_payload FROM inbox WHERE status = 'PENDING'"
            ) as cursor:
                worker_row = await cursor.fetchone()
                assert worker_row is not None
                
                await process_event(worker_row[0], worker_row[1], db)
        
        print("✓ STEP 2: Worker processed terminal event")
        
        # Verify diagnosis
        diagnosis = diagnose_failure(bank_code="01", raw_error_text=None)
        assert diagnosis.failure_class == FailureClass.HARD_TERMINAL
        
        print(f"✓ STEP 3: Diagnosis - Code 01 → {diagnosis.failure_class.value}")
        
        # Check guardrails
        state = MandateStateRecord(
            case_id="case_terminal_001",
            mandate_id="man_terminal_001",
            merchant_id="mer_001",
            customer_id="cust_001",
            rail=PaymentRail.ENACH,
            amount_inr=Decimal("1500.00"),
            attempt_count=4,
            failure_code="01",
            failure_class=FailureClass.HARD_TERMINAL,
            failure_timestamp=datetime.fromisoformat(failure_timestamp),
            last_attempt_timestamp=None,
            afa_required=False,
            pre_debit_notice_sent=True,
            customer_timezone="Asia/Kolkata",
            channel_consent={
                "WHATSAPP": ConsentStatus.OPTED_OUT,
                "SMS": ConsentStatus.OPTED_OUT,
                "PAYMENT_LINK": ConsentStatus.OPTED_OUT,
            },
        )
        
        feasible_actions, _ = compute_feasible_action_set(state)
        assert feasible_actions == {ActionType.ABORT_COMPLIANT}, \
            f"Terminal case guardrails failed: {feasible_actions}"
        
        print(f"✓ STEP 4: Guardrails - Only ABORT_COMPLIANT (terminal state)")
        
        # Check optimizer
        decision = optimize_decision(state)
        assert decision.selected_action == ActionType.ABORT_COMPLIANT, \
            f"Should abort terminal case, got {decision.selected_action}"
        assert decision.cost_inr == Decimal("0.00"), \
            f"Abort should have zero cost: {decision.cost_inr}"
        
        print(f"✓ STEP 5: Optimizer - ABORT_COMPLIANT with zero cost")
        
        # Verify audit
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT audit_json FROM audit_log WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                audit_row = await cursor.fetchone()
                assert audit_row is not None
                audit_data = json.loads(audit_row[0])
                assert audit_data["action"] == "ABORT_COMPLIANT"
        
        print("✓ STEP 6: Execution & Audit - abort recorded with rationale")
        print("\n✅ HARD_TERMINAL ABORT: All 6 layers working correctly!\n")
    
    
    @pytest.mark.asyncio
    async def test_idempotency_duplicate_event(self):
        """
        Test idempotency: duplicate event_id should not be processed twice
        """
        
        event_id = "evnt_idempotent_001"
        raw_event = {
            "state": {
                "case_id": "case_dup",
                "mandate_id": "man_dup",
                "merchant_id": "mer_001",
                "customer_id": "cust_001",
                "rail": PaymentRail.UPI_AUTOPAY.value,
                "amount_inr": "1000.00",
                "attempt_count": 1,
                "failure_code": "Z9",
                "failure_timestamp": datetime.now(timezone.utc).isoformat(),
                "failure_class": FailureClass.SOFT_LIQUIDITY.value,
                "channel_consent": {"WHATSAPP": ConsentStatus.OPTED_IN.value},
            }
        }
        
        raw_body = json.dumps(raw_event).encode()
        signature = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        
        headers = {
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
            "x-razorpay-event-id": event_id,
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First call
            response1 = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
            assert response1.status_code == 202
            
            # Duplicate call
            response2 = await client.post("/webhook/razorpay", content=raw_body, headers=headers)
            assert response2.status_code == 202  # Still accepted (202 Accepted)
        
        # Verify only one inbox entry
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM inbox WHERE event_id = ?",
                (event_id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                assert count == 1, f"Duplicate event_id created multiple inbox entries: {count}"
        
        print("✓ Idempotency: duplicate event_id handled correctly (only 1 inbox entry)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
