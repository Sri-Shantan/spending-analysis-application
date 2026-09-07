# Spending Analysis Application

Personal spending-analysis application for converting bank and credit-card statements into a normalized transaction ledger, SQLite database, and Excel report.

## Supported statements

- Chase Checking
- Chase Freedom Unlimited credit card
- American Express Blue Cash Everyday
- Citi Diamond Preferred
- Discover IT

The supplied statement formats differ substantially, so the application uses statement-specific parsers feeding one common `Transaction` model.

## Pipeline

`PDF/TXT -> statement parser -> common Transaction model -> rule categorizer -> SQLite -> Excel`

Amounts are normalized to account cashflow: income/inflows are positive and spending/outflows are negative. Credit-card payments are `TRANSFER` so they can be excluded from spending totals and avoid double counting.

For checking statements, when both transaction and posting dates are present, `transaction_date` preserves the transaction date and `posted_date` preserves the posting date.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m src.main --input statements
```

Extracted `.txt` files can be used for development/testing. PDF files are also accepted and are extracted with `pypdf` before parsing.

## Privacy

Statement files, SQLite databases, and generated Excel files are ignored by git. Do not commit real financial statements or generated transaction databases.
