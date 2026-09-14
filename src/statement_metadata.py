import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class StatementMetadata:
    account: str
    statement_start: Optional[str]
    statement_end: Optional[str]
    source_file: str
    statement_hash: str


def extract_statement_period(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract common statement-period formats as ISO dates."""
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
    ]
    for pattern, date_format in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                start = datetime.strptime(match.group(1), date_format).date().isoformat()
                end = datetime.strptime(match.group(2), date_format).date().isoformat()
                return start, end
            except ValueError:
                pass
    return None, None
