from io import BytesIO

import openpyxl
import pytest

from export_tool import packing_list


def _write(cells):
    wb = openpyxl.Workbook()
    ws = wb.active
    for (row, col), value in cells.items():
        ws[f"{col}{row}"] = value
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_TWO_ITEM_CELLS = {
    (1, "A"): "Sr No", (1, "B"): "Style No.", (1, "C"): "Category", (1, "D"): "KT",
    (1, "E"): "Qty", (1, "F"): "Gross Wt in gms", (1, "G"): "Total Metal wt. gms",
    (1, "H"): "Metal Value", (1, "I"): "Lab", (1, "J"): "Certificate No",
    (1, "K"): "Studding Type", (1, "L"): "Shape/Color Clarity", (1, "M"): "Stn Pcs",
    (1, "N"): "Stn Cts", (1, "O"): "Value $", (1, "P"): "Making Value",
    # Item 1: RING, one center stone (has cert) + one side stone (no cert)
    (2, "A"): 1, (2, "B"): "STYLE1", (2, "C"): "RING", (2, "D"): "18KT WG",
    (2, "E"): 1, (2, "F"): 5.0, (2, "G"): 4.5, (2, "H"): 200.0,
    (2, "I"): "IGI", (2, "J"): "CERT001", (2, "K"): "LG Diamond",
    (2, "L"): "RD-FG-VS", (2, "M"): 10, (2, "N"): 0.3, (2, "O"): 50.0, (2, "P"): 30.0,
    (3, "L"): "RD-H-VS", (3, "M"): 5, (3, "N"): 0.1, (3, "O"): 10.0,
    # Item 2: BRACELET, single stone no cert (single-stone rule -> center)
    (4, "A"): 2, (4, "B"): "STYLE2", (4, "C"): "BRACELET", (4, "D"): "14KT RG",
    (4, "E"): 1, (4, "F"): 3.0, (4, "G"): 2.8, (4, "H"): 150.0,
    (4, "K"): "LG Diamond-CVD", (4, "L"): "EM-D-VVS1", (4, "M"): 1, (4, "N"): 0.5,
    (4, "O"): 80.0, (4, "P"): 20.0,
}


def test_parses_items_with_a_stone_continuation_line():
    items, warnings = packing_list.parse_packing_list(_write(_TWO_ITEM_CELLS))

    assert warnings == []
    assert len(items) == 2

    item1 = items[0]
    assert item1["sr"] == 1
    assert item1["sn"] == "STYLE1"
    assert item1["cat"] == "RING"
    assert item1["kt"] == "18KT WG"
    assert item1["qty"] == 1
    assert item1["gw"] == 5.0
    assert item1["tmw"] == 4.5
    assert item1["mv"] == 200.0
    assert item1["making"] == 30.0
    assert item1["cert"] == "CERT001"
    assert len(item1["stones"]) == 2
    assert item1["stones"][0]["position"] == "center"
    assert item1["stones"][0]["cert"] == "CERT001"
    assert item1["stones"][1]["position"] == "side"
    assert item1["stones"][1]["cert"] is None

    item2 = items[1]
    assert item2["sn"] == "STYLE2"
    assert len(item2["stones"]) == 1
    assert item2["stones"][0]["position"] == "center"
    assert item2["stones"][0]["pcs"] == 1


def test_chain_category_is_merged_into_the_preceding_item():
    cells = dict(_TWO_ITEM_CELLS)
    cells[(5, "A")] = 3
    cells[(5, "B")] = "CHAINX"
    cells[(5, "C")] = "CHAIN"
    cells[(5, "F")] = 1.0
    cells[(5, "G")] = 0.9
    cells[(5, "H")] = 10.0
    cells[(5, "P")] = 2.0

    items, _ = packing_list.parse_packing_list(_write(cells))

    assert len(items) == 2
    item2 = items[1]
    assert item2["sn"] == "STYLE2"
    assert item2["gw"] == 3.0 + 1.0
    assert item2["tmw"] == 2.8 + 0.9
    assert item2["mv"] == 150.0 + 10.0
    assert item2["making"] == 20.0 + 2.0


def test_category_header_and_total_rows_do_not_produce_spurious_items():
    cells = {key: value for key, value in _TWO_ITEM_CELLS.items() if key[0] in (1, 2)}
    cells[(3, "A")] = "[02] TEST CATEGORY BLOCK"
    cells[(4, "A")] = "Total:"
    cells[(4, "F")] = 5.0  # a subtotal value must not be read as an item's Gross Wt
    cells[(5, "A")] = 2
    cells[(5, "B")] = "STYLE2"
    cells[(5, "C")] = "BRACELET"
    cells[(5, "D")] = "14KT RG"
    cells[(5, "E")] = 1
    cells[(5, "F")] = 3.0
    cells[(5, "G")] = 2.8
    cells[(5, "H")] = 150.0
    cells[(5, "K")] = "LG Diamond-CVD"
    cells[(5, "L")] = "EM-D-VVS1"
    cells[(5, "M")] = 1
    cells[(5, "N")] = 0.5
    cells[(5, "O")] = 80.0
    cells[(5, "P")] = 20.0

    items, _ = packing_list.parse_packing_list(_write(cells))

    assert len(items) == 2
    assert items[1]["sn"] == "STYLE2"
    assert items[1]["gw"] == 3.0


def test_missing_style_no_column_raises_parse_error():
    cells = dict(_TWO_ITEM_CELLS)
    del cells[(1, "B")]

    with pytest.raises(packing_list.PackingListParseError, match="Sr No / Style No"):
        packing_list.parse_packing_list(_write(cells))


def test_missing_optional_column_is_a_warning_not_an_error():
    cells = dict(_TWO_ITEM_CELLS)
    del cells[(1, "H")]

    items, warnings = packing_list.parse_packing_list(_write(cells))

    assert len(items) == 2
    assert any("Metal Value" in w for w in warnings)
    assert items[0]["mv"] is None


def test_no_header_row_raises_parse_error():
    with pytest.raises(packing_list.PackingListParseError, match="header row"):
        packing_list.parse_packing_list(_write({(1, "A"): "not a header"}))


def test_columns_resolved_by_label_survive_a_different_column_order():
    cells = {
        (1, "A"): "Sr No", (1, "B"): "Certificate No", (1, "C"): "Style No.",
        (1, "D"): "Category", (1, "E"): "KT", (1, "F"): "Qty",
        (1, "G"): "Gross Wt in gms", (1, "H"): "Total Metal wt. gms",
        (1, "I"): "Metal Value", (1, "J"): "Lab", (1, "K"): "Studding Type",
        (1, "L"): "Shape/Color Clarity", (1, "M"): "Stn Pcs", (1, "N"): "Stn Cts",
        (1, "O"): "Value $", (1, "P"): "Making Value",
        (2, "A"): 1, (2, "B"): "CERT001", (2, "C"): "STYLE1", (2, "D"): "RING",
        (2, "E"): "18KT WG", (2, "F"): 1, (2, "G"): 5.0, (2, "H"): 4.5, (2, "I"): 200.0,
        (2, "J"): "IGI", (2, "K"): "LG Diamond", (2, "L"): "RD-FG-VS",
        (2, "M"): 10, (2, "N"): 0.3, (2, "O"): 50.0, (2, "P"): 30.0,
    }

    items, warnings = packing_list.parse_packing_list(_write(cells))

    assert warnings == []
    assert len(items) == 1
    assert items[0]["sn"] == "STYLE1"
    assert items[0]["cert"] == "CERT001"
