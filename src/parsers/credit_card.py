import re
from datetime import date, datetime
from decimal import Decimal
from src.models import Transaction, TransactionType
from src.parsers.base import StatementParser
from src.statement_metadata import extract_statement_period

DATE_RE = re.compile(r"^(\d{2}/\d{2})(?:\*)?\s+(.*)$")
AMOUNT_RE = re.compile(r"^([+-])?\$?([\d,]+\.\d{2})$")
TRAILING_AMOUNT_RE = re.compile(r"([+-]?\$?[\d,]+\.\d{2})\s*$")


def money(s: str) -> Decimal:
    negative = s.strip().startswith("-")
    value = Decimal(s.strip().lstrip("+-").replace("$", "").replace(",", ""))
    return -value if negative else value


def trailing_amount(text: str):
    m = TRAILING_AMOUNT_RE.search(text)
    return (money(m.group(1)), text[:m.start()].strip()) if m else (None, text)


class CreditCardParser(StatementParser):
    issuer: str
    def _year(self, text):
        years = [int(y) for y in re.findall(r"\b20\d{2}\b", text)]
        return max(years) if years else datetime.now().year
    def _date(self, mmdd: str, text: str) -> date:
        statement_start, statement_end = extract_statement_period(text)
        if statement_start and statement_end:
            start = date.fromisoformat(statement_start)
            end = date.fromisoformat(statement_end)
            month, day = (int(value) for value in mmdd.split("/"))
            candidates = []
            for year in {start.year, end.year}:
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                if start <= candidate <= end:
                    candidates.append(candidate)
            if len(candidates) == 1:
                return candidates[0]
            raise ValueError(f"Transaction date {mmdd} is outside statement period {start} to {end}")
        return datetime.strptime(f"{mmdd}/{self._year(text)}", "%m/%d/%Y").date()
    @staticmethod
    def _merchant(description): return re.sub(r"\s+", " ", description).strip()
    @staticmethod
    def _category(description):
        d = description.upper()
        if any(x in d for x in ("DOORDASH", "CHIPOTLE", "RESTAURANT", "TST*", "DD/BR")): return "Food"
        if any(x in d for x in ("SHELL", "GAS")): return "Gas"
        if any(x in d for x in ("COSTCO", "KROGER", "GROCERY", "JAGDEEP")): return "Groceries"
        if "PARKING" in d or "METROPOLIS" in d: return "Transportation"
        if any(x in d for x in ("SPECTRUM", "DUKE", "GOOGLE ONE")): return "Bills"
        if any(x in d for x in ("AMAZON", "FABLETICS", "HOME DEPOT", "NORDRACK", "NORDSTROM")): return "Shopping"
        if "INTEREST CHARGED" in d: return "Finance"
        return "Uncategorized"
    @staticmethod
    def _classify(description, amount):
        d = description.upper()
        if "PAYMENT" in d and any(x in d for x in ("THANK YOU", "MOBILE", "ONLINE", "INTERNET")): return TransactionType.TRANSFER, "Credit Card Payment"
        if "INTEREST CHARGED" in d: return TransactionType.EXPENSE, "Finance"
        if "CASHBACK" in d or "REWARD" in d: return TransactionType.ADJUSTMENT, "Rewards"
        if amount < 0: return TransactionType.ADJUSTMENT, "Refund/Credit"
        return TransactionType.EXPENSE, "Uncategorized"


class ChaseCreditParser(CreditCardParser):
    account_name = "Chase Credit Card"
    def can_parse(self, text): return "CHASE FREEDOM UNLIMITED" in text and "Date of" in text and "Transaction Merchant" in text
    def parse(self, text, source_file=None):
        lines=[x.strip() for x in text.splitlines()]; out=[]
        start=next((i for i,x in enumerate(lines) if x.startswith("Date of")),-1); i=start+1 if start>=0 else len(lines)
        while i<len(lines):
            m=DATE_RE.match(lines[i])
            if not m: i+=1; continue
            mmdd,rest=m.groups(); amount,desc=trailing_amount(rest); j=i
            if amount is None:
                parts=[rest]
                while j<len(lines) and not DATE_RE.match(lines[j]):
                    a,c=trailing_amount(lines[j])
                    if a is not None: amount=a; parts.append(c); break
                    if lines[j] and not lines[j].startswith("Total "): parts.append(lines[j])
                    j+=1
                desc=" ".join(parts).strip()
            if amount is None: i+=1; continue
            dt=self._date(mmdd,text); tt,cat=self._classify(desc,amount)
            if cat=="Uncategorized": cat=self._category(desc)
            normalized=-amount if tt==TransactionType.EXPENSE and amount>0 else (abs(amount) if tt==TransactionType.TRANSFER else amount)
            out.append(Transaction(dt,None,desc,self._merchant(desc),normalized,self.account_name,tt,cat,source_file=source_file)); i=j+1
        return out


class CitiParser(CreditCardParser):
    account_name="Citi Credit Card"
    def can_parse(self,text): return "Citi Diamond Preferred" in text and "Trans." in text and "Payments, Credits and Adjustments" in text
    def parse(self,text,source_file=None):
        lines=[x.strip() for x in text.splitlines()]; out=[]
        start=next((i for i,x in enumerate(lines) if x=="Payments, Credits and Adjustments"),-1); i=start+1 if start>=0 else len(lines)
        while i<len(lines):
            if not re.fullmatch(r"\d{2}/\d{2}",lines[i]): i+=1; continue
            mmdd=lines[i]; j=i+1; posted_str=None
            if j<len(lines) and re.fullmatch(r"\d{2}/\d{2}",lines[j]): posted_str=lines[j]; j+=1
            parts=[]; amount=None
            while j<len(lines) and not re.fullmatch(r"\d{2}/\d{2}",lines[j]):
                c=lines[j]
                if AMOUNT_RE.match(c): amount=money(c); break
                if c not in {"Standard P","urchases","Standard Purchases","Fees Charged","Interest Charged","Date","Description","Amount"} and c: parts.append(c)
                j+=1
            if amount is None: i+=1; continue
            dt=self._date(mmdd,text); posted=self._date(posted_str or mmdd,text); tt,cat=self._classify(" ".join(parts),amount)
            if tt==TransactionType.EXPENSE: cat=self._category(" ".join(parts))
            normalized=-amount if tt==TransactionType.EXPENSE and amount>0 else (abs(amount) if tt==TransactionType.TRANSFER else amount)
            out.append(Transaction(dt,posted if posted!=dt else None," ".join(parts),self._merchant(" ".join(parts)),normalized,self.account_name,tt,cat,source_file=source_file)); i=j+1
        return out


class DiscoverParser(CreditCardParser):
    account_name="Discover Credit Card"
    def can_parse(self,text): return "DISCOVER IT CARD" in text and "DATE PURCHASES MERCHANT CATEGORY AMOUNT" in text
    def parse(self,text,source_file=None):
        lines=[x.strip() for x in text.splitlines()]; out=[]
        start=next((i for i,x in enumerate(lines) if x=="DATE PURCHASES MERCHANT CATEGORY AMOUNT" and i>0 and lines[i-1]=="TRANS."),-1)
        if start<0:return out
        for i in range(start+1,len(lines)):
            m=re.search(r"(\d{2}/\d{2})\s+(.*)$",lines[i])
            if not m: continue
            mmdd,rest=m.groups(); amount,clean=trailing_amount(rest); parts=[clean]; j=i+1
            while amount is None and j<len(lines) and not re.search(r"^\d{2}/\d{2}\s+",lines[j]):
                c=lines[j]; a,cl=trailing_amount(c)
                if a is not None: amount=a; parts.append(cl); break
                if c and not c.startswith(("TOTAL ","PREVIOUS BALANCE")): parts.append(c)
                j+=1
            if amount is None: continue
            desc=re.sub(r"^.*?\+\$[\d.]+",""," ".join(parts)).strip(); dt=self._date(mmdd,text); tt,cat=self._classify(desc,amount)
            if tt==TransactionType.EXPENSE: cat=self._category(desc)
            normalized=-amount if tt==TransactionType.EXPENSE and amount>0 else (abs(amount) if tt==TransactionType.TRANSFER else amount)
            out.append(Transaction(dt,None,desc,self._merchant(desc),normalized,self.account_name,tt,cat,source_file=source_file))
        return out


class AmexParser(CreditCardParser):
    account_name="Amex Blue Cash Everyday"
    AMEX_DATE_RE=re.compile(r"^(\d{2}/\d{2}/\d{2})(?:\*)?\s+(.*)$")
    def can_parse(self,text): return "Blue Cash Everyday" in text and "New Charges Details" in text and "Payments and Credits Summary" in text
    def _parse_section(self,lines,start,end,kind,source_file):
        out=[]; i=start
        while i<end:
            m=self.AMEX_DATE_RE.match(lines[i])
            if not m: i+=1; continue
            datestr,rest=m.groups(); amount,clean=trailing_amount(rest); parts=[clean]; j=i+1
            while amount is None and j<end and not self.AMEX_DATE_RE.match(lines[j]):
                c=lines[j]; a,cl=trailing_amount(c)
                if a is not None: amount=a; parts.append(cl); break
                if c and not c.startswith("Total "): parts.append(c)
                j+=1
            if amount is None: i+=1; continue
            dt=datetime.strptime(datestr,"%m/%d/%y").date(); desc=" ".join(p for p in parts if p).strip()
            if kind=="charge": tt,cat,normalized=TransactionType.EXPENSE,self._category(desc),-abs(amount)
            elif "PAYMENT" in desc.upper(): tt,cat,normalized=TransactionType.TRANSFER,"Credit Card Payment",abs(amount)
            else: tt,cat,normalized=TransactionType.ADJUSTMENT,"Refund/Credit",abs(amount)
            out.append(Transaction(dt,None,desc,self._merchant(desc),normalized,self.account_name,tt,cat,source_file=source_file)); i=j+1
        return out
    def parse(self,text,source_file=None):
        lines=[x.strip() for x in text.splitlines()]; out=[]
        payment=next((i for i,x in enumerate(lines) if x=="Payments Details"),-1); credits=next((i for i,x in enumerate(lines) if x=="Credits Details"),-1); charges=next((i for i,x in enumerate(lines) if x=="New Charges Details"),-1)
        if payment>=0: out+=self._parse_section(lines,payment+1,credits if credits>payment else charges,"credit",source_file)
        if credits>=0: out+=self._parse_section(lines,credits+1,charges if charges>credits else len(lines),"credit",source_file)
        if charges>=0: out+=self._parse_section(lines,charges+1,len(lines),"charge",source_file)
        return out
