import argparse
from pathlib import Path
from src.categorizer import categorize, load_rules
from src.database import connect, insert_transactions
from src.excel_exporter import export
from src.pdf_reader import extract_pdf_text
from src.text_reader import read_statement_text
from src.parsers.chase_checking import ChaseCheckingParser
from src.parsers.credit_card import ChaseCreditParser, CitiParser, DiscoverParser, AmexParser

PARSERS=[ChaseCheckingParser(), ChaseCreditParser(), CitiParser(), DiscoverParser(), AmexParser()]


def parse_file(path: Path):
    text=extract_pdf_text(path) if path.suffix.lower()==".pdf" else read_statement_text(path)
    for parser in PARSERS:
        if parser.can_parse(text): return parser.parse(text, source_file=path.name), parser.account_name
    raise ValueError(f"No parser matched {path.name}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="statements")
    ap.add_argument("--db",default="database/spending.db")
    ap.add_argument("--excel",default="output/spending.xlsx")
    ap.add_argument("--rules",default="config/merchant_rules.json")
    args=ap.parse_args(); rules=load_rules(args.rules); conn=connect(args.db); total=0
    paths=sorted([*Path(args.input).glob("*.pdf"), *Path(args.input).glob("*.txt")])
    for path in paths:
        txs,account=parse_file(path); txs=[categorize(t,rules) for t in txs]
        total += insert_transactions(conn,txs); print(f"{path.name}: {len(txs)} parsed ({account})")
    export(conn,args.excel); print(f"Inserted {total} new transactions")

if __name__=="__main__": main()
