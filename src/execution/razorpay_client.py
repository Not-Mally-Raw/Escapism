import asyncio
import json
import os
import time
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import httpx


class MockRazorpayClient:
    async def execute_action(self, selected_action: str, idempotency_key: str, **_: Any) -> dict:
        await asyncio.sleep(0.1)
        result = {
            "id": f"mock_{uuid4()}",
            "action": selected_action,
            "status": "created",
            "idempotency_key": idempotency_key,
            "mode": "mock",
        }
        self._log_call(result)
        return result

    def _log_call(self, result: dict):
        with open("razorpay_calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")


class RazorpayClient:
    """
    Minimal real Razorpay test-mode client for bounded recovery actions.

    Razorpay documents Payment Links as POST /v1/payment_links with Basic Auth.
    The public idempotency header is documented for payouts, not Payment Links,
    so external traceability uses reference_id while local exactly-once behavior
    stays in the webhook inbox/audit tables.
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
                "mode": "live",
            }

        if selected_action in {"PAYMENT_LINK", "WHATSAPP_NUDGE", "SMS_NUDGE", "RE_MANDATE_FLOW", "PIN_PROMPTED_RETRY"}:
            return await self.create_payment_link(
                amount_inr=amount_inr or Decimal("1.00"),
                reference_id=idempotency_key[:40],
                description=description or f"Recovery workflow action: {selected_action}",
                customer_contact=customer_contact,
                customer_email=customer_email,
            )

        return {
            "id": None,
            "action": selected_action,
            "status": "not_dispatched",
            "reason": "unsupported_external_action",
            "mode": "live",
        }

    async def create_payment_link(
        self,
        amount_inr: Decimal,
        reference_id: str,
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
                "name": "Revenue Recovery Test Customer",
                "contact": customer_contact,
                "email": customer_email,
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": True,
            "notes": {"source": "razorpay-revenue-recovery", "workflow_reference": reference_id},
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(
                f"{self.base_url}/payment_links",
                json=payload,
                auth=(self.key_id, self.key_secret),
                headers={"Content-Type": "application/json"},
            )
        response.raise_for_status()
        data = response.json()
        data["mode"] = "live"
        return data

    async def fetch_payment_link_status(self, payment_link_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(
                f"{self.base_url}/payment_links/{payment_link_id}",
                auth=(self.key_id, self.key_secret),
            )
        response.raise_for_status()
        return response.json()


def get_execution_client():
    mode = os.getenv("RAZORPAY_EXECUTION_MODE", "mock").lower()
    if mode == "live":
        return RazorpayClient()
    return MockRazorpayClient()
