import re
from datetime import datetime
from decimal import Decimal
from src.models import Transaction, TransactionType
from src.parsers.base import StatementParser

DATE_RE = re.compile(r"^(\d{2}/\d{2})\s+(.*)$")
PERIOD_RE = re.compile(r"statement period (\w+ \d{2}, \d{4}) through (\w+ \d{2}, \d{4})", re.I)


class ChaseCheckingParser(StatementParser):
    account_name = "Chase Checking"

    def can_parse(self, text: str) -> bool:
        return "Chase College Checking" in text and "TRANSACTION DETAIL" in text

    def parse(self, text: str, source_file: str | None = None) -> list[Transaction]:
        lines = [x.strip() for x in text.splitlines()]
        year = self._statement_year(text)
        out = []
        start = next((i for i, x in enumerate(lines) if x.startswith("TRANSACTION DETAIL") or x.startswith("DATE DESCRIPTION AMOUNT BALANCE")), -1)
        i = start + 1 if start >= 0 else len(lines)
        while i < len(lines):
            m = DATE_RE.match(lines[i])
            if not m:
                i += 1; continue
            mmdd, rest = m.groups()
            amount, desc = self._extract_amounts(rest); j = i
            if amount is None:
                parts = [rest]
                while j < len(lines) and not DATE_RE.match(lines[j]):
                    a, c = self._extract_amounts(lines[j])
                    if a is not None:
                        amount = a; parts.append(c); break
                    if lines[j] and not lines[j].startswith(("Beginning Balance", "Ending Balance")): parts.append(lines[j])
                    j += 1
                desc = " ".join(parts).strip()
            if amount is None:
                i += 1; continue
            posted = datetime.strptime(f"{mmdd}/{year}", "%m/%d/%Y").date()
            embedded = re.search(r"(?:Card Purchase|Recurring Card Purchase)\s+(\d{2}/\d{2})\s+", desc, re.I)
            tx_date = datetime.strptime(f"{embedded.group(1)}/{year}", "%m/%d/%Y").date() if embedded else posted
            ttype, category = self._classify(desc, amount)
            out.append(Transaction(tx_date, posted if tx_date != posted else None, desc, self._merchant(desc), amount, self.account_name, ttype, category, source_file=source_file))
            i = j + 1 if j > i else i + 1
        return out

    @staticmethod
    def _extract_amounts(text):
        matches = list(re.finditer(r"[+-]?\$?[\d,]+\.\d{2}", text))
        if not matches: return None, text
        m = matches[0]
        value = Decimal(m.group(0).replace("$", "").replace(",", ""))
        return value, (text[:m.start()] + text[m.end():]).strip()

    @staticmethod
    def _statement_year(text: str) -> int:
        m = PERIOD_RE.search(text)
        if m: return datetime.strptime(m.group(2), "%B %d, %Y").year
        years = [int(y) for y in re.findall(r"\b20\d{2}\b", text)]
        return max(years) if years else datetime.now().year

    @staticmethod
    def _merchant(description: str) -> str:
        return re.sub(r"^(Card Purchase|Recurring Card Purchase|Zelle Payment To|Zelle Payment From|Zelle To|Zelle From)\s+", "", description, flags=re.I).strip()

    @staticmethod
    def _classify(description: str, amount: Decimal):
        d = description.upper()
        if "PAYROLL" in d: return TransactionType.INCOME, "Income"
        if "ZELLE" in d and amount > 0: return TransactionType.INCOME, "Zelle"
        if any(x in d for x in ("PAYMENT TO CHASE CARD", "AMERICAN EXPRESS ACH PMT", "DISCOVER E-PAYMENT")): return TransactionType.TRANSFER, "Credit Card Payment"
        if "ATM WITHDRAWAL" in d: return TransactionType.EXPENSE, "Cash Withdrawal"
        if "DUKEENERGY" in d: return TransactionType.EXPENSE, "Bills"
        return (TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME), "Uncategorized"
