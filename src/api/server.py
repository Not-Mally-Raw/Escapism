from contextlib import asynccontextmanager
import hmac
import hashlib
import json
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.router import router as v1_router
from src.execution.worker import execute_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
WEBHOOK_SECRET = "test_secret"
DB_PATH = "gateway.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        schema_path = ROOT_DIR / "src" / "ingestion" / "schema.sql"
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                await db.executescript(f.read())

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Razorpay Autonomous Revenue Recovery Terminal",
    description="Compliance-Gated AI Allocation Engine with Bloomberg Terminal Interface",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 REST API Router
app.include_router(v1_router)

# Mount Static Assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Root endpoint serves the Bloomberg Terminal UI
@app.get("/", include_in_schema=False)
async def serve_terminal():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)

# Landing Page
@app.get("/landing", include_in_schema=False)
async def serve_landing():
    landing_file = STATIC_DIR / "landing.html"
    return FileResponse(landing_file)

# Webhook Ingestion Gateway Endpoint
@app.post("/webhook/razorpay")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_id = request.headers.get("x-razorpay-event-id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing x-razorpay-event-id header")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        # Check idempotency
        async with db.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)) as cur:
            if await cur.fetchone():
                return Response(status_code=202)

        # Process through worker pipeline
        try:
            payload_str = raw_body.decode("utf-8")
            res = await execute_pipeline(payload_str, event_id=event_id, db=db)
            return {"status": "accepted", "event_id": event_id, "decision": res}
        except Exception as e:
            return Response(status_code=202)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
