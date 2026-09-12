from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import sqlite3


class ReconciliationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    DUPLICATES = "DUPLICATES"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class ReconciliationResult:
    statement_id: int
    parsed_count: int
    inserted_count: int
    duplicate_count: int
    transaction_count: int
    needs_review_count: int
    expense_total: Decimal
    income_total: Decimal
    transfer_total: Decimal
    adjustment_total: Decimal
    status: ReconciliationStatus


def reconcile_statement(
    conn: sqlite3.Connection,
    statement_id: int,
    parsed_count: int,
    inserted_count: int,
) -> ReconciliationResult:
    """Reconcile parsed transactions against those linked to a statement."""
    row = conn.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(SUM(needs_review), 0),
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' THEN -amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' THEN amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN transaction_type = 'TRANSFER' THEN amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN transaction_type = 'ADJUSTMENT' THEN amount ELSE 0 END), 0)
        FROM transactions
        WHERE statement_id = ?
        """,
        (statement_id,),
    ).fetchone()

    transaction_count = int(row[0])
    needs_review_count = int(row[1])
    duplicate_count = max(parsed_count - inserted_count, 0)

    if parsed_count == 0:
        status = ReconciliationStatus.EMPTY
    elif duplicate_count > 0:
        status = ReconciliationStatus.DUPLICATES
    elif needs_review_count > 0:
        status = ReconciliationStatus.REVIEW_REQUIRED
    elif transaction_count == parsed_count:
        status = ReconciliationStatus.RECONCILED
    else:
        status = ReconciliationStatus.REVIEW_REQUIRED

    conn.execute(
        "UPDATE statements SET status = ? WHERE id = ?",
        (status.value, statement_id),
    )
    conn.commit()

    return ReconciliationResult(
        statement_id=statement_id,
        parsed_count=parsed_count,
        inserted_count=inserted_count,
        duplicate_count=duplicate_count,
        transaction_count=transaction_count,
        needs_review_count=needs_review_count,
        expense_total=Decimal(str(row[2] or 0)),
        income_total=Decimal(str(row[3] or 0)),
        transfer_total=Decimal(str(row[4] or 0)),
        adjustment_total=Decimal(str(row[5] or 0)),
        status=status,
    )
