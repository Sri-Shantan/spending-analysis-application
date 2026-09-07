import sqlite3
from pathlib import Path
from src.models import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    transaction_hash TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account);
"""


def connect(path: str | Path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def insert_transactions(conn, transactions: list[Transaction]) -> int:
    import hashlib
    before = conn.total_changes
    rows=[]
    for t in transactions:
        fingerprint=f"{t.transaction_date}|{t.description}|{t.amount}|{t.account}"
        h=hashlib.sha256(fingerprint.encode()).hexdigest()
        rows.append((t.transaction_date.isoformat(), t.posted_date.isoformat() if t.posted_date else None, t.description, t.merchant, str(t.amount), t.account, t.transaction_type.value, t.category, t.subcategory, t.source_file, t.source_page, int(t.needs_review), h))
    conn.executemany("""INSERT OR IGNORE INTO transactions
        (transaction_date,posted_date,description,merchant,amount,account,transaction_type,category,subcategory,source_file,source_page,needs_review,transaction_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    return conn.total_changes - before
