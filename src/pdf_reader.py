from pathlib import Path
from pypdf import PdfReader


def extract_pdf_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for number, page in enumerate(reader.pages, 1):
        pages.append(f"--- Page {number} ---\n{page.extract_text() or ''}")
    return "\n\n".join(pages)
