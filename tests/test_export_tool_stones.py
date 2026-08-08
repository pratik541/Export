import pytest
from export_tool import stones


def test_classify_position_cert_present_is_always_center():
    assert stones.classify_position("CERT1", 5) == "center"
    assert stones.classify_position("CERT1", None) == "center"


def test_classify_position_no_cert_single_stone_is_center():
    assert stones.classify_position(None, 1) == "center"
    assert stones.classify_position(None, None) == "center"


def test_classify_position_no_cert_multiple_stones_is_side():
    assert stones.classify_position(None, 2) == "side"


def _stone(**overrides):
    base = {
        "position": "side", "label": "LG Diamond", "shape": "RD", "color": "FG",
        "clarity": "VS", "lab": "IGI", "cert": None, "cts": 0.1, "pcs": 1, "val": 10.0,
    }
    base.update(overrides)
    return base


def test_aggregate_sums_center_stones_sharing_a_cert():
    groups = stones.aggregate([
        _stone(position="center", cert="CERT1", cts=0.2, pcs=1, val=50.0),
        _stone(position="center", cert="CERT1", cts=0.1, pcs=1, val=20.0),
    ])

    assert len(groups) == 1
    assert groups[0]["cts"] == pytest.approx(0.3)
    assert groups[0]["pcs"] == 2
    assert groups[0]["val"] == 70.0


def test_aggregate_keeps_center_stones_without_a_cert_separate():
    groups = stones.aggregate([
        _stone(position="center", cert=None, shape="RD"),
        _stone(position="center", cert=None, shape="RD"),
    ])

    assert len(groups) == 2


def test_aggregate_sums_side_stones_by_shape_and_nulls_disagreeing_color():
    groups = stones.aggregate([
        _stone(position="side", shape="RD", color="FG", clarity="VS", cts=0.1, pcs=10, val=20.0),
        _stone(position="side", shape="RD", color="H", clarity="VS", cts=0.2, pcs=5, val=15.0),
    ])

    assert len(groups) == 1
    assert groups[0]["cts"] == pytest.approx(0.3)
    assert groups[0]["pcs"] == 15
    assert groups[0]["val"] == 35.0
    assert groups[0]["color"] is None


def test_aggregate_promotes_first_group_to_center_when_every_stone_is_side():
    groups = stones.aggregate([_stone(position="side", shape="RD"), _stone(position="side", shape="EM")])

    assert groups[0]["position"] == "center"


def test_aggregate_orders_center_groups_before_side_groups():
    groups = stones.aggregate([
        _stone(position="side", shape="RD"),
        _stone(position="center", cert="CERT1"),
    ])

    assert groups[0]["position"] == "center"
    assert groups[1]["position"] == "side"
