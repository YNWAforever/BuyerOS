"""CSV export safety (BO-023): formula neutralization plus correct quoting."""

import csv
import io

FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: str) -> str:
    if value and value[0] in FORMULA_PREFIX:
        return "'" + value
    return value


def to_csv(rows: list[dict], columns: list[str], data_mode: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow([*columns, "data_mode"])
    for row in rows:
        writer.writerow([neutralize(str(row.get(c, ""))) for c in columns] + [data_mode])
    return buf.getvalue()
