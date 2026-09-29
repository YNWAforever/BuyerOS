"""CSV export safety (BO-023): formula neutralization plus correct quoting."""

import csv
import io
import unicodedata

FORMULA_PREFIX = ("=", "+", "-", "@")


def neutralize(value: str) -> str:
    """Prevent spreadsheet execution even when whitespace or controls lead a cell."""
    if not value:
        return value
    first = value[0]
    if first in FORMULA_PREFIX or first.isspace() or unicodedata.category(first) in {"Cc", "Cf"}:
        return "'" + value
    return value


def to_csv(rows: list[dict], columns: list[str], data_mode: str, *, include_data_mode: bool = True) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow([*columns, *(["data_mode"] if include_data_mode else [])])
    for row in rows:
        writer.writerow([neutralize("" if row.get(c) is None else str(row[c])) for c in columns]
                        + ([data_mode] if include_data_mode else []))
    return buf.getvalue()
