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
    (6, "A"): "Sr No", (6, "D"): "Style No.", (6, "F"): "Category",
    (6, "G"): "RITC", (6, "H"): "KT", (6, "J"): "Gross Wt in gms",
    (6, "K"): "Net Wt in gms", (6, "AA"): "Total Cts. Stone wt",
    (6, "AD"): "Total FOB Value $",
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


def test_multi_word_piece_names_are_parsed_correctly():
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(12, "E")] = "(  3 EAR RING (Pcs) / 2 NOSE PIN (Pcs) )"

    categories = packing_list.parse_packing_list(_write(cells))

    assert "EAR RING-03 PCS, NOSE PIN-02 PCS" in categories[1]["description"]


def test_bare_pendant_piece_becomes_chwithpd_when_header_says_chain_with_pendant():
    # Real-world case (JNE019 category [04]): the category header spells out
    # "...CHAIN WITH PENDANT...", but the piece breakdown itself just says
    # "PENDANT" -- in that category, a bare "PENDANT" piece means a
    # chain-with-pendant set, and should render as "CHWITHPD" in the
    # description (the header phrase itself is left untouched).
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(11, "A")] = (
        "[02] 10KTGOLD JEWELLERY STUDDED WITH LABORATORY GROWN DIAMOND "
        "WITH 10KT PLAIN GOLD CHAIN WITH PENDANT (MECHANIZED)"
    )
    cells[(12, "E")] = "(  2 PENDANT (Pcs) )"

    categories = packing_list.parse_packing_list(_write(cells))

    assert "CHAIN WITH PENDANT (MECH), CHWITHPD-02 PCS" in categories[1]["description"]
    assert "PENDANT-02 PCS" not in categories[1]["description"]


def test_bare_pendant_piece_is_left_alone_without_chain_with_pendant_in_header():
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(12, "E")] = "(  2 PENDANT (Pcs) )"

    categories = packing_list.parse_packing_list(_write(cells))

    assert "PENDANT-02 PCS" in categories[1]["description"]
    assert "CHWITHPD" not in categories[1]["description"]


def test_missing_subtotal_value_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    del cells[(10, "AA")]

    with pytest.raises(packing_list.PackingListParseError, match=r"\[01\]"):
        packing_list.parse_packing_list(_write(cells))


def test_zero_gross_weight_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(10, "J")] = 0

    with pytest.raises(packing_list.PackingListParseError, match=r"\[01\]"):
        packing_list.parse_packing_list(_write(cells))


def test_unparseable_piece_breakdown_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    cells[(8, "E")] = "not a valid breakdown string"

    with pytest.raises(packing_list.PackingListParseError, match=r"\[01\]"):
        packing_list.parse_packing_list(_write(cells))


def test_missing_ritc_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    del cells[(9, "G")]

    with pytest.raises(packing_list.PackingListParseError, match=r"\[01\]"):
        packing_list.parse_packing_list(_write(cells))


def test_parses_a_packing_list_whose_trailing_columns_are_shifted_left():
    # Real-world regression (JNE019): that export omitted a blank spacer
    # column present in the original reference file, shifting every column
    # from "Rate $ Per Cts" onward one position left -- "Total Cts. Stone wt"
    # landed at Z instead of AA, "Total FOB Value $" at AC instead of AD.
    # Column-position-hardcoded parsing raised IndexError on this file;
    # header-label-driven column resolution must handle it correctly.
    cells = {
        (2, "A"): "TEST EXPORTER PVT LTD",
        (3, "A"): "TST001/26-27",
        (6, "A"): "Sr No", (6, "D"): "Style No.", (6, "F"): "Category",
        (6, "G"): "RITC", (6, "H"): "KT", (6, "J"): "Gross Wt in gms",
        (6, "K"): "Net Wt in gms", (6, "Z"): "Total Cts. Stone wt",
        (6, "AC"): "Total FOB Value $",
        (7, "A"): "[01] TEST GOLD JEWELLERY STUDDED WITH LABORATORY GROWN DIAMOND (MECHANIZED)",
        (8, "A"): "Total:", (8, "B"): 1, (8, "C"): "Unit", (8, "E"): "(  1 RING (Pcs) )",
        (9, "A"): 1, (9, "D"): "STYLE1", (9, "F"): "RING", (9, "G"): "12345678", (9, "H"): "18KTY",
        (9, "J"): 50.0, (9, "K"): 45.0, (9, "Z"): 0.5, (9, "AC"): 600.0,
        (10, "J"): 50.0, (10, "K"): 45.0, (10, "Z"): 0.5, (10, "AC"): 600.0,
    }

    categories = packing_list.parse_packing_list(_write(cells))

    assert len(categories) == 1
    cat = categories[0]
    assert cat["stone_wt"] == 0.5
    assert cat["fob_value"] == 600.0
    assert cat["unit_price"] == 12.0


def test_missing_header_column_raises_parse_error():
    cells = dict(_TWO_CATEGORY_CELLS)
    del cells[(6, "AD")]

    with pytest.raises(packing_list.PackingListParseError, match="fob_value"):
        packing_list.parse_packing_list(_write(cells))
