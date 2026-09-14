from src.categorizer import recategorize_transactions
from src.database import connect, insert_transactions, register_statement
from src.models import Transaction, TransactionType
from src.reconciliation import ReconciliationStatus, reconcile_statement
from src.statement_metadata import extract_statement_period
from datetime import date
from decimal import Decimal


def test_extract_statement_period():
    text = "STATEMENT PERIOD August 06, 2026 through September 03, 2026"
    assert extract_statement_period(text) == ("2026-08-06", "2026-09-03")


def test_extract_discover_open_to_close_period():
    text = "OPEN TO CLOSE DATE: 07/26/2026 - 08/25/2026"
    assert extract_statement_period(text) == ("2026-07-26", "2026-08-25")


def test_statement_registration_is_idempotent(tmp_path):
    conn = connect(tmp_path / "spending.db")
    first = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-06", "2026-09-03", "abc")
    second = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-06", "2026-09-03", "abc")
    assert first[1] is True
    assert second == (first[0], False)


def test_transactions_link_to_statement(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "xyz")
    tx = Transaction(
        transaction_date=date(2026, 9, 1),
        posted_date=None,
        description="Test merchant",
        merchant="Test merchant",
        amount=Decimal("-10.00"),
        account="Chase Checking",
        transaction_type=TransactionType.EXPENSE,
        category="Shopping",
    )
    assert insert_transactions(conn, [tx], statement_id=statement_id) == 1
    row = conn.execute("SELECT statement_id FROM transactions").fetchone()
    assert row[0] == statement_id


def _make_tx(description="Test merchant", amount="-10.00", needs_review=False):
    return Transaction(
        transaction_date=date(2026, 9, 1),
        posted_date=None,
        description=description,
        merchant=description,
        amount=Decimal(amount),
        account="Chase Checking",
        transaction_type=TransactionType.EXPENSE,
        category="Shopping",
        needs_review=needs_review,
    )


def test_recategorize_existing_transactions(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "recat-1")
    tx = _make_tx("NEW MERCHANT", "-12.00", needs_review=True)
    tx = Transaction(**{**tx.__dict__, "category": "Uncategorized"})
    assert insert_transactions(conn, [tx], statement_id=statement_id) == 1

    updated = recategorize_transactions(
        conn,
        {"rules": [{"keywords": ["NEW MERCHANT"], "category": "Shopping", "subcategory": "Online"}]},
    )

    assert updated == 1
    row = conn.execute(
        "SELECT category, subcategory, needs_review FROM transactions WHERE id = 1"
    ).fetchone()
    assert row == ("Shopping", "Online", 0)


def test_recategorize_leaves_unmatched_transaction_uncategorized(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "recat-2")
    tx = _make_tx("UNKNOWN MERCHANT", "-15.00", needs_review=True)
    tx = Transaction(**{**tx.__dict__, "category": "Uncategorized"})
    assert insert_transactions(conn, [tx], statement_id=statement_id) == 1

    updated = recategorize_transactions(conn, {"rules": []})

    assert updated == 0
    row = conn.execute(
        "SELECT category, subcategory, needs_review FROM transactions WHERE id = 1"
    ).fetchone()
    assert row == ("Uncategorized", None, 1)


def test_reconciliation_reconciled(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "reconcile-1")
    txs = [_make_tx("Merchant A", "-10.00"), _make_tx("Merchant B", "-20.00")]
    inserted = insert_transactions(conn, txs, statement_id=statement_id)
    result = reconcile_statement(conn, statement_id, parsed_count=2, inserted_count=inserted)
    assert result.status is ReconciliationStatus.RECONCILED
    assert result.transaction_count == 2
    assert result.expense_total == Decimal("30")
    assert result.duplicate_count == 0
    assert conn.execute("SELECT status FROM statements WHERE id=?", (statement_id,)).fetchone()[0] == "RECONCILED"


def test_reconciliation_detects_duplicates(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "reconcile-2")
    tx = _make_tx()
    inserted = insert_transactions(conn, [tx], statement_id=statement_id)
    result = reconcile_statement(conn, statement_id, parsed_count=2, inserted_count=inserted)
    assert result.status is ReconciliationStatus.DUPLICATES
    assert result.duplicate_count == 1


def test_reconciliation_flags_review_required(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "reconcile-3")
    inserted = insert_transactions(conn, [_make_tx(needs_review=True)], statement_id=statement_id)
    result = reconcile_statement(conn, statement_id, parsed_count=1, inserted_count=inserted)
    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert result.needs_review_count == 1


def test_reconciliation_empty_statement(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", None, None, "reconcile-4")
    result = reconcile_statement(conn, statement_id, parsed_count=0, inserted_count=0)
    assert result.status is ReconciliationStatus.EMPTY
