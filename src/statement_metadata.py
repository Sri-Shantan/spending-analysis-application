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
        r"STATEMENT PERIOD\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"statement period\s*:?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*(?:-|to|through)\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                start = datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
                end = datetime.strptime(match.group(2), "%B %d, %Y").date().isoformat()
                return start, end
            except ValueError:
                pass
    return None, None
