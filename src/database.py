import hashlib
import sqlite3
from pathlib import Path
from src.models import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    account TEXT NOT NULL,
    statement_start TEXT,
    statement_end TEXT,
    statement_hash TEXT NOT NULL UNIQUE,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'INGESTED'
);
CREATE INDEX IF NOT EXISTS idx_statements_account ON statements(account);
CREATE INDEX IF NOT EXISTS idx_statements_period ON statements(statement_start, statement_end);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    statement_id INTEGER,
    transaction_date TEXT NOT NULL,
    posted_date TEXT,
    description TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    account TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    source_file TEXT,
    source_page INTEGER,
    needs_review INTEGER NOT NULL DEFAULT 0,
    transaction_hash TEXT UNIQUE,
    FOREIGN KEY (statement_id) REFERENCES statements(id)
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account);
CREATE INDEX IF NOT EXISTS idx_transactions_statement ON transactions(statement_id);
"""


def connect(path: str | Path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def register_statement(
    conn,
    source_file: str,
    account: str,
    statement_start: str | None,
    statement_end: str | None,
    statement_hash: str,
):
    """Register a source statement and return (statement_id, is_new)."""
    row = conn.execute(
        "SELECT id FROM statements WHERE statement_hash = ?",
        (statement_hash,),
    ).fetchone()
    if row:
        return row[0], False

    cur = conn.execute(
        """INSERT INTO statements
           (source_file, account, statement_start, statement_end, statement_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (source_file, account, statement_start, statement_end, statement_hash),
    )
    conn.commit()
    return cur.lastrowid, True


def insert_transactions(conn, transactions: list[Transaction], statement_id: int | None = None) -> int:
    before = conn.total_changes
    rows = []
    for t in transactions:
        fingerprint = f"{t.transaction_date}|{t.description}|{t.amount}|{t.account}"
        h = hashlib.sha256(fingerprint.encode()).hexdigest()
        rows.append(
            (
                statement_id,
                t.transaction_date.isoformat(),
                t.posted_date.isoformat() if t.posted_date else None,
                t.description,
                t.merchant,
                str(t.amount),
                t.account,
                t.transaction_type.value,
                t.category,
                t.subcategory,
                t.source_file,
                t.source_page,
                int(t.needs_review),
                h,
            )
        )

    conn.executemany(
        """INSERT OR IGNORE INTO transactions
        (statement_id, transaction_date, posted_date, description, merchant, amount,
         account, transaction_type, category, subcategory, source_file, source_page,
         needs_review, transaction_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    return conn.total_changes - before
