from pathlib import Path


def read_statement_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:200]:
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(encoding).lstrip("\ufeff")
            except UnicodeDecodeError:
                pass
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")
