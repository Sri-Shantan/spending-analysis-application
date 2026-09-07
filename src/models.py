from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass(frozen=True)
class Transaction:
    transaction_date: date
    posted_date: Optional[date]
    description: str
    merchant: str
    amount: Decimal
    account: str
    transaction_type: TransactionType
    category: str
    subcategory: Optional[str] = None
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    needs_review: bool = False
    transaction_hash: Optional[str] = None
