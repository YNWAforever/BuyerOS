from buyeros_api.services.csv_export import neutralize, to_csv


def test_formula_prefixes_are_neutralized():
    for value in ("=1+1", "+x", "-x", "@x", "\t=x", "\r=x"):
        assert neutralize(value).startswith("'")


def test_safe_values_are_unchanged():
    assert neutralize("normal") == "normal"


def test_quotes_and_newlines_are_escaped():
    out = to_csv([{"name": 'A, "B"', "city": "X\nY"}], ["name", "city"], "live")
    assert '"A, ""B"""' in out


def test_export_carries_mode_column():
    out = to_csv([{"name": "A"}], ["name"], "live")
    header = out.splitlines()[0]
    assert "data_mode" in header
    assert '"live"' in out


def test_leading_space_controls_unicode_and_formula_are_inert():
    import csv
    import io

    values = ["  =SUM(1,2)", "\x00@cmd", "\u200b+1", "\tcmd", "\r=1", "-2", "normal\n\u4e2d文"]
    out = to_csv([{"name": value} for value in values], ["name"], "live")
    parsed = list(csv.DictReader(io.StringIO(out)))
    assert len(parsed) == len(values)
    for original, row in zip(values[:-1], parsed[:-1]):
        assert row["name"] == "'" + original
    assert parsed[-1]["name"] == values[-1]
    assert all(row["data_mode"] == "live" for row in parsed)


def test_bulk_failure_report_has_only_whitelisted_columns_and_inert_reason():
    import csv
    import io

    out = to_csv([{"buyer_id": "00000000-0000-4000-8000-000000000001",
                   "status": "blocked", "reason_code": " \t=HYPERLINK"}],
                 ["buyer_id", "status", "reason_code"], "live", include_data_mode=False)
    assert out.splitlines()[0] == '"buyer_id","status","reason_code"'
    assert "data_mode" not in out
    assert list(csv.DictReader(io.StringIO(out)))[0]["reason_code"] == "' \t=HYPERLINK"
