"""
SQLite connection + schema for the Accurova loyalty program.
WAL mode for reliability under concurrent reads/writes (Telegram bot + web + admin
can all hit the DB at once without locking each other out).
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "loyalty.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT UNIQUE,
    email TEXT UNIQUE,
    telegram_id INTEGER UNIQUE,
    referral_code TEXT UNIQUE NOT NULL,
    referred_by_client_id INTEGER REFERENCES clients(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_clients_referral_code ON clients(referral_code);

-- Append-only ledger. Balance is ALWAYS derived (SUM(delta)), never stored/mutated
-- directly. This is what makes the system reliable: nothing can drift out of sync,
-- and every point ever awarded/spent is permanently traceable.
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN
        ('booking', 'referral_bonus', 'redemption', 'adjustment', 'signup_bonus')),
    reference_id TEXT,              -- e.g. invoice ID from InvoiceForge
    idempotency_key TEXT UNIQUE,    -- prevents double-crediting on webhook retries
    note TEXT,
    created_by TEXT,                -- 'system' | 'admin:julian' | telegram_id etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ledger_client ON ledger(client_id);

-- One-time codes for web login (sent via Telegram if linked, else email).
CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact TEXT NOT NULL,          -- phone or email used to request it
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
