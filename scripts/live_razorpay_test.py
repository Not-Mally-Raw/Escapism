import os
import httpx
import json

# Parse .env manually
env_file = ".env"
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

key_id = os.getenv("RAZORPAY_KEY_ID")
key_secret = os.getenv("RAZORPAY_KEY_SECRET")

if not key_id or "YourKeyHere" in key_id:
    print("⚠️  No real Razorpay test keys found in .env. Falling back to dummy keys to capture the API rejection.")
    key_id = key_id or "rzp_test_dummy"
    key_secret = key_secret or "dummy_secret"

print(f"Executing real HTTP call to Razorpay Test Environment using Key ID: {key_id[:10]}...")

payload = {
  "amount": 50000,
  "currency": "INR",
  "accept_partial": False,
  "description": "Recovery for Failed Mandate (Test Mode)",
  "customer": {
    "name": "Test Customer",
    "email": "test@example.com",
    "contact": "+919876543210"
  },
  "notify": {
    "sms": False,
    "email": False
  },
  "reminder_enable": True
}

try:
    response = httpx.post(
        "https://api.razorpay.com/v1/payment_links",
        json=payload,
        auth=(key_id, key_secret),
        headers={"Content-Type": "application/json"}
    )
    print("\n--- RAZORPAY API RESPONSE ---")
    print(f"Status Code: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    print("-----------------------------")
except Exception as e:
    print(f"\n--- RAZORPAY CONNECTION FAILED (Sandbox Network) ---")
    print(f"Error: {e}")
    print("--------------------------------------------------")
