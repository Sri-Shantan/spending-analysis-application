from src.database import connect, insert_transactions, register_statement
from src.models import Transaction, TransactionType
from src.statement_metadata import extract_statement_period
from datetime import date
from decimal import Decimal


def test_extract_statement_period():
    text = "STATEMENT PERIOD August 06, 2026 through September 03, 2026"
    assert extract_statement_period(text) == ("2026-08-06", "2026-09-03")


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
