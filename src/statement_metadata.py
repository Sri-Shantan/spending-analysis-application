import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class StatementMetadata:
    account: str
    statement_start: Optional[str]
    statement_end: Optional[str]
    source_file: str
    statement_hash: str


def extract_statement_period(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract the full period covered by one or more statement ranges."""
    patterns = [
        (
            r"STATEMENT PERIOD\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            "%B %d, %Y",
        ),
        (
            r"statement period\s*:?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*(?:-|to|through)\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            "%B %d, %Y",
        ),
        (
            r"OPEN TO CLOSE DATE\s*:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
            "%m/%d/%Y",
        ),
        (
            r"(?<![A-Za-z])([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            "%B %d, %Y",
        ),
    ]
    periods = []
    for pattern, date_format in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                start = datetime.strptime(match.group(1), date_format).date()
                end = datetime.strptime(match.group(2), date_format).date()
                periods.append((start, end))
            except ValueError:
                pass
    if periods:
        return min(start for start, _ in periods).isoformat(), max(end for _, end in periods).isoformat()
    return None, None


def resolve_partial_date(mmdd: str, statement_start: str, statement_end: str) -> date:
    """Resolve an MM/DD date within an inclusive statement period."""
    start = date.fromisoformat(statement_start)
    end = date.fromisoformat(statement_end)
    month, day = (int(value) for value in mmdd.split("/"))
    candidates = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            candidates.append(candidate)
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(f"Transaction date {mmdd} is outside statement period {start} to {end}")


def resolve_near_date(mmdd: str, reference: date, max_distance_days: int = 31) -> date:
    """Resolve an MM/DD date to the closest year around a reference date."""
    month, day = (int(value) for value in mmdd.split("/"))
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        raise ValueError(f"Invalid transaction date: {mmdd}")
    candidate = min(candidates, key=lambda value: abs(value - reference))
    if abs((candidate - reference).days) > max_distance_days:
        raise ValueError(f"Transaction date {mmdd} is too far from posted date {reference}")
    return candidate
