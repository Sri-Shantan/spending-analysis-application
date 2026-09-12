import json
from pathlib import Path
from src.models import Transaction


def load_rules(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def categorize(transaction: Transaction, rules: dict) -> Transaction:
    text = transaction.description.upper()
    for rule in rules.get("rules", []):
        if any(keyword.upper() in text for keyword in rule["keywords"]):
            return Transaction(**{**transaction.__dict__, "category": rule["category"], "subcategory": rule.get("subcategory"), "needs_review": False})
    return Transaction(**{**transaction.__dict__, "needs_review": transaction.category == "Uncategorized"})
