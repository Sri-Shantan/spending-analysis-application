import argparse
import hashlib
from pathlib import Path
from src.categorizer import categorize, load_rules, recategorize_transactions
from src.data_quality import validate_statement
from src.database import connect, insert_transactions, register_statement
from src.excel_exporter import export
from src.pdf_reader import extract_pdf_text
from src.reconciliation import reconcile_statement
from src.statement_metadata import extract_statement_period
from src.text_reader import read_statement_text
from src.parsers.chase_checking import ChaseCheckingParser
from src.parsers.credit_card import ChaseCreditParser, CitiParser, DiscoverParser, AmexParser

PARSERS = [ChaseCheckingParser(), ChaseCreditParser(), CitiParser(), DiscoverParser(), AmexParser()]


def parse_file(path: Path):
    text = extract_pdf_text(path) if path.suffix.lower() == ".pdf" else read_statement_text(path)
    for parser in PARSERS:
        if parser.can_parse(text):
            return parser.parse(text, source_file=path.name), parser.account_name, text
    raise ValueError(f"No parser matched {path.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="statements")
    ap.add_argument("--db", default="database/spending.db")
    ap.add_argument("--excel", default="output/spending.xlsx")
    ap.add_argument("--rules", default="config/merchant_rules.json")
    ap.add_argument("--recategorize", action="store_true", help="Re-apply merchant rules to existing transactions")
    args = ap.parse_args()
    rules = load_rules(args.rules)
    conn = connect(args.db)

    if args.recategorize:
        updated = recategorize_transactions(conn, rules)
        export(conn, args.excel)
        print(f"Re-categorized {updated} transactions")
        return

    total = 0
    paths = sorted([*Path(args.input).glob("*.pdf"), *Path(args.input).glob("*.txt")])

    for path in paths:
        txs, account, text = parse_file(path)
        statement_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        start, end = extract_statement_period(text)
        statement_id, is_new = register_statement(conn, path.name, account, start, end, statement_hash)
        if not is_new:
            print(f"{path.name}: already ingested; skipped")
            continue

        txs = [categorize(t, rules) for t in txs]
        inserted = insert_transactions(conn, txs, statement_id=statement_id)
        total += inserted
        reconciliation = reconcile_statement(conn, statement_id, len(txs), inserted)
        quality = validate_statement(conn, statement_id)

        print(f"{path.name}: {len(txs)} parsed ({account})")
        print(
            f"  reconciliation: {reconciliation.status.value}; "
            f"inserted={reconciliation.inserted_count}; "
            f"duplicates={reconciliation.duplicate_count}; "
            f"needs_review={reconciliation.needs_review_count}"
        )
        print(
            f"  data quality: {'PASS' if quality.passed else 'REVIEW'}; "
            f"transactions={quality.transaction_count}; "
            f"outside_period={quality.outside_period_count}; "
            f"missing_hash={quality.missing_hash_count}; "
            f"invalid_amount={quality.invalid_amount_count}; "
            f"invalid_type={quality.invalid_type_count}"
        )

        if not quality.passed:
            conn.execute("UPDATE statements SET status = 'REVIEW_REQUIRED' WHERE id = ?", (statement_id,))
            conn.commit()

    export(conn, args.excel)
    print(f"Inserted {total} new transactions")


if __name__ == "__main__":
    main()
