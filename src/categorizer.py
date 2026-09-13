import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.models import Transaction, TransactionType


def load_rules(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def categorize(transaction: Transaction, rules: dict) -> Transaction:
    text = transaction.description.upper()
    for rule in rules.get("rules", []):
        if any(keyword.upper() in text for keyword in rule["keywords"]):
            return Transaction(**{**transaction.__dict__, "category": rule["category"], "subcategory": rule.get("subcategory"), "needs_review": False})
    return Transaction(**{**transaction.__dict__, "needs_review": transaction.category == "Uncategorized"})


def recategorize_transactions(conn, rules: dict) -> int:
    """Re-apply merchant rules to all existing transactions.

    Existing transaction identity and source fields are preserved. Returns the
    number of transactions whose category, subcategory, or review status changed.
    """
    rows = conn.execute(
        """SELECT id, transaction_date, posted_date, description, merchant, amount,
                  account, transaction_type, category, subcategory, source_file,
                  source_page, needs_review, transaction_hash
           FROM transactions
           ORDER BY id"""
    ).fetchall()

    updated = 0
    for row in rows:
        transaction = Transaction(
            transaction_date=date.fromisoformat(row[1]),
            posted_date=date.fromisoformat(row[2]) if row[2] else None,
            description=row[3],
            merchant=row[4],
            amount=Decimal(str(row[5])),
            account=row[6],
            transaction_type=TransactionType(row[7]),
            category=row[8],
            subcategory=row[9],
            source_file=row[10],
            source_page=row[11],
            needs_review=bool(row[12]),
            transaction_hash=row[13],
        )
        recategorized = categorize(transaction, rules)
        if (
            recategorized.category != transaction.category
            or recategorized.subcategory != transaction.subcategory
            or recategorized.needs_review != transaction.needs_review
        ):
            conn.execute(
                """UPDATE transactions
                   SET category = ?, subcategory = ?, needs_review = ?
                   WHERE id = ?""",
                (
                    recategorized.category,
                    recategorized.subcategory,
                    int(recategorized.needs_review),
                    row[0],
                ),
            )
            updated += 1

    conn.commit()
    return updated
