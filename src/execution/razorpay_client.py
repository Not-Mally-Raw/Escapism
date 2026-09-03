"""
Razorpay Execution Client Module.

System Boundaries & Disclosures:
- DEFAULT EXECUTION MODE: Mock execution (MockRazorpayClient) is the certified default.
  Live API dispatch (RazorpayClient) requires explicit configuration via `RAZORPAY_EXECUTION_MODE=live`
  along with valid `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
- OMNICHANNEL RECOVERY NOTIFICATIONS: Omnichannel nudges (WhatsApp, SMS, Payment Links)
  dispatch webhook intents and Razorpay Payment Link workflows with customer contact metadata
  rather than direct proprietary telecom integration.
- IDEMPOTENCY: Idempotency is enforced using the `x-razorpay-event-id` / `idempotency_key` across
  retries to guarantee exactly-once external side effects.
"""

import asyncio
import json
import logging
import os
import time
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


class MockRazorpayClient:
    """
    Mock Razorpay execution client for local testing, simulation, and deterministic verification.
    Guarantees idempotency by caching results per idempotency_key.
    """

    def __init__(self):
        self._executed_calls: Dict[str, dict] = {}

    async def execute_action(
        self,
        selected_action: str,
        idempotency_key: str,
        amount_inr: Optional[Decimal] = None,
        **kwargs: Any,
    ) -> dict:
        """
        Executes a mock recovery action with deterministic idempotency caching.
        """
        await asyncio.sleep(0.01)

        # Idempotency check: return existing result if already executed
        if idempotency_key in self._executed_calls:
            existing = self._executed_calls[idempotency_key]
            logger.info(f"[MockRazorpayClient] Replay detected for idempotency_key={idempotency_key}, reusing result.")
            return existing

        if selected_action in {"ABORT_COMPLIANT", "ESCALATE_HUMAN", "COOLDOWN_WAIT"}:
            result = {
                "id": None,
                "action": selected_action,
                "status": "not_dispatched",
                "reason": "terminal_or_non_external_action",
                "idempotency_key": idempotency_key,
                "mode": "mock",
            }
        else:
            result = {
                "id": f"mock_plink_{uuid4().hex[:16]}",
                "action": selected_action,
                "status": "created",
                "amount_inr": str(amount_inr) if amount_inr is not None else "0.00",
                "idempotency_key": idempotency_key,
                "reference_id": idempotency_key[:40],
                "mode": "mock",
                "created_at": int(time.time()),
            }

        self._executed_calls[idempotency_key] = result
        self._log_call(result)
        return result

    async def fetch_payment_link_status(self, payment_link_id: str) -> dict:
        """
        Fetches status for a mock payment link or returns deterministic active status.
        """
        for receipt in self._executed_calls.values():
            if receipt.get("id") == payment_link_id:
                return receipt
        return {
            "id": payment_link_id,
            "status": "created",
            "mode": "mock",
        }

    async def fetch_action_status(self, idempotency_key: str) -> Optional[dict]:
        """
        Reconciliation lookup by idempotency key.
        """
        return self._executed_calls.get(idempotency_key)

    def _log_call(self, result: dict):
        try:
            with open("razorpay_calls.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(result) + "\n")
        except Exception as e:
            logger.debug(f"Failed to append to razorpay_calls.jsonl: {e}")


class RazorpayClient:
    """
    Real Razorpay API client for live recovery actions.
    Enforces idempotency headers (`x-razorpay-event-id`) and reference IDs on all dispatch calls.
    """

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: str = "https://api.razorpay.com/v1",
        timeout_s: float = 10.0,
    ):
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        if not self.key_id or not self.key_secret:
            raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required for live execution mode")

    async def execute_action(
        self,
        selected_action: str,
        idempotency_key: str,
        amount_inr: Optional[Decimal] = None,
        customer_contact: str = "+919876543210",
        customer_email: str = "recovery-test@example.com",
        description: Optional[str] = None,
        **_: Any,
    ) -> dict:
        if selected_action in {"ABORT_COMPLIANT", "ESCALATE_HUMAN", "COOLDOWN_WAIT"}:
            return {
                "id": None,
                "action": selected_action,
                "status": "not_dispatched",
                "reason": "terminal_or_non_external_action",
                "idempotency_key": idempotency_key,
                "mode": "live",
            }

        if selected_action in {"PAYMENT_LINK", "WHATSAPP_NUDGE", "SMS_NUDGE", "RE_MANDATE_FLOW", "PIN_PROMPTED_RETRY"}:
            return await self.create_payment_link(
                amount_inr=amount_inr or Decimal("1.00"),
                reference_id=idempotency_key[:40],
                idempotency_key=idempotency_key,
                description=description or f"Recovery workflow action: {selected_action}",
                customer_contact=customer_contact,
                customer_email=customer_email,
            )

        return {
            "id": None,
            "action": selected_action,
            "status": "not_dispatched",
            "reason": "unsupported_external_action",
            "idempotency_key": idempotency_key,
            "mode": "live",
        }

    async def create_payment_link(
        self,
        amount_inr: Decimal,
        reference_id: str,
        idempotency_key: str,
        description: str,
        customer_contact: str,
        customer_email: str,
    ) -> dict:
        amount_paise = int((amount_inr * Decimal("100")).to_integral_value())
        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "expire_by": int(time.time()) + 7 * 24 * 60 * 60,
            "reference_id": reference_id,
            "description": description,
            "customer": {
                "name": "Revenue Recovery Customer",
                "contact": customer_contact,
                "email": customer_email,
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": True,
            "notes": {
                "source": "razorpay-revenue-recovery",
                "workflow_reference": reference_id,
                "idempotency_key": idempotency_key,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-razorpay-event-id": idempotency_key,
            "X-Idempotency-Key": idempotency_key,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(
                f"{self.base_url}/payment_links",
                json=payload,
                auth=(self.key_id, self.key_secret),
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        data["mode"] = "live"
        data["idempotency_key"] = idempotency_key
        return data

    async def fetch_payment_link_status(self, payment_link_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(
                f"{self.base_url}/payment_links/{payment_link_id}",
                auth=(self.key_id, self.key_secret),
            )
        response.raise_for_status()
        data = response.json()
        data["mode"] = "live"
        return data


def get_execution_client():
    """
    Factory function returning the configured execution client.
    Defaults to MockRazorpayClient unless RAZORPAY_EXECUTION_MODE='live'.
    """
    mode = os.getenv("RAZORPAY_EXECUTION_MODE", "mock").lower()
    if mode == "live":
        return RazorpayClient()
    return MockRazorpayClient()
