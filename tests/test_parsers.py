from decimal import Decimal
from src.parsers.chase_checking import ChaseCheckingParser
from src.parsers.credit_card import ChaseCreditParser, CitiParser, DiscoverParser, AmexParser


def test_chase_credit():
    text="""CHASE FREEDOM UNLIMITED
Date of Transaction Merchant Name or Transaction Description $ Amount
07/31 Payment Thank You-Mobile -117.23
07/07 METROPOLIS PARKING METROPOLIS.IO TN 9.99
08/03 DD *DOORDASH CURRITO 855-431-0459 CA 15.98
"""
    tx=ChaseCreditParser().parse(text)
    assert len(tx)==3 and tx[0].amount==Decimal("117.23") and tx[0].transaction_type.value=="TRANSFER"


def test_citi():
    text="""Citi Diamond Preferred
Trans. date Post date Description Amount
Payments, Credits and Adjustments
09/01
ONLINE PAYMENT, THANK YOU
-
$87.29
Standard P
urchases
08/22
08/22
DD/BR #344417 CINCINNATI OH
$9.67
08/23
08/23
TST* ALIVE & WELL CINCINNATI OH
$8.55
"""
    tx=CitiParser().parse(text)
    assert len(tx)==3 and tx[0].transaction_type.value=="TRANSFER" and tx[1].amount==Decimal("-9.67")


def test_discover():
    text="""DISCOVER IT CARD
TRANS.
DATE PURCHASES MERCHANT CATEGORY AMOUNT
09/01 INTERNET PAYMENT - THANK YOU -$18.56
08/09 SPECTRUM 855-707-7328 MO Services $40.00
08/22 ABC*7663-CRUNCH FITNESS7 859-371-2348 KY
Travel/Entertainment $360.00
"""
    tx=DiscoverParser().parse(text)
    assert len(tx)==3 and tx[0].transaction_type.value=="TRANSFER" and tx[1].category=="Bills"


def test_discover_uses_statement_period_instead_of_unrelated_future_year():
    text="""DISCOVER IT CARD
Your next automatic payment will be on April 22, 2027.
OPEN TO CLOSE DATE: 07/26/2026 - 08/25/2026
TRANS.
DATE PURCHASES MERCHANT CATEGORY AMOUNT
07/26 INTERNET PAYMENT - THANK YOU -$268.75
08/05 APPLE.COM/BILL Merchandise $14.38
08/23 APPLE.COM/BILL Merchandise $21.31
"""
    tx=DiscoverParser().parse(text)
    assert [item.transaction_date.isoformat() for item in tx] == [
        "2026-07-26",
        "2026-08-05",
        "2026-08-23",
    ]


def test_discover_resolves_dates_across_calendar_years():
    text="""DISCOVER IT CARD
OPEN TO CLOSE DATE: 12/26/2025 - 01/25/2026
TRANS.
DATE PURCHASES MERCHANT CATEGORY AMOUNT
12/30 STORE A Merchandise $10.00
01/03 STORE B Merchandise $20.00
"""
    tx=DiscoverParser().parse(text)
    assert [item.transaction_date.isoformat() for item in tx] == [
        "2025-12-30",
        "2026-01-03",
    ]


def test_amex():
    text="""Blue Cash Everyday
Payments Details
08/01/26* MOBILE PAYMENT - THANK YOU -$1,047.04
Credits Details
07/28/26 DD *DOORDASHDASHPASS
SAN FRANCISCO CA
-$5.16
New Charges Details
07/09/26 DD *CINCYGOURMETDELI $10.00
07/10/26 DD *DOORDASH CINCYGOUR $8.02
"""
    tx=AmexParser().parse(text)
    assert len(tx)==3
    assert any(t.transaction_type.value=="TRANSFER" for t in tx)
    assert any(t.amount==Decimal("-10.00") for t in tx)


def test_chase_checking_embedded_transaction_date():
    text="""Chase College Checking
STATEMENT PERIOD August 06, 2026 through September 03, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
08/19 Card Purchase 08/18 Chipotle -10.10 3,000.00
"""
    tx=ChaseCheckingParser().parse(text)
    assert tx[0].transaction_date.isoformat()=="2026-08-18"
    assert tx[0].posted_date.isoformat()=="2026-08-19"


def test_chase_checking_preserves_negative_transaction_amount_and_stops_at_page_boundary():
    text="""Chase College Checking
STATEMENT PERIOD August 06, 2026 through September 03, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
09/03 Card Purchase 09/01 Homedepot.Com 800-466-3337 GA Card 1256 -32.31 5,231.67
--- Page 3 ---
18848630202000000062
3 4Page of
*start*dreportraitdisclosure message area
*end*dreportraitdisclosure message area
August 06, 2026 through September 03, 2026
Account Number: 000000768711936
IN CASE OF ERRORS OR QUESTIONS ABOUT YOUR ELECTRONIC FUNDS TRANSFERS:
Call us at 1-866-564-2262 or write us at the address on the front of this statement.
"""
    tx = ChaseCheckingParser().parse(text)

    assert len(tx) == 1
    assert tx[0].transaction_date.isoformat() == "2026-09-01"
    assert tx[0].posted_date.isoformat() == "2026-09-03"
    assert tx[0].amount == Decimal("-32.31")
    assert tx[0].transaction_type.value == "EXPENSE"
    assert tx[0].description == "Card Purchase 09/01 Homedepot.Com 800-466-3337 GA Card 1256"
    assert tx[0].merchant == "09/01 Homedepot.Com 800-466-3337 GA Card 1256"


def test_chase_checking_uses_bare_period_instead_of_zip_code_year():
    text="""Chase College Checking
JPMorgan Chase Bank, N.A.
Columbus, OH 43218 - 2051
February 14, 2026 through March 13, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
02/17 Card Purchase 02/16 Chipotle -13.91 616.99
"""
    tx=ChaseCheckingParser().parse(text)
    assert tx[0].transaction_date.isoformat() == "2026-02-16"
    assert tx[0].posted_date.isoformat() == "2026-02-17"


def test_chase_checking_tracks_periods_across_combined_statements():
    text="""Chase College Checking
December 13, 2025 through January 15, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
12/15 Card Purchase 12/14 Store A -10.00 100.00
01/05 Card Purchase 01/03 Store B -20.00 80.00
--- Page 2 ---
February 14, 2026 through March 13, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
02/17 Card Purchase 02/16 Store C -30.00 50.00
"""
    tx=ChaseCheckingParser().parse(text)
    assert [item.transaction_date.isoformat() for item in tx] == [
        "2025-12-14",
        "2026-01-03",
        "2026-02-16",
    ]
    assert [item.posted_date.isoformat() for item in tx] == [
        "2025-12-15",
        "2026-01-05",
        "2026-02-17",
    ]


def test_chase_checking_allows_purchase_date_before_period_start():
    text="""Chase College Checking
January 16, 2026 through February 13, 2026
TRANSACTION DETAIL
DATE DESCRIPTION AMOUNT BALANCE
01/16 Card Purchase 01/15 Store A -10.00 100.00
"""
    tx=ChaseCheckingParser().parse(text)
    assert tx[0].transaction_date.isoformat() == "2026-01-15"
    assert tx[0].posted_date.isoformat() == "2026-01-16"
