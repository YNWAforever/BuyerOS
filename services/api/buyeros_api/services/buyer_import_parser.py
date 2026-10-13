"""Bounded, offline CSV/OOXML parsing. All cells remain unverified source claims."""
import csv
import hashlib
import io
import ipaddress
import json
import posixpath
import re
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from pathlib import PurePath
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 500
MAX_COLUMNS = 64
MAX_CELL_CHARS = 10000
MAX_SOURCE_CHARS = 2000000
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 16 * 1024 * 1024
_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _key(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())


_ALIASES = {
    "name": {"company", "companyname", "companytradingname", "tradingname", "buyer", "buyername", "name", "公司", "公司名稱"},
    "website": {"website", "websiteurl", "url", "domain", "公司網站"},
    "source_date": {"checkedon", "sourcedate", "checkeddate", "asof", "observedon", "資料日期"},
    "source_row": {"sourcerow", "來源行"},
    "source_url": {"evidencesourceurl", "sourceurl", "evidenceurl", "來源網址"},
    "contact_url": {"contactsourceurl"},
}


def safe_url(raw: str) -> str | None:
    """Only ordinary public HTTP links; never evaluate or fetch an imported URL."""
    if not raw.strip():
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in raw) or "\\" in raw or len(raw) > 2000:
        raise ValueError("unsafe URL")
    value = raw.strip()
    if "://" not in value and re.fullmatch(r"[\w.-]+\.[a-zA-Z]{2,63}(?:/[^\s]*)?", value):
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode().lower().rstrip(".")
        if (parsed.scheme.lower() not in {"http", "https"} or parsed.username is not None
                or parsed.password is not None or parsed.port not in {None, 80, 443}
                or "." not in host or len(host) > 253 or host.endswith((".localhost", ".local", ".internal"))
                or not re.fullmatch(r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})", host.rsplit(".", 1)[-1])
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split("."))):
            raise ValueError("unsafe URL")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("IP address URLs are not supported")
        return urlunsplit((parsed.scheme.lower(), host + (f":{parsed.port}" if parsed.port else ""), parsed.path, parsed.query, parsed.fragment))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("unsafe URL") from exc


def identity_keys(name, domain):
    """Stable source identity hints, without claiming legal-entity verification."""
    normalized_name = " ".join(unicodedata.normalize("NFKC", name).lower().split())
    return (["domain:" + domain] if domain else []) + ["name:" + normalized_name]


def _xml(archive, path):
    raw = archive.read(path)
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw.replace(b"\x00", b""), re.I):
        raise ValueError("XML declarations and entities are not supported")
    return ET.fromstring(raw)


def _column_number(reference):
    match = re.fullmatch(r"([A-Z]+)[1-9][0-9]*", reference)
    if not match:
        raise ValueError("invalid spreadsheet cell reference")
    number = 0
    for char in match[1]:
        number = number * 26 + ord(char) - 64
    if number > MAX_COLUMNS:
        raise ValueError("spreadsheet exceeds 64 columns")
    return number


def _column_name(number):
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _xlsx(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            paths = [entry.filename for entry in entries]
            if (len(entries) > 256 or len(paths) != len(set(paths))
                    or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES
                    or any(entry.flag_bits & 1 for entry in entries)
                    or any("vbaproject" in path.lower() or "externallinks/" in path.lower() for path in paths)):
                raise ValueError("unsupported or oversized workbook archive")
            root = _xml(archive, "xl/workbook.xml")
            rels = _xml(archive, "xl/_rels/workbook.xml.rels")
            relation = {item.get("Id"): item for item in rels}
            strings = []
            if "xl/sharedStrings.xml" in paths:
                for item in _xml(archive, "xl/sharedStrings.xml").findall(_MAIN + "si"):
                    value = "".join(node.text or "" for node in item.iter(_MAIN + "t"))
                    if len(value) > MAX_CELL_CHARS:
                        raise ValueError("spreadsheet cell exceeds 10000 characters")
                    strings.append(value)
            sheets = root.findall(f"{_MAIN}sheets/{_MAIN}sheet")
            # Prefer the labelled buyer sheet, while ordinary single-sheet files work too.
            sheets.sort(key=lambda item: _key(item.get("name", "")) != "buyerlist")
            properties = root.find(_MAIN + "workbookPr")
            epoch = date(1904, 1, 1) if properties is not None and properties.get("date1904") in {"1", "true"} else date(1899, 12, 30)
            for sheet in sheets:
                rel = relation.get(sheet.get(_REL + "id"))
                if rel is None or rel.get("TargetMode") == "External":
                    raise ValueError("unsupported worksheet relationship")
                target = rel.get("Target", "")
                path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
                if not path.startswith("xl/worksheets/") or path not in paths:
                    raise ValueError("invalid worksheet path")
                rows = []
                source_chars = 0
                for row in _xml(archive, path).findall(f"{_MAIN}sheetData/{_MAIN}row"):
                    values = []
                    formulas = set()
                    for cell in row.findall(_MAIN + "c"):
                        column = _column_number(cell.get("r", ""))
                        while len(values) < column:
                            values.append("")
                        if cell.find(_MAIN + "f") is not None:
                            formulas.add(column - 1)
                            value = "=" + (cell.find(_MAIN + "f").text or "")
                        elif cell.get("t") == "inlineStr":
                            value = "".join(node.text or "" for node in cell.iter(_MAIN + "t"))
                        else:
                            value = cell.findtext(_MAIN + "v", "")
                            if cell.get("t") == "s":
                                index = int(value)
                                if index < 0 or index >= len(strings):
                                    raise ValueError("invalid shared string index")
                                value = strings[index]
                        if len(value) > MAX_CELL_CHARS:
                            raise ValueError("spreadsheet cell exceeds 10000 characters")
                        values[column - 1] = value
                    if any(values):
                        source_chars += sum(len(value) for value in values)
                        if source_chars > MAX_SOURCE_CHARS:
                            raise ValueError("workbook source text exceeds 2000000 characters")
                        rows.append((int(row.get("r", "0")), values, formulas))
                    if len(rows) > MAX_ROWS + 20:
                        raise ValueError("spreadsheet exceeds 500 buyer rows")
                if any(any(_key(value) in _ALIASES["name"] for value in values) for _, values, _ in rows[:20]):
                    return rows, sheet.get("name", "Sheet"), epoch
            raise ValueError("workbook has no recognised company-name header")
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, TypeError, OverflowError) as exc:
        raise ValueError("invalid XLSX workbook") from exc


def _source_date(raw, epoch):
    if not raw.strip():
        return None
    value = raw.strip()
    if epoch is not None and re.fullmatch(r"[0-9]{1,5}(?:\.0+)?", value):
        return (epoch + timedelta(days=int(float(value)))).isoformat()
    for format in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, format).date().isoformat()
        except ValueError:
            pass
    raise ValueError("source date must be an ISO date (YYYY-MM-DD)")


def parse_buyer_file(content: bytes, filename: str) -> dict:
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("file must contain data and be at most 5 MiB")
    filename = PurePath(filename.replace("\\", "/")).name
    if not filename or len(filename) > 200 or any(ord(char) < 32 for char in filename):
        raise ValueError("invalid file name")
    if filename.lower().endswith(".csv"):
        try:
            decoded = content.decode("utf-8-sig")
            rows = []
            source_chars = 0
            for index, values in enumerate(csv.reader(io.StringIO(decoded), strict=True), 1):
                if any(values):
                    source_chars += sum(len(value) for value in values)
                    if source_chars > MAX_SOURCE_CHARS:
                        raise ValueError("CSV source text exceeds 2000000 characters")
                    rows.append((index, values, set()))
                if len(rows) > MAX_ROWS + 20:
                    raise ValueError("CSV exceeds 500 buyer rows")
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("CSV must be valid UTF-8 with consistent quoting") from exc
        sheet, epoch = "CSV", None
    elif filename.lower().endswith(".xlsx"):
        rows, sheet, epoch = _xlsx(content)
    else:
        raise ValueError("only UTF-8 CSV and XLSX files are supported")
    header_index = next((index for index, (_, values, _) in enumerate(rows[:20]) if any(_key(value) in _ALIASES["name"] for value in values)), None)
    if header_index is None:
        raise ValueError("a Company or Company / trading name header is required")
    headers = [value.strip() for value in rows[header_index][1]]
    while headers and not headers[-1]:
        headers.pop()
    if not 1 <= len(headers) <= MAX_COLUMNS or any(not value or len(value) > 200 or "\x00" in value for value in headers) or len({_key(value) for value in headers}) != len(headers):
        raise ValueError("headers must be unique, nonempty and at most 64 columns")
    aliases = {}
    for field, variants in _ALIASES.items():
        matches = [header for header in headers if _key(header) in variants]
        if len(matches) > 1:
            raise ValueError(f"ambiguous {field} headers")
        aliases[field] = matches[0] if matches else None
    data_rows = rows[header_index + 1:]
    if not 1 <= len(data_rows) <= MAX_ROWS:
        raise ValueError("file must contain 1 to 500 buyer rows")
    parsed = []
    source_bytes = 0
    for row_number, values, formulas in data_rows:
        if len(values) > len(headers) and any(values[len(headers):]):
            raise ValueError(f"row {row_number} has values outside the header columns")
        if sheet == "CSV" and len(values) != len(headers):
            raise ValueError(f"row {row_number} has a different number of columns")
        if any(len(value) > MAX_CELL_CHARS or "\x00" in value for value in values):
            raise ValueError(f"row {row_number} has an unsupported cell value")
        original = dict(zip(headers, values + [""] * (len(headers) - len(values))))
        get = lambda field: original.get(aliases.get(field), "")
        name = get("name").strip()
        errors = []
        if not 1 <= len(name) <= 400:
            errors.append("Company name must contain 1 to 400 characters")
        if formulas:
            errors.append("Formula cells are not supported; replace them with source values")
        website = None
        source_urls = []
        for field in ("website", "source_url", "contact_url"):
            if aliases.get(field) and headers.index(aliases[field]) in formulas:
                continue
            try:
                value = safe_url(get(field))
                if field == "website":
                    website = value
                elif value and value not in source_urls:
                    source_urls.append(value)
            except ValueError:
                errors.append(f"{aliases[field]} must be a safe public HTTP or HTTPS URL")
        try:
            source_date = _source_date(get("source_date"), epoch)
        except ValueError:
            source_date = None
            errors.append("Source date must be a valid date")
        domain = urlsplit(website).hostname.removeprefix("www.") if website else None
        source_row = get("source_row").strip() or f"{sheet}!A{row_number}:{_column_name(len(headers))}{row_number}"
        item = {"row_number": row_number, "source_row": source_row, "name": name,
                "normalized_domain": domain, "website": website, "source_date": source_date,
                "source_urls": source_urls, "original_fields": original, "errors": errors}
        # Count repeated header keys and normalized fields too, before staging JSONB.
        source_bytes += len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if source_bytes > MAX_SOURCE_BYTES:
            raise ValueError("serialized source data exceeds 8 MiB; split the file into smaller batches")
        parsed.append(item)
    return {"file_name": filename, "file_sha256": hashlib.sha256(content).hexdigest(), "rows": parsed}
