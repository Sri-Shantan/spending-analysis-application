from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class DataQualityResult:
    statement_id: int
    transaction_count: int
    outside_period_count: int
    missing_hash_count: int
    missing_description_count: int
    invalid_amount_count: int
    invalid_type_count: int
    needs_review_count: int

    @property
    def issue_count(self) -> int:
        return sum((
            self.outside_period_count,
            self.missing_hash_count,
            self.missing_description_count,
            self.invalid_amount_count,
            self.invalid_type_count,
            self.needs_review_count,
        ))

    @property
    def passed(self) -> bool:
        return self.issue_count == 0


def validate_statement(conn: sqlite3.Connection, statement_id: int) -> DataQualityResult:
    statement = conn.execute(
        "SELECT statement_start, statement_end FROM statements WHERE id = ?",
        (statement_id,),
    ).fetchone()
    if statement is None:
        raise ValueError(f"Unknown statement_id: {statement_id}")

    start, end = statement
    row = conn.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN (? IS NOT NULL AND COALESCE(posted_date, transaction_date) < ?) OR (? IS NOT NULL AND COALESCE(posted_date, transaction_date) > ?) THEN 1 ELSE 0 END),
            SUM(CASE WHEN transaction_hash IS NULL OR transaction_hash = '' THEN 1 ELSE 0 END),
            SUM(CASE WHEN description IS NULL OR TRIM(description) = '' THEN 1 ELSE 0 END),
            SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN transaction_type NOT IN ('INCOME','EXPENSE','TRANSFER','ADJUSTMENT') THEN 1 ELSE 0 END),
            SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END)
        FROM transactions
        WHERE statement_id = ?
        """,
        (start, start, end, end, statement_id),
    ).fetchone()

    return DataQualityResult(
        statement_id=statement_id,
        transaction_count=int(row[0] or 0),
        outside_period_count=int(row[1] or 0),
        missing_hash_count=int(row[2] or 0),
        missing_description_count=int(row[3] or 0),
        invalid_amount_count=int(row[4] or 0),
        invalid_type_count=int(row[5] or 0),
        needs_review_count=int(row[6] or 0),
    )
