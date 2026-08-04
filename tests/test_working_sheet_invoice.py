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


def test_parse_invoice_defaults_rodtep_to_yes_when_not_disclaimed(monkeypatch):
    text_without_disclaimer = _SAMPLE_TEXT_WITH_RODTEP_DISCLAIMED.replace(
        "Declaration: WE INTEND TO NOT CLAIM REWARDS UNDER THE RoDTEP SCHEME.", ""
    )
    monkeypatch.setattr(invoice, "extract_text", lambda b: text_without_disclaimer)

    result = invoice.parse_invoice(b"unused")

    assert result["rodtep"] == "YES"
