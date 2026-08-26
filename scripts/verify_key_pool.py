"""
Key Pool Health Validator.
Validates all Groq API keys present in .env without leaking key values to logs.
Tests each key against available Groq models to find all working key-model pairs.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

# Active Groq models in production
PROBE_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "groq/compound",
]

def load_all_keys_from_env() -> list[str]:
    keys = []
    env_path = Path(".env")
    if not env_path.exists():
        return keys

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Match any line containing a gsk_ pattern
            match = re.search(r"(gsk_[a-zA-Z0-9_-]+)", line)
            if match:
                k = match.group(1).strip()
                if k not in keys:
                    keys.append(k)
    return keys

def probe_key(key: str, key_idx: int) -> dict:
    masked_key = f"Key #{key_idx:02d} (len={len(key)}, prefix={key[:8]}...)"
    
    for model in PROBE_MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "KeyValidator/1.0",
            },
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=6.0) as res:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "masked_key": masked_key,
                    "working": True,
                    "model": model,
                    "latency_ms": latency_ms,
                    "error": None,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            # If model_not_found or decommissioned, try next model with same key
            if any(k in err_body for k in ["model_not_found", "does not exist", "decommissioned", "not found"]):
                continue
            return {
                "masked_key": masked_key,
                "working": False,
                "model": model,
                "latency_ms": 0.0,
                "error": f"HTTP {e.code}: {err_body[:80]}",
            }
        except Exception as e:
            return {
                "masked_key": masked_key,
                "working": False,
                "model": model,
                "latency_ms": 0.0,
                "error": f"{type(e).__name__}: {str(e)}",
            }

    return {
        "masked_key": masked_key,
        "working": False,
        "model": "all",
        "latency_ms": 0.0,
        "error": "All candidate models failed for this key.",
    }

def main():
    keys = load_all_keys_from_env()
    print("=" * 80)
    print(f"GROQ API KEY POOL HEALTH CHECK: Found {len(keys)} key candidate(s) in .env")
    print("=" * 80)

    working_count = 0
    for idx, k in enumerate(keys, 1):
        result = probe_key(k, idx)
        if result["working"]:
            working_count += 1
            print(f"  [PASS] {result['masked_key']} -> ACTIVE | Model: {result['model']} | Ping: {result['latency_ms']:.1f}ms")
        else:
            print(f"  [FAIL] {result['masked_key']} -> {result['error']}")

    print("-" * 80)
    print(f"Summary: {working_count}/{len(keys)} keys verified functional.")
    print("=" * 80)

if __name__ == "__main__":
    main()
