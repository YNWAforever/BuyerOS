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
