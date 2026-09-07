from pathlib import Path
import sqlite3
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font


def export(conn: sqlite3.Connection, output: str | Path) -> None:
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    wb=Workbook(); ws=wb.active; ws.title="Transactions"
    headers=["date_of_transaction","posted_date","description","merchant","amount","account","transaction_type","category","subcategory","source_file","needs_review"]
    ws.append(headers)
    for c in ws[1]: c.font=Font(bold=True)
    rows=conn.execute("SELECT transaction_date,posted_date,description,merchant,amount,account,transaction_type,category,subcategory,source_file,needs_review FROM transactions ORDER BY transaction_date").fetchall()
    for row in rows: ws.append(row)
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    ws.column_dimensions["C"].width=45; ws.column_dimensions["D"].width=28; ws.column_dimensions["E"].width=14
    for cell in ws["E"][1:]: cell.number_format='$#,##0.00;[Red]-$#,##0.00'
    last=max(ws.max_row,2)
    ws.conditional_formatting.add(f"E2:E{last}", CellIsRule(operator="lessThan", formula=["0"], font=Font(color="9C0006")))
    ws.conditional_formatting.add(f"E2:E{last}", CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="006100")))
    wb.save(output)
