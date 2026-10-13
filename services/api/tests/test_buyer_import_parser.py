"""Import files remain bounded source claims, never executable or verified contacts."""
import importlib
import io
import zipfile
from xml.sax.saxutils import escape

import pytest


def parse(content, filename="buyers.csv"):
    spec = importlib.util.find_spec("buyeros_api.services.buyer_import_parser")
    assert spec is not None, "buyer import parser is not implemented"
    return importlib.import_module(spec.name).parse_buyer_file(content, filename)


def workbook(rows, *, title="Buyer List", formulas=None, extra=None):
    """Small real OOXML archive; no third-party workbook mock."""
    cells = []
    for row_index, values in rows:
        row_cells = []
        for column, value in enumerate(values):
            ref = f"{chr(65 + column)}{row_index}"
            formula = f"<f>{escape(formulas[ref])}</f>" if formulas and ref in formulas else ""
            row_cells.append(f'<c r="{ref}" t="inlineStr">{formula}<is><t>{escape(value)}</t></is></c>')
        cells.append(f'<row r="{row_index}">{"".join(row_cells)}</row>')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{title}" sheetId="1" r:id="r1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(cells)}</sheetData></worksheet>')
        for path, data in (extra or {}).items():
            archive.writestr(path, data)
    return stream.getvalue()


def test_csv_aliases_preserve_original_fields_and_source_claims():
    payload = '\ufeffCompany / trading name,Website,Checked on,Public contact route,Commercial hypothesis (not verified interest),Source row\r\nExample Foods,https://WWW.EXAMPLE.COM/catalogue,2026-09-18,sales@example.com,May be interested,Buyer List!A5:F5\r\n'.encode()
    result = parse(payload)
    row = result["rows"][0]
    assert row["name"] == "Example Foods"
    assert row["normalized_domain"] == "example.com"
    assert row["website"] == "https://www.example.com/catalogue"
    assert row["source_date"] == "2026-09-18"
    assert row["source_row"] == "Buyer List!A5:F5"
    assert row["original_fields"]["Public contact route"] == "sales@example.com"
    assert row["original_fields"]["Commercial hypothesis (not verified interest)"] == "May be interested"
    assert row["errors"] == []
    assert "contacts" not in row and "fit" not in row


def test_xlsx_skips_cover_rows_and_preserves_numeric_source_date_and_row():
    content = workbook([(1, ["Research workbook"]), (4, ["Company / trading name", "Website", "Checked on"]), (5, ["Sample Buyer", "https://buyer.example", "46283"])])
    row = parse(content, "buyers.xlsx")["rows"][0]
    assert row["source_row"] == "Buyer List!A5:C5"
    assert row["row_number"] == 5
    assert row["source_date"] == "2026-09-18"
    assert row["original_fields"]["Checked on"] == "46283"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "https://user:password@example.com", "https://127.0.0.1", "https://example.com\\@evil.com", "http://localhost", "https://example.com\n.evil.com"])
def test_unsafe_urls_are_row_errors_and_never_become_clickable_urls(url):
    import csv
    text = io.StringIO()
    csv.writer(text).writerows([["Company", "Website"], ["A Buyer", url]])
    row = parse(text.getvalue().encode())["rows"][0]
    assert row["errors"]
    assert row["website"] is None
    assert row["normalized_domain"] is None
    assert row["original_fields"]["Website"] == url


def test_missing_name_duplicate_headers_and_ragged_csv_do_not_silently_shift_values():
    for content in (b"Website\nhttps://example.com\n", b"Company,Company\nOne,Two\n", b"Company,Website\nOne,https://example.com,EXTRA\n"):
        with pytest.raises(ValueError):
            parse(content)
    row = parse(b"Company,Website\n,https://example.com\n")["rows"][0]
    assert row["errors"]


def test_formula_cells_are_reported_as_invalid_without_using_cached_values():
    content = workbook([(1, ["Company", "Website"]), (2, ["Buyer", "https://example.com"])], formulas={"B2": 'HYPERLINK("https://evil.example","https://example.com")'})
    row = parse(content, "buyers.xlsx")["rows"][0]
    assert row["errors"]
    assert row["website"] is None


def test_only_bounded_supported_files_are_accepted():
    for content, filename in ((b"Company\nBuyer", "buyers.xls"), (b"not a zip", "buyers.xlsx"), (b"\xff\xfe", "buyers.csv"), (b"Company\n" + b"a" * (5 * 1024 * 1024), "buyers.csv")):
        with pytest.raises(ValueError):
            parse(content, filename)
    with pytest.raises(ValueError):
        parse(b"Company\n" + b"Buyer\n" * 501)
    with pytest.raises(ValueError):
        parse(workbook([(1, ["Company"]), (2, ["Buyer"])], extra={"xl/vbaProject.bin": b"macro"}), "buyers.xlsx")


def test_xlsx_dtd_entities_and_oversized_expansion_are_rejected():
    payload = workbook([(1, ["Company"]), (2, ["Buyer"])], extra={"xl/sharedStrings.xml": b'<!DOCTYPE x [<!ENTITY x "bad">]><sst>&x;</sst>'})
    with pytest.raises(ValueError):
        parse(payload, "buyers.xlsx")
    payload = workbook([(1, ["Company"]), (2, ["Buyer"])], extra={"xl/sharedStrings.xml": b" " * (17 * 1024 * 1024)})
    with pytest.raises(ValueError):
        parse(payload, "buyers.xlsx")


def test_url_domain_that_cannot_fit_company_storage_is_a_preview_error():
    host = ".".join(["a" * 63] * 5) + ".example"
    row = parse(f"Company,Website\nBuyer,https://{host}\n".encode())["rows"][0]
    assert row["errors"]
    assert row["normalized_domain"] is None


def test_expanded_excel_source_text_is_bounded_even_when_the_zip_is_small():
    content = workbook([(1, ["Company", "Notes"])] + [(index + 2, [f"Buyer {index}", "N" * 10000]) for index in range(300)])
    assert len(content) < 100000
    with pytest.raises(ValueError, match="source text"):
        parse(content, "buyers.xlsx")


def test_repeated_header_bytes_cannot_create_an_oversized_json_manifest():
    import csv
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(["Company"] + ["資料" * 98 + str(index) for index in range(63)])
    writer.writerows([[f"Buyer {index}"] + [""] * 63 for index in range(500)])
    with pytest.raises(ValueError, match="source data"):
        parse(text.getvalue().encode())


def test_nul_in_header_is_rejected_before_postgres_json_serialization():
    with pytest.raises(ValueError):
        parse(b"Company\x00,Website\nBuyer,https://example.com\n")


@pytest.mark.parametrize("host", ["127.1", "0x7f.1", "0177.0.0.1"])
def test_browser_style_ip_shorthand_cannot_become_a_public_source_link(host):
    row = parse(f"Company,Website\nBuyer,https://{host}\n".encode())["rows"][0]
    assert row["website"] is None
    assert row["errors"]
