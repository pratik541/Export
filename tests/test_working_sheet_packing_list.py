from io import BytesIO

import openpyxl
import pytest

from working_sheet import packing_list


def _write(cells):
    """Builds a minimal .xlsx mimicking the Packing List export's structure.
    `cells` is {(row, col_letter): value} — col_letter matches the real
    file's lettering (A, D, E, F, G, H, I, J, K, N, O, Q, V, W, Z, AA, AC, AD)
    so the parser's column-index assumptions are exercised the same way
    they'd be against a real export."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for (row, col), value in cells.items():
        ws[f"{col}{row}"] = value
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_TWO_CATEGORY_CELLS = {
    (2, "A"): "TEST EXPORTER PVT LTD",
    (3, "A"): "TST001/26-27",
    (6, "A"): "Sr No", (6, "G"): "RITC",
    # Category 1
    (7, "A"): "[01] TEST GOLD JEWELLERY STUDDED WITH LABORATORY GROWN DIAMOND  (MECHANIZED)",
    (8, "A"): "Total:", (8, "B"): 1, (8, "C"): "Unit", (8, "E"): "(  1 RING (Pcs) )",
    (9, "A"): 1, (9, "D"): "STYLE1", (9, "F"): "RING", (9, "G"): "12345678", (9, "H"): "18KTY",
    (9, "I"): 1, (9, "J"): 50.0, (9, "K"): 45.0, (9, "V"): 10, (9, "W"): 0.5, (9, "AA"): 0.5,
    (9, "AD"): 600.0,
    (10, "I"): 1, (10, "J"): 50.0, (10, "K"): 45.0, (10, "V"): 10, (10, "W"): 0.5, (10, "AA"): 0.5,
    (10, "AD"): 600.0,
    # Category 2
    (11, "A"): "[02] TEST SILVER JEWELLERY STUDDED WITH LABORATORY GROWN DIAMOND (MECHANIZED)",
    (12, "A"): "Total:", (12, "B"): 1, (12, "C"): "Unit", (12, "E"): "(  1 NECKLACE (Pcs) )",
    (13, "A"): 2, (13, "D"): "STYLE2", (13, "F"): "NECKLACE", (13, "G"): "87654321", (13, "H"): "925FW",
    (13, "I"): 1, (13, "J"): 20.0, (13, "K"): 18.0, (13, "V"): 5, (13, "W"): 0.2, (13, "AA"): 0.2,
    (13, "AD"): 100.0,
    (14, "I"): 1, (14, "J"): 20.0, (14, "K"): 18.0, (14, "V"): 5, (14, "W"): 0.2, (14, "AA"): 0.2,
    (14, "AD"): 100.0,
    # Grand total
    (15, "D"): "Grand Total :", (15, "I"): 2, (15, "J"): 70.0, (15, "K"): 63.0,
}


def test_parses_two_categories_with_correct_derived_fields():
    categories = packing_list.parse_packing_list(_write(_TWO_CATEGORY_CELLS))

    assert len(categories) == 2

    cat1 = categories[0]
    assert cat1["number"] == 1
    assert cat1["ritc"] == "12345678"
    assert cat1["description"] == (
        "TEST GOLD JEWELLERY STUDDED WITH LGD (MECH), RING-01 PCS, "
        "NW-45.000 GMS, SW-0.50 CTS"
    )
    assert cat1["gross_wt"] == 50.0
    assert cat1["net_wt"] == 45.0
    assert cat1["stone_wt"] == 0.5
    assert cat1["fob_value"] == 600.0
    assert cat1["unit_price"] == 12.0
    assert cat1["standard_qty"] == 0.05

    cat2 = categories[1]
    assert cat2["number"] == 2
    assert cat2["ritc"] == "87654321"
    assert cat2["description"] == (
        "TEST SILVER JEWELLERY STUDDED WITH LGD (MECH), NECKLACE-01 PCS, "
        "NW-18.000 GMS, SW-0.20 CTS"
    )
    assert cat2["unit_price"] == 5.0
    assert cat2["standard_qty"] == 0.02


def test_multi_item_piece_breakdown_is_reformatted_in_order():
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(11, "A")] = "[02] TEST GOLD JEWELLERY STUDDED WITH LABORATORY GROWN DIAMOND (MECHANIZED)"
    cells[(12, "E")] = "(  14 RING (Pcs) / 2 BRACELET (Pcs) )"

    categories = packing_list.parse_packing_list(_write(cells))

    assert categories[1]["description"].startswith(
        "TEST GOLD JEWELLERY STUDDED WITH LGD (MECH), RING-14 PCS, BRACELET-02 PCS, "
    )


def test_category_with_no_subtotal_row_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    del cells[(10, "I")], cells[(10, "J")], cells[(10, "K")]
    del cells[(10, "V")], cells[(10, "W")], cells[(10, "AA")], cells[(10, "AD")]

    with pytest.raises(packing_list.PackingListParseError, match=r"\[01\]"):
        packing_list.parse_packing_list(_write(cells))
