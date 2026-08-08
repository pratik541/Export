from export_tool import fantasy_file


def _item(**overrides):
    base = {
        "sr": 1, "sn": "STYLE1", "cat": "RING", "kt": "18KT WG",
        "qty": 1, "gw": 5.0, "tmw": 4.5, "mv": 200.0, "making": 30.0,
        "cert": None, "stones": [],
    }
    base.update(overrides)
    return base


def _stone(**overrides):
    base = {
        "position": "center", "label": "LG Diamond", "shape": "RD", "color": "FG",
        "clarity": "VS", "lab": "IGI", "cert": "CERT001", "cts": 0.3, "pcs": 10, "val": 50.0,
    }
    base.update(overrides)
    return base


def test_build_rows_maps_core_fields_from_item_and_jobsheet():
    item = _item(stones=[_stone()])
    jobsheet_index = {
        "STYLE1": {
            "Original Payment Method": "ORDER123",
            "Product Status": "STYLE1",
            "Setting Certificate No": "SETCERT1",
        }
    }

    rows, warnings = fantasy_file.build_rows([item], jobsheet_index)

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["LotName"] == "SETCERT1"
    assert row["Metal"] == "18KT WG"
    assert row["Order #"] == "ORDER123"
    assert row["Qty"] == 1
    assert row["Weight"] == 5.0
    assert row["ItemTypeID"] == 11
    assert row["C1:Item Name"] == "18KT WG"
    assert row["C1:Weight"] == 4.5
    assert row["C1: Total H.Cost"] == 200.0
    assert row["C2:Item Name"] == "Labor"
    assert row["C2: Total H.Cost"] == 30.0
    assert row["C3:Item Name"] == "Diamonds"
    assert row["C3:LotName"] == "CERT001"
    assert row["C3:Shape"] == "RD"
    assert row["C3: Stone Position"] == "C"


def test_build_rows_falls_back_to_master_style_jobsheet_lookup():
    item = _item(sn="STYLE1/2")
    jobsheet_index = {"STYLE1": {"Original Payment Method": "ORDER123"}}

    rows, _ = fantasy_file.build_rows([item], jobsheet_index)

    assert rows[0]["Order #"] == "ORDER123"


def test_build_rows_lot_name_falls_back_to_item_cert_then_style_no():
    rows, _ = fantasy_file.build_rows([_item(cert="ITEMCERT")], {})
    assert rows[0]["LotName"] == "ITEMCERT"

    rows2, _ = fantasy_file.build_rows([_item(sn="STYLE2", cert=None)], {})
    assert rows2[0]["LotName"] == "STYLE2"


def test_build_rows_excludes_side_stones_for_no_side_diamond_categories():
    item = _item(cat="BRACELET", stones=[
        _stone(position="center", cert="C1"),
        _stone(position="side", cert=None, shape="EM"),
    ])

    rows, _ = fantasy_file.build_rows([item], {})

    assert rows[0]["C3:Item Name"] == "Diamonds"
    assert rows[0]["C4:Item Name"] is None


def test_build_rows_warns_and_truncates_when_more_than_twenty_stone_groups():
    stones_list = [_stone(position="side", shape=f"SHAPE{i}", cert=None) for i in range(21)]
    item = _item(stones=stones_list)

    rows, warnings = fantasy_file.build_rows([item], {})

    assert any("truncated" in w for w in warnings)
    assert rows[0]["C22:Item Name"] is not None
