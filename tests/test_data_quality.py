from datetime import date
from decimal import Decimal

from src.data_quality import validate_statement
from src.database import connect, insert_transactions, register_statement
from src.models import Transaction, TransactionType


def _tx(day=1, posted_day=None, needs_review=False):
    return Transaction(
        transaction_date=date(2026, 8, day),
        posted_date=date(2026, 8, posted_day) if posted_day else None,
        description="Test merchant",
        merchant="Test merchant",
        amount=Decimal("-10.00"),
        account="Chase Checking",
        transaction_type=TransactionType.EXPENSE,
        category="Shopping",
        needs_review=needs_review,
    )


def test_data_quality_passes_for_transactions_inside_period(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-01", "2026-08-31", "quality-1")
    insert_transactions(conn, [_tx(1), _tx(31)], statement_id=statement_id)
    result = validate_statement(conn, statement_id)
    assert result.passed
    assert result.transaction_count == 2
    assert result.outside_period_count == 0
    assert result.missing_hash_count == 0


def test_data_quality_flags_transaction_outside_period(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-01", "2026-08-31", "quality-2")
    insert_transactions(conn, [_tx(1)], statement_id=statement_id)
    conn.execute("UPDATE transactions SET transaction_date = '2026-09-01' WHERE statement_id = ?", (statement_id,))
    conn.commit()
    result = validate_statement(conn, statement_id)
    assert not result.passed
    assert result.outside_period_count == 1


def test_data_quality_uses_posted_date_for_statement_period(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-02", "2026-08-31", "quality-posted")
    insert_transactions(conn, [_tx(day=1, posted_day=2)], statement_id=statement_id)
    result = validate_statement(conn, statement_id)
    assert result.outside_period_count == 0


def test_data_quality_flags_review_transactions(tmp_path):
    conn = connect(tmp_path / "spending.db")
    statement_id, _ = register_statement(conn, "statement.txt", "Chase Checking", "2026-08-01", "2026-08-31", "quality-3")
    insert_transactions(conn, [_tx(needs_review=True)], statement_id=statement_id)
    result = validate_statement(conn, statement_id)
    assert not result.passed
    assert result.needs_review_count == 1
