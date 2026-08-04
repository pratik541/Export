from working_sheet import builder

_CATEGORIES = [
    {
        "number": 1, "ritc": "12345678", "description": "CAT ONE DESC",
        "gross_wt": 50.0, "net_wt": 45.0, "stone_wt": 0.5, "fob_value": 600.0,
        "unit_price": 12.0, "standard_qty": 0.05,
    },
    {
        "number": 2, "ritc": "87654321", "description": "CAT TWO DESC",
        "gross_wt": 20.0, "net_wt": 18.0, "stone_wt": 0.2, "fob_value": 100.0,
        "unit_price": 5.0, "standard_qty": 0.02,
    },
]

_INVOICE = {
    "invoice_no": "TST001/26-27", "invoice_date": "01-01-26",
    "state_code": "27", "district_code": "483", "fta_code": "NCPTI",
    "igst_status": "LUT", "rodtep": "NO",
    "categories": [
        {"number": 1, "ritc": "12345678", "cost": 600.0, "gross_wt": 50.0},
        {"number": 2, "ritc": "87654321", "cost": 100.0, "gross_wt": 20.0},
    ],
}


def test_build_rows_maps_every_working_sheet_column():
    rows = builder.build_rows(_CATEGORIES, _INVOICE)

    assert len(rows) == 2
    assert list(rows[0].keys()) == builder.WORKING_SHEET_COLUMNS
    assert rows[0]["Invoice No."] == "TST001/26-27"
    assert rows[0]["Item No."] == 1
    assert rows[0]["RITC"] == "12345678"
    assert rows[0]["Item Description"] == "CAT ONE DESC"
    assert rows[0]["Qty."] == 50.0
    assert rows[0]["Unit of Qty"] == "GMS"
    assert rows[0]["Unit Price"] == 12.0
    assert rows[0]["Per"] == "1"
    assert rows[0]["PMV Unit Price"] == "0.00"
    assert rows[0]["Scheme Code"] == "00"
    assert rows[0]["End Use"] == "GNX100"
    assert rows[0]["IGST Payment Status"] == "LUT"
    assert rows[0]["State Code"] == "27"
    assert rows[0]["District Code"] == "483"
    assert rows[0]["Standard Qty"] == 0.05
    assert rows[0]["Standard Qty Unit"] == "KGS"
    assert rows[0]["FTA Code"] == "NCPTI"
    assert rows[0]["Accessory Status"] == "0"
    assert rows[0]["RoDTEP"] == "NO"
    assert rows[0]["Drawback Sr. No."] == ""
    assert rows[1]["Item No."] == 2


def test_cross_validate_returns_no_warnings_when_everything_matches():
    assert builder.cross_validate(_CATEGORIES, _INVOICE) == []


def test_cross_validate_flags_ritc_mismatch():
    invoice = {**_INVOICE, "categories": [
        {"number": 1, "ritc": "99999999", "cost": 600.0, "gross_wt": 50.0},
        _INVOICE["categories"][1],
    ]}

    warnings = builder.cross_validate(_CATEGORIES, invoice)

    assert len(warnings) == 1
    assert "[01]" in warnings[0] and "RITC" in warnings[0]


def test_cross_validate_flags_gross_weight_mismatch():
    invoice = {**_INVOICE, "categories": [
        {"number": 1, "ritc": "12345678", "cost": 600.0, "gross_wt": 999.0},
        _INVOICE["categories"][1],
    ]}

    warnings = builder.cross_validate(_CATEGORIES, invoice)

    assert len(warnings) == 1
    assert "[01]" in warnings[0] and "gross weight" in warnings[0].lower()


def test_cross_validate_flags_category_count_mismatch():
    invoice = {**_INVOICE, "categories": _INVOICE["categories"][:1]}

    warnings = builder.cross_validate(_CATEGORIES, invoice)

    assert any("count" in w.lower() for w in warnings)
