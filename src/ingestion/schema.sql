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
    status TEXT DEFAULT 'PENDING', -- PENDING, PROCESSING, PROCESSED, FAILED
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
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
