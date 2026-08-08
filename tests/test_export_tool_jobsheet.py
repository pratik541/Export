from export_tool import jobsheet

_CSV = (
    "Order Id,Setting SKU,Original Payment Method,Product Status,Setting Certificate No\n"
    "ORD1,SKU1,PAY-1,PARENT-1,SETCERT-1\n"
    "ORD2,SKU2,PAY-2,PARENT-2,SETCERT-2\n"
)


def test_indexes_a_row_under_every_populated_key_column():
    index, warnings = jobsheet.parse_jobsheet(_CSV.encode())

    assert index["ORD1"]["Original Payment Method"] == "PAY-1"
    assert index["SKU1"]["Original Payment Method"] == "PAY-1"
    assert index["ORD2"]["Setting Certificate No"] == "SETCERT-2"
    assert warnings == []


def test_first_row_wins_when_two_rows_share_a_key():
    csv_text = (
        "Order Id,Setting SKU,Original Payment Method,Product Status,Setting Certificate No\n"
        "DUP,SKU-D,FIRST,PARENT,SETCERT\n"
        "DUP,SKU-D,SECOND,PARENT,SETCERT\n"
    )

    index, warnings = jobsheet.parse_jobsheet(csv_text.encode())

    assert index["DUP"]["Original Payment Method"] == "FIRST"
    assert warnings == []


def test_missing_key_column_in_csv_is_ignored_not_an_error():
    # "Setting SKU" (a JOBSHEET_KEY_COLUMNS entry, but not a configured
    # JOBSHEET_COLUMNS value) is absent -- indexing still works via "Order
    # Id" alone, no warning (Order Id doubles as the configured design_no
    # column, so it must stay present here).
    csv_text = (
        "Order Id,Original Payment Method,Product Status,Setting Certificate No\n"
        "ORD9,PAY-9,PARENT,SETCERT\n"
    )

    index, warnings = jobsheet.parse_jobsheet(csv_text.encode())

    assert index["ORD9"]["Original Payment Method"] == "PAY-9"
    assert warnings == []


def test_blank_key_value_is_not_indexed():
    csv_text = (
        "Order Id,Setting SKU,Original Payment Method,Product Status,Setting Certificate No\n"
        ",SKU5,PAY-5,PARENT,SETCERT\n"
    )

    index, warnings = jobsheet.parse_jobsheet(csv_text.encode())

    assert "" not in index
    assert index["SKU5"]["Original Payment Method"] == "PAY-5"
    assert warnings == []


def test_missing_all_key_columns_warns():
    csv_text = "Foo,Bar\nx,y\n"

    index, warnings = jobsheet.parse_jobsheet(csv_text.encode())

    assert any(
        "None of the expected jobsheet key columns" in w and "check this is the right file" in w
        for w in warnings
    )
