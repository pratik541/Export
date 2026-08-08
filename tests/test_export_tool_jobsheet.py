from export_tool import jobsheet

_CSV = (
    "Order Id,Setting SKU,Original Payment Method,Product Status,Setting Certificate No\n"
    "ORD1,SKU1,PAY-1,PARENT-1,SETCERT-1\n"
    "ORD2,SKU2,PAY-2,PARENT-2,SETCERT-2\n"
)


def test_indexes_a_row_under_every_populated_key_column():
    index = jobsheet.parse_jobsheet(_CSV.encode())

    assert index["ORD1"]["Original Payment Method"] == "PAY-1"
    assert index["SKU1"]["Original Payment Method"] == "PAY-1"
    assert index["ORD2"]["Setting Certificate No"] == "SETCERT-2"


def test_first_row_wins_when_two_rows_share_a_key():
    csv_text = (
        "Order Id,Original Payment Method\n"
        "DUP,FIRST\n"
        "DUP,SECOND\n"
    )

    index = jobsheet.parse_jobsheet(csv_text.encode())

    assert index["DUP"]["Original Payment Method"] == "FIRST"


def test_missing_key_column_in_csv_is_ignored_not_an_error():
    csv_text = "Setting SKU,Original Payment Method\nSKU9,PAY-9\n"

    index = jobsheet.parse_jobsheet(csv_text.encode())

    assert index["SKU9"]["Original Payment Method"] == "PAY-9"


def test_blank_key_value_is_not_indexed():
    csv_text = "Order Id,Setting SKU,Original Payment Method\n,SKU5,PAY-5\n"

    index = jobsheet.parse_jobsheet(csv_text.encode())

    assert "" not in index
    assert index["SKU5"]["Original Payment Method"] == "PAY-5"
