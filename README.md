# Spending Analysis — Project Overview

## 1. Project Goal

Build a personal spending-analysis application that:

1. Reads bank statement PDFs from a `statements/` folder.
2. Extracts transaction information using `pypdf`.
3. Parses and normalizes transactions.
4. Categorizes transactions.
5. Stores the normalized data in a free local database.
6. Exports the data to Excel.
7. Eventually provides a dashboard for querying and visualizing spending by date range.

The initial priority is reliable PDF parsing, categorization, database storage, duplicate detection, and reconciliation. The dashboard is a lower-priority feature.

---

# 2. Recommended Architecture

```text
statements/
    *.pdf
        |
        v
PDF Reader (pypdf)
        |
        v
Raw Text / Line Items
        |
        v
Transaction Parser
        |
        v
Normalized Transactions
        |
        v
Categorizer
        |
        +------------------+
        |                  |
        v                  v
    SQLite DB          Excel Export
        |
        v
    Dashboard
```

The application should separate PDF extraction, parsing, categorization, and storage rather than having one large parser function responsible for everything.

---

# 3. Directory Structure

Recommended project structure:

```text
spending-analysis/
│
├── statements/
│   └── *.pdf
│
├── processed/
│   └── successfully processed PDFs
│
├── failed/
│   └── PDFs that could not be parsed
│
├── database/
│   └── spending.db
│
├── output/
│   └── spending.xlsx
│
├── config/
│   ├── categories.json
│   └── merchant_rules.json
│
├── src/
│   ├── main.py
│   ├── pdf_reader.py
│   ├── transaction_parser.py
│   ├── categorizer.py
│   ├── database.py
│   ├── excel_exporter.py
│   └── utils.py
│
└── dashboard/
    └── app.py
```

### Why separate `processed/` and `failed/`?

The original idea was to move PDFs into `myStatements/{month}/`.

Instead, use:

- `statements/` — files waiting to be processed
- `processed/` — files successfully processed
- `failed/` — files that encountered an error

The database should store the statement period and source filename, so month-based folders are not necessary.

---

# 4. Processing Pipeline

The main processing flow should be:

```text
main.py
   |
   +-- Find PDFs in statements/
   |
   +-- Calculate PDF hash
   |
   +-- Check whether PDF was already processed
   |
   +-- pdf_reader.py
   |       |
   |       +-- Extract raw text using pypdf
   |
   +-- transaction_parser.py
   |       |
   |       +-- Convert raw text into transactions
   |
   +-- categorizer.py
   |       |
   |       +-- Determine merchant/category/type
   |
   +-- database.py
   |       |
   |       +-- Insert into SQLite
   |
   +-- excel_exporter.py
   |       |
   |       +-- Generate/update Excel
   |
   +-- Move PDF to processed/
```

---

# 5. Stage 1 — PDF Reader

Use `pypdf` to extract text from each statement.

Example:

```python
text = extract_text_from_pdf(pdf)
```

The PDF reader should only be responsible for extracting information.

It should NOT decide whether a transaction is:

- Groceries
- Shopping
- Food
- Bills
- Income

That responsibility belongs to the categorizer.

---

# 6. Stage 2 — Transaction Parser

The parser converts raw PDF text into normalized transaction objects.

For example, raw PDF text might contain:

```text
01/05/2026
COSTCO WHOLESALE #123
-125.43
```

The parser should produce something like:

```python
{
    "date": "2026-01-05",
    "description": "COSTCO WHOLESALE #123",
    "amount": -125.43
}
```

The parser should focus on identifying:

- Transaction date
- Description
- Amount
- Balance, if available
- Any other useful fields contained in the statement

The parser should not be responsible for database insertion or Excel generation.

---

# 7. Stage 3 — Categorization

After parsing, the transaction should be categorized.

Example:

```python
{
    "date": "2026-01-05",
    "description": "COSTCO WHOLESALE #123",
    "amount": -125.43,
    "category": "Groceries"
}
```

The categorizer should ideally determine:

- Merchant
- Category
- Subcategory
- Transaction type
- Whether manual review is needed

---

# 8. Transaction Types

Use a transaction type in addition to the category.

Recommended transaction types:

```text
INCOME
EXPENSE
TRANSFER
```

Examples:

```text
Payroll              → INCOME
Zelle Credit         → INCOME
Costco               → EXPENSE
Amazon               → EXPENSE
Rent                 → EXPENSE
Credit Card Payment  → TRANSFER
Bank Transfer        → TRANSFER
```

This is important because transfers should not be counted as spending.

---

# 9. Avoid Double-Counting Credit Card Payments

Credit card payments require special handling.

For example:

```text
01/05  Amazon                -$100
01/20  Credit Card Payment  -$100
```

Actual spending is:

```text
$100
```

not:

```text
$200
```

Therefore, credit card payments should normally be treated as:

```text
transaction_type = TRANSFER
```

rather than:

```text
category = Bills
```

This allows spending calculations to exclude transfers.

---

# 10. Initial Categories

Start with a relatively simple category structure.

```text
Income
    Payroll
    Zelle
    Other

Expenses
    Groceries
    Shopping
    Food
    Bills
    Transportation
    Entertainment
    Miscellaneous

Transfers
    Credit Card Payment
    Bank Transfer
```

The categories can be expanded later.

---

# 11. Zelle Transactions

Do not automatically assume every Zelle transaction is the same type.

Examples:

```text
Zelle From Employer      → potentially INCOME
Zelle From Friend        → potentially INCOME / OTHER
Zelle To Friend          → potentially EXPENSE / OTHER
Zelle Rent Payment       → EXPENSE / Bills
```

The categorization system should eventually use the transaction description and configurable rules to determine the appropriate category.

---

# 12. Rule-Based Categorization

Start with a rule-based system rather than AI/LLMs.

Example:

```python
CATEGORY_RULES = {
    "Groceries": [
        "COSTCO",
        "KROGER",
        "JAGDEEP",
    ],

    "Shopping": [
        "AMAZON",
        "WALMART",
        "TARGET",
    ],

    "Food": [
        "DOORDASH",
        "UBER EATS",
        "CHIPOTLE",
    ],

    "Bills": [
        "DUKE ENERGY",
        "COMCAST",
    ],
}
```

A transaction such as:

```text
COSTCO WHOLESALE #123
```

would match:

```text
COSTCO
```

and become:

```text
category = Groceries
```

### Why rule-based first?

It is:

- Predictable
- Easy to debug
- Free
- Fast
- Easy to modify
- Easy to understand why a transaction received a category

AI can potentially be added later for transactions that cannot be categorized using rules.

---

# 13. Configurable Merchant Rules

Avoid hardcoding all categorization rules inside Python.

Eventually use:

```text
config/
    categories.json
    merchant_rules.json
```

For example:

```json
{
    "Costco": {
        "keywords": ["COSTCO"],
        "category": "Groceries"
    },
    "Amazon": {
        "keywords": ["AMAZON"],
        "category": "Shopping"
    }
}
```

This allows merchant rules to be modified without changing the application code.

---

# 14. Merchant vs. Description

Store both the original transaction description and a normalized merchant.

Example:

```text
Original description:
POS 4837 COSTCO WHSE #1234 CINCINNATI OH

Merchant:
Costco

Category:
Groceries
```

This is useful for future analysis such as:

```text
Top Merchants

Costco        $642.32
Amazon        $421.18
Kroger        $283.91
DoorDash      $194.72
```

The original description should still be preserved for traceability.

---

# 15. Uncategorized / Needs Review

Do not force unknown transactions into `Miscellaneous`.

Use something like:

```text
category = Uncategorized
needs_review = True
```

Example:

```text
ABC SERVICES LLC
-$73.25
```

If the system does not recognize it, mark it for review.

Eventually the dashboard can display:

```text
17 transactions need review
```

After manually categorizing it, the system could save a rule:

```text
ABC SERVICES LLC → Bills
```

so future statements are automatically categorized.

---

# 16. Database

Use **SQLite** as the primary database.

Reasons:

- Free
- No database server required
- Built into Python
- Easy to back up
- More than sufficient for personal finance data
- Easy to query
- Works well with future dashboard frameworks such as Streamlit

The database should be the **source of truth**.

Excel should be considered an output/reporting format.

---

# 17. Database Tables

Start with two primary tables.

## `statements`

Suggested columns:

```text
id
source_file
account
statement_start_date
statement_end_date
processed_at
file_hash
```

## `transactions`

Suggested columns:

```text
id
statement_id
date_of_transaction
description
merchant
amount
transaction_type
category
subcategory
needs_review
transaction_hash
```

Potential future columns can be added as needed.

---

# 18. Important: Source Tracking

Store:

```text
source_file
source_page
```

where possible.

Example:

```text
source_file = Chase_Jan_2026.pdf
source_page = 3
```

If something looks incorrect, the transaction can be traced back to the exact PDF page.

This will be very useful while developing and debugging the parser.

---

# 19. Important: Duplicate Detection

The application should be safe to run multiple times.

For example, if:

```bash
python main.py
```

is executed twice, transactions should NOT be inserted twice.

Use a transaction hash or another unique identifier.

A possible transaction fingerprint could be based on:

```text
date
description
amount
account
```

For example:

```text
2026-01-05|COSTCO WHOLESALE|125.43|CHECKING
```

Hash this value and store it as:

```text
transaction_hash
```

The database can then reject duplicate transactions.

---

# 20. Amount Representation

Do not store colors in the database.

Store amounts as numbers:

```text
-125.43
+2500.00
```

Convention:

```text
Negative = money leaving the account
Positive = money entering the account
```

Excel/dashboard can then display:

```text
-$125.43
+$2,500.00
```

and use red/green formatting.

This keeps the underlying data clean and numeric.

---

# 21. Excel

Excel should be generated from the database.

Recommended transaction columns:

```text
Date
Description
Merchant
Amount
Transaction Type
Category
Subcategory
Account
Source File
```

Example:

| Date | Description | Merchant | Amount | Type | Category |
|---|---|---|---:|---|---|
| 2026-01-05 | COSTCO WHOLESALE | Costco | -125.43 | EXPENSE | Groceries |
| 2026-01-07 | DIRECT DEPOSIT | Employer | 2500.00 | INCOME | Payroll |
| 2026-01-20 | CREDIT CARD PAYMENT | Chase Card | -500.00 | TRANSFER | Credit Card Payment |

Excel formatting can make credits green and debits red, but the underlying value remains numeric.

---

# 22. Statement Reconciliation

Add reconciliation to ensure the parser did not miss transactions.

If the statement provides:

```text
Beginning Balance
+ Credits
- Debits
= Ending Balance
```

the application should verify:

```text
beginning_balance
+ sum(credits)
- sum(debits)
≈ ending_balance
```

Example:

```text
Statement: Chase_Jan_2026.pdf

Expected ending balance:   $4,281.32
Calculated ending balance: $4,281.32

✓ Reconciled
```

If it does not match:

```text
Expected ending balance:   $4,281.32
Calculated ending balance: $4,181.32

❌ Difference: $100.00
```

This should be treated as an important validation step before marking a statement as successfully processed.

---

# 23. Dashboard — Lower Priority

The dashboard should be built after the data pipeline is reliable.

Potential technology:

```text
SQLite
   ↓
Streamlit
   ↓
Dashboard
```

Potential dashboard features:

- Date range selector
- Total income
- Total expenses
- Net income
- Spending by category
- Spending by merchant
- Monthly spending
- Uncategorized transactions
- Transactions requiring review

Example:

```text
------------------------------------------------
             Spending Dashboard
------------------------------------------------

Date: [Jan 1, 2026] → [Sep 7, 2026]

Income             $52,430
Expenses           $31,284
Net                $21,146

------------------------------------------------

Spending by Category

Groceries          $4,230
Food               $3,840
Bills              $8,120
Shopping           $5,210
Miscellaneous      $1,250

------------------------------------------------

Top Merchants

Costco             $1,240
Amazon             $980
Kroger             $740
DoorDash           $520
```

The dashboard should query SQLite rather than directly reading the PDFs.

---

# 24. Recommended Implementation Order

Implement the project incrementally in this order:

### Phase 1 — PDF Extraction

```text
PDF
 ↓
pypdf
 ↓
Raw text
```

### Phase 2 — Transaction Parsing

```text
Raw text
 ↓
Normalized transactions
```

### Phase 3 — Categorization

```text
Normalized transactions
 ↓
Merchant + category + transaction type
```

### Phase 4 — SQLite

```text
Categorized transactions
 ↓
SQLite
```

### Phase 5 — Duplicate Detection

Make processing idempotent so the same statement can safely be processed multiple times.

### Phase 6 — Reconciliation

Verify that parsed transactions match the statement's beginning/ending balances where available.

### Phase 7 — Excel

Generate Excel from SQLite.

### Phase 8 — Dashboard

Build the dashboard only after the underlying data is reliable.

---

# 25. Final Architecture

The target architecture is:

```text
                         BANK STATEMENTS
                               |
                               v
                        +--------------+
                        |   pypdf      |
                        | PDF Reader   |
                        +--------------+
                               |
                               v
                        +--------------+
                        | Transaction  |
                        |    Parser    |
                        +--------------+
                               |
                               v
                        +--------------+
                        | Normalized   |
                        | Transactions |
                        +--------------+
                               |
                               v
                        +--------------+
                        | Categorizer  |
                        +--------------+
                               |
                               v
                    +-----------------------+
                    | Validation / Review   |
                    | - Duplicate detection |
                    | - Reconciliation      |
                    +-----------------------+
                               |
                         +-----+-----+
                         |           |
                         v           v
                    +---------+  +---------+
                    | SQLite  |  |  Excel  |
                    |   DB    |  | Export  |
                    +---------+  +---------+
                         |
                         v
                    +-----------+
                    | Dashboard |
                    | (later)   |
                    +-----------+
```

## Core Design Principles

1. **SQLite is the source of truth.**
2. **PDF extraction, parsing, categorization, and storage are separate responsibilities.**
3. **Store numeric amounts, not display formatting.**
4. **Use `INCOME`, `EXPENSE`, and `TRANSFER` transaction types.**
5. **Do not count credit card payments as spending.**
6. **Keep original descriptions for traceability.**
7. **Normalize merchants separately from descriptions.**
8. **Use configurable rules for categorization.**
9. **Unknown transactions should be marked `Uncategorized` / `needs_review`, not blindly classified as Miscellaneous.**
10. **Prevent duplicate transactions.**
11. **Reconcile parsed data against statement balances where possible.**
12. **Generate Excel from SQLite.**
13. **Build the dashboard only after the data pipeline is reliable.**
14. **Start with deterministic rule-based categorization; AI can be added later if useful.**

---

# 26. First Development Milestone

The first useful version should accomplish:

```text
Put PDF into:
    statements/

Run:
    python main.py

Result:

PDF extracted
      ↓
Transactions parsed
      ↓
Transactions categorized
      ↓
Duplicates checked
      ↓
SQLite updated
      ↓
Excel generated
      ↓
PDF moved to processed/
```

At this point, the project already provides a complete automated spending-analysis pipeline. The dashboard can then be added without changing the core architecture.
