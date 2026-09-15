import re
from decimal import Decimal
from src.models import Transaction, TransactionType
from src.parsers.base import StatementParser
from src.statement_metadata import StatementDateResolver, extract_statement_period

DATE_RE = re.compile(r"^(\d{2}/\d{2})\s+(.*)$")
AMOUNT_RE = re.compile(r"[+-]?\$?[\d,]+\.\d{2}")
PAGE_RE = re.compile(r"^---\s*Page\s+\d+\s+---$", re.I)


class ChaseCheckingParser(StatementParser):
    account_name = "Chase Checking"

    def can_parse(self, text: str) -> bool:
        return "Chase College Checking" in text and "TRANSACTION DETAIL" in text

    def parse(self, text: str, source_file: str | None = None) -> list[Transaction]:
        lines = [x.strip() for x in text.splitlines()]
        out = []
        start = next((i for i, x in enumerate(lines) if x == "TRANSACTION DETAIL"), -1)
        i = start + 1 if start >= 0 else len(lines)
        statement_start, statement_end = extract_statement_period("\n".join(lines[:i]))

        while i < len(lines):
            page_start, page_end = extract_statement_period(lines[i])
            if page_start and page_end:
                statement_start, statement_end = page_start, page_end
                i += 1
                continue

            m = DATE_RE.match(lines[i])
            if not m:
                i += 1
                continue

            posted_mmdd, first_text = m.groups()
            if first_text.startswith(("Beginning Balance", "Ending Balance")):
                i += 1
                continue

            # A Chase transaction has a posted date, a description that may
            # wrap across lines, then transaction amount and running balance.
            # Stop at page boundaries so footer text cannot be mistaken for part
            # of the transaction and introduce unrelated monetary values.
            parts = [first_text]
            j = i + 1
            while j < len(lines) and not DATE_RE.match(lines[j]):
                if PAGE_RE.match(lines[j]):
                    break
                if lines[j] in {"*start*transactiondetail", "*end*transaction detail"}:
                    break
                if lines[j].startswith("Ending Balance"):
                    break
                parts.append(lines[j])
                j += 1

            row_text = " ".join(p for p in parts if p).strip()
            tx_amount, desc = self._extract_transaction_amount(row_text)
            if tx_amount is None:
                i = j if j > i else i + 1
                continue

            if not statement_start or not statement_end:
                raise ValueError("Could not determine Chase statement period")
            resolver = StatementDateResolver(statement_start, statement_end)
            posted = resolver.resolve(posted_mmdd)
            embedded = re.search(
                r"(?:Card Purchase|Recurring Card Purchase|Card Purchase With Pin)\s+(\d{2}/\d{2})\s+",
                desc,
                re.I,
            )
            tx_date = (
                resolver.resolve_near(embedded.group(1), posted)
                if embedded
                else posted
            )
            ttype, category = self._classify(desc, tx_amount)
            out.append(
                Transaction(
                    tx_date,
                    posted if tx_date != posted else None,
                    desc,
                    self._merchant(desc),
                    tx_amount,
                    self.account_name,
                    ttype,
                    category,
                    source_file=source_file,
                )
            )
            i = j if j > i else i + 1

        return out

    @staticmethod
    def _extract_transaction_amount(row_text: str):
        """Return the transaction amount and description from a Chase row.

        Chase places the transaction amount immediately before the final
        running-balance value. Always use that penultimate monetary value so
        the balance can never become the transaction amount.
        """
        amounts = list(AMOUNT_RE.finditer(row_text))
        if len(amounts) < 2:
            return None, row_text

        tx_match = amounts[-2]
        balance_match = amounts[-1]
        tx_amount = Decimal(tx_match.group(0).replace("$", "").replace(",", ""))
        desc = (row_text[:tx_match.start()] + row_text[balance_match.end():]).strip()
        return tx_amount, desc

    @staticmethod
    def _merchant(description: str) -> str:
        return re.sub(
            r"^(Card Purchase(?: With Pin)?|Recurring Card Purchase|Zelle Payment To|Zelle Payment From|Zelle To|Zelle From)\s+",
            "",
            description,
            flags=re.I,
        ).strip()

    @staticmethod
    def _classify(description: str, amount: Decimal):
        d = description.upper()
        if "PAYROLL" in d:
            return TransactionType.INCOME, "Income"
        if "ZELLE" in d and amount > 0:
            return TransactionType.INCOME, "Zelle"
        if any(x in d for x in ("PAYMENT TO CHASE CARD", "AMERICAN EXPRESS ACH PMT", "DISCOVER E-PAYMENT")):
            return TransactionType.TRANSFER, "Credit Card Payment"
        if "ATM WITHDRAWAL" in d:
            return TransactionType.EXPENSE, "Cash Withdrawal"
        if "DUKEENERGY" in d:
            return TransactionType.EXPENSE, "Bills"
        return (TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME), "Uncategorized"
