-- Enable WAL mode for concurrent writes
PRAGMA journal_mode=WAL;

-- Idempotency log (UNIQUE constraint enforces deduplication)
CREATE TABLE IF NOT EXISTS seen_events (
    event_id TEXT PRIMARY KEY,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Inbox queue (persistent, survives worker restarts)
CREATE TABLE IF NOT EXISTS inbox (
    event_id TEXT PRIMARY KEY,
    raw_payload TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'PENDING', -- PENDING, PROCESSING, PROCESSED, FAILED, DEAD_LETTER
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMP
);

-- Execution intents (recorded prior to external dispatch for replay safety and crash reconciliation)
CREATE TABLE IF NOT EXISTS execution_intents (
    intent_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, DISPATCHED, COMPLETED, FAILED, RECONCILED
    payload_json TEXT,
    receipt_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dead Letter Queue
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    attempt_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log (append-only, OPE-critical)
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    audit_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox(status);
CREATE INDEX IF NOT EXISTS idx_audit_event_id ON audit_log(event_id);
CREATE INDEX IF NOT EXISTS idx_intent_event_id ON execution_intents(event_id);
CREATE INDEX IF NOT EXISTS idx_intent_idempotency_key ON execution_intents(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_dlq_event_id ON dead_letter_queue(event_id);
