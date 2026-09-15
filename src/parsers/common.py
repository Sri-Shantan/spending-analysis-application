import re
from decimal import Decimal

from src.models import TransactionType


MONEY_PATTERN = r"(?:[+-]\s*)?\$?[\d,]+\.\d{2}"
MONEY_RE = re.compile(MONEY_PATTERN)
FULL_MONEY_RE = re.compile(rf"^{MONEY_PATTERN}$")
TRAILING_MONEY_RE = re.compile(rf"({MONEY_PATTERN})\s*$")


def parse_money(value: str) -> Decimal:
    """Parse a monetary value while tolerating spaces after its sign."""
    normalized = re.sub(r"[\s$,]", "", value)
    return Decimal(normalized)


def trailing_money(text: str):
    match = TRAILING_MONEY_RE.search(text)
    if not match:
        return None, text
    return parse_money(match.group(1)), text[:match.start()].strip()


def classify_direction(description: str):
    """Return a direction implied by provider-independent transaction wording."""
    normalized = re.sub(r"\s+", " ", description.upper())
    if re.search(r"\bZELLE (?:PAYMENT )?TO\b", normalized):
        return TransactionType.EXPENSE, "Zelle"
    if re.search(r"\bZELLE (?:PAYMENT )?FROM\b", normalized):
        return TransactionType.INCOME, "Zelle"
    return None
