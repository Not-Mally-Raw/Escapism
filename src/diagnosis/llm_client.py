"""
Live LLM Client for Semantic Diagnosis.
Executes structured output completion against OpenAI or compatible API endpoints.
Enforces DiagnosticOutput schema locking (extra="forbid") and fail-closed timeout boundaries.
"""
import json
import os
import urllib.request
import urllib.error
from typing import Optional

from src.core.types import FailureClass
from src.diagnosis.models import DiagnosticOutput

DIAGNOSTIC_SYSTEM_PROMPT = """You are a precise banking payment failure diagnostic classifier for Indian recurring mandates (UPI AutoPay and e-NACH).
Your task is to analyze the provided raw bank error code and sanitized error message, and classify it into exactly one of the five canonical FailureClass categories:

Canonical Categories:
1. SOFT_LIQUIDITY: Insufficient funds, low balance, customer liquidity exhaustion, or collect request timeout (Z9, 04, U69).
2. TECHNICAL_RETRYABLE: Transient bank switch outages, network timeouts, or rate limiting (U28, Z7, 91).
3. HARD_TERMINAL: Permanent fatal failures such as account closed, invalid account number, dormant/inoperative account, mandate revoked by customer, or ticket amount limit exceeded (01, 02, 05, 06, Z8, AP01, AP02, AP04, AP05).
4. LEGAL_HOLD: Regulatory freeze, court order, litigation, or law enforcement freeze (07, AP03).
5. AMBIGUOUS_DECLINE: Indeterminate generic declines with insufficient diagnostic evidence (U19, U30, uncatalogued generic codes).

Rules:
- Output MUST be valid JSON conforming strictly to the schema:
  {
    "failure_class": "SOFT_LIQUIDITY" | "TECHNICAL_RETRYABLE" | "HARD_TERMINAL" | "LEGAL_HOLD" | "AMBIGUOUS_DECLINE",
    "confidence": <float between 0.0 and 1.0>,
    "evidence": [<string reason 1>, <string reason 2>]
  }
- If the error text is contradictory, vague, or generic, assign a low confidence (<= 0.40) and classify as AMBIGUOUS_DECLINE.
- Do NOT output any markdown formatting, backticks, or extra fields. Output raw JSON only.
"""

def call_live_llm(
    bank_code: str,
    sanitized_text: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    timeout_seconds: float = 8.0,
) -> tuple[DiagnosticOutput, str]:
    """
    Calls OpenAI Chat Completions API with strict JSON object formatting.
    Returns tuple of (DiagnosticOutput, raw_json_response_string).
    """
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not resolved_api_key:
        raise ValueError("No LLM API key configured in environment (OPENAI_API_KEY or LLM_API_KEY).")

    user_prompt = f"Bank Code: {bank_code}\nSanitized Error Text: {sanitized_text}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DIAGNOSTIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_api_key}",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        res_body = response.read().decode("utf-8")
        data = json.loads(res_body)
        content_str = data["choices"][0]["message"]["content"]
        
        # Enforce strict schema validation (extra="forbid" on DiagnosticOutput)
        parsed_diagnosis = DiagnosticOutput.model_validate_json(content_str)
        return parsed_diagnosis, content_str
