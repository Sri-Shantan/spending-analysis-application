from decimal import Decimal

from src.parsers.common import classify_direction, parse_money, trailing_money


def test_parse_money_supports_common_sign_and_currency_variants():
    assert parse_money("- 4.69") == Decimal("-4.69")
    assert parse_money("-$4.69") == Decimal("-4.69")
    assert parse_money("+$1,234.56") == Decimal("1234.56")


def test_trailing_money_separates_description_from_amount():
    assert trailing_money("Merchant name - $12.34") == (
        Decimal("-12.34"),
        "Merchant name",
    )


def test_classify_direction_uses_transaction_wording_not_bank_name():
    assert classify_direction("Zelle Payment To Friend")[0].value == "EXPENSE"
    assert classify_direction("Zelle From Friend")[0].value == "INCOME"
    assert classify_direction("Ordinary purchase") is None
