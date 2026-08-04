from io import BytesIO

import pandas as pd

import excel_export


def test_build_excel_bytes_roundtrips_dataframe_contents():
    df = pd.DataFrame({
        "filename": ["tag1.jpg", "tag2.jpg"],
        "igi_report_no": ["809614206", "123456789"],
        "carat": ["3.01", "1.25"],
        "needs_review": [False, True],
    })

    excel_bytes = excel_export.build_excel_bytes(df)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    roundtripped = pd.read_excel(BytesIO(excel_bytes))
    assert list(roundtripped["filename"]) == ["tag1.jpg", "tag2.jpg"]
    assert list(roundtripped["igi_report_no"]) == [809614206, 123456789]
    assert list(roundtripped["needs_review"]) == [False, True]


def test_build_excel_bytes_handles_empty_dataframe():
    df = pd.DataFrame(columns=["filename", "igi_report_no"])
    excel_bytes = excel_export.build_excel_bytes(df)
    roundtripped = pd.read_excel(BytesIO(excel_bytes))
    assert list(roundtripped.columns) == ["filename", "igi_report_no"]
    assert len(roundtripped) == 0


def test_build_working_sheet_bytes_roundtrips_dataframe_contents():
    df = pd.DataFrame({
        "Invoice No.": ["TST001/26-27"],
        "Item No.": [1],
        "RITC": ["12345678"],
        "Qty.": [50.0],
    })

    excel_bytes = excel_export.build_working_sheet_bytes(df)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    roundtripped = pd.read_excel(BytesIO(excel_bytes))
    assert list(roundtripped["Invoice No."]) == ["TST001/26-27"]
    assert list(roundtripped["RITC"]) == [12345678]
