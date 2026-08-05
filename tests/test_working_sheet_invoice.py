import pytest

from working_sheet import invoice

_SAMPLE_TEXT_WITH_RODTEP_DISCLAIMED = """
Exporter Invoice No TST001/26-27 EXPORTER'S REFERENCE
Invoice Dt : 01-01-26 BIN NO. FAKE1234
This Export is against Letter of Undertaking & without payment of IGST
ORIGIN OF GOODS : 27,DISTRICT OF ORIGIN OF GOODS : 483 SQC-KGS / FTA CODE-NCPTI-
RITC (HSN) Code Description of Goods Weight Rate Amount
12345678 [01] TEST GOLD JEWELLERY
Item KT QTY
RING 18KT 1 Pcs
Total 1 Pcs
Details Of Studding 18KT Gross Wt Gms. US $ / GM US $
50.000
Net Wt GMS.
45.000 12.00 540.00
Wastage 2.80 %
Studd Type Pcs Wt (Cts) Total US $
LG Diamonds 10 0.50 60.00 Cost of Metal 540.00
Total 10 0.50 60.00 Cost 600.00
87654321 [02] TEST SILVER JEWELLERY
Item KT QTY
NECKLACE 925F 1 Pcs
Total 1 Pcs
Details Of Studding 925F Gross Wt Gms. US $ / GM US $
20.000
Net Wt GMS.
18.000 5.00 90.00
Studd Type Pcs Wt (Cts) Total US $
LG Diamonds 5 0.20 10.00 Cost of Metal 90.00
Total 5 0.20 10.00 Cost 100.00
Declaration: WE INTEND TO NOT CLAIM REWARDS UNDER THE RoDTEP SCHEME.
"""


def test_parse_invoice_extracts_shipment_level_fields(monkeypatch):
    monkeypatch.setattr(invoice, "extract_text", lambda b: _SAMPLE_TEXT_WITH_RODTEP_DISCLAIMED)

    result = invoice.parse_invoice(b"unused")

    assert result["invoice_no"] == "TST001/26-27"
    assert result["invoice_date"] == "01-01-26"
    assert result["state_code"] == "27"
    assert result["district_code"] == "483"
    assert result["fta_code"] == "NCPTI"
    assert result["igst_status"] == "LUT"
    assert result["rodtep"] == "NO"


def test_parse_invoice_extracts_per_category_cross_check_data(monkeypatch):
    monkeypatch.setattr(invoice, "extract_text", lambda b: _SAMPLE_TEXT_WITH_RODTEP_DISCLAIMED)

    result = invoice.parse_invoice(b"unused")

    assert result["categories"] == [
        {"number": 1, "ritc": "12345678", "cost": 600.0, "gross_wt": 50.0},
        {"number": 2, "ritc": "87654321", "cost": 100.0, "gross_wt": 20.0},
    ]


_SAMPLE_TEXT_WITH_STONELESS_CATEGORY_AND_RATE_REFERENCE_LINE = """
Exporter Invoice No TST002/26-27 EXPORTER'S REFERENCE
Invoice Dt : 01-01-26 BIN NO. FAKE1234
This Export is against Letter of Undertaking & without payment of IGST
ORIGIN OF GOODS : 27,DISTRICT OF ORIGIN OF GOODS : 483 SQC-KGS / FTA CODE-NCPTI-
RITC (HSN) Code Description of Goods Weight Rate Amount
11111111 [01] TEST GOLD MOUNTING (NO STONES)
Item KT QTY
RING 14KT 1 Pcs
Total 1 Pcs
Details Of Studding 14KT Gross Wt Gms. US $ / GM US $
4.510
Net Wt GMS.
4.510 76.28 344.02
Wastage 0.40 %
0.018 76.28 1.37
Studd Type Pcs Wt (Cts) Total US $
Cost of Metal 345.39
7.84 % Mfg Cost 27.08
Cost of Studding 0.00
Cost 372.47
22222222 [02] TEST GOLD SEMI MOUNTING WITH RATE REFERENCE LINE
Item KT QTY
RING 14KT 2 Pcs
Total 2 Pcs
Details Of Studding 14KT Gross Wt Gms. US $ / GM US $
DIL -GOLD-RATE-I NO OX26100MUM780- 4063.014000 FOR GOLD -Dt.28/07/2026 9.260
Net Wt GMS.
8.894 76.28 678.44
Wastage 2.80 %
0.249 76.28 18.99
Studd Type Pcs Wt (Cts) Total US $
LG Diamonds 44 1.83 70.42 Cost of Metal 697.43
7.96 % Mfg Cost 61.15
Cost of Studding 70.42
Total 44 1.83 70.42 Cost 829.00
33333333 [03] TEST THIRD CATEGORY
Item KT QTY
RING 14KT 1 Pcs
Total 1 Pcs
Details Of Studding 14KT Gross Wt Gms. US $ / GM US $
3.000
Net Wt GMS.
2.800 76.28 213.58
Studd Type Pcs Wt (Cts) Total US $
LG Diamonds 5 0.10 20.00 Cost of Metal 213.58
Total 5 0.10 20.00 Cost 250.00
"""


def test_parse_invoice_leaves_cost_none_for_a_category_with_no_stones_and_does_not_shift_the_rest(monkeypatch):
    monkeypatch.setattr(
        invoice, "extract_text",
        lambda b: _SAMPLE_TEXT_WITH_STONELESS_CATEGORY_AND_RATE_REFERENCE_LINE,
    )

    result = invoice.parse_invoice(b"unused")

    assert result["categories"][0] == {"number": 1, "ritc": "11111111", "cost": None, "gross_wt": 4.510}
    assert result["categories"][1]["cost"] == 829.00
    assert result["categories"][2]["cost"] == 250.00


def test_parse_invoice_extracts_gross_weight_past_a_rate_reference_line(monkeypatch):
    monkeypatch.setattr(
        invoice, "extract_text",
        lambda b: _SAMPLE_TEXT_WITH_STONELESS_CATEGORY_AND_RATE_REFERENCE_LINE,
    )

    result = invoice.parse_invoice(b"unused")

    assert result["categories"][1]["gross_wt"] == 9.260
    assert result["categories"][2]["gross_wt"] == 3.000


def test_parse_invoice_defaults_rodtep_to_yes_when_not_disclaimed(monkeypatch):
    text_without_disclaimer = _SAMPLE_TEXT_WITH_RODTEP_DISCLAIMED.replace(
        "Declaration: WE INTEND TO NOT CLAIM REWARDS UNDER THE RoDTEP SCHEME.", ""
    )
    monkeypatch.setattr(invoice, "extract_text", lambda b: text_without_disclaimer)

    result = invoice.parse_invoice(b"unused")

    assert result["rodtep"] == "YES"
