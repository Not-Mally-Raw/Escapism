import json
import hmac
import hashlib
import aiosqlite
from fastapi import FastAPI, Request, HTTPException, Response

app = FastAPI(title="Webhook Ingestion Gateway")

WEBHOOK_SECRET = "test_secret"
DB_PATH = "webhook.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        with open("src/ingestion/schema.sql", "r") as f:
            await db.executescript(f.read())

@app.on_event("startup")
async def startup():
    await init_db()

@app.post("/webhook/razorpay")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # The payload is used to check schema but NOT for event_id extraction
    try:
        json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Strictly enforce the header, fail if missing. Do NOT dig through payload.
    event_id = request.headers.get("x-razorpay-event-id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing x-razorpay-event-id header")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        
        async with db.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)) as cursor:
            if await cursor.fetchone():
                return Response(status_code=202)
        
        # Atomic deduplication in inbox
        try:
            await db.execute(
                "INSERT INTO inbox (event_id, raw_payload, status) VALUES (?, ?, 'PENDING')",
                (event_id, raw_body.decode("utf-8"))
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            # Already exists in inbox
            return Response(status_code=202)

    return Response(status_code=202)
