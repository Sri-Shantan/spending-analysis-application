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
