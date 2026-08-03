"""Unit tests for the pure helpers in ui_common (no Streamlit runtime needed)."""
import imaging
import ui_common


def _item(ocr_result=None, crop_method="barcode"):
    return {"id": 1, "crop_method": crop_method, "ocr_result": ocr_result}


def test_item_status_not_scanned_when_no_result():
    assert ui_common.item_status(_item(None)).startswith("⏳ Not scanned")


def test_item_status_hints_recrop_when_not_cropped():
    assert "re-crop" in ui_common.item_status(_item(None, crop_method=None))


def test_item_status_failed_shows_reason():
    r = {"accepted": False, "reason": "blurry"}
    assert ui_common.item_status(_item(r)) == "❌ blurry"


def test_item_status_ok_vs_needs_review():
    assert ui_common.item_status(_item({"accepted": True, "needs_review": False})) == "✅ OK"
    assert ui_common.item_status(_item({"accepted": True, "needs_review": True})) == "⚠️ Needs review"


def test_guide_box_constants_match_documented_frontend_values():
    # The vendored component's CSS box (rear_camera/frontend/style.css) is
    # documented to use these exact fractions. Guard them so the visible box
    # stays equal to the crop region.
    assert imaging.GUIDE_BOX_WIDTH_FRAC == 0.78
    assert imaging.GUIDE_BOX_ASPECT == 2.0
    assert imaging.GUIDE_BOX_CENTER_Y_FRAC == 0.42


def test_guide_box_css_jewelry_has_jewelry_dimensions():
    assert "92%" in ui_common.guide_box_css("jewelry")


def test_guide_box_css_diamond_has_diamond_dimensions():
    assert "78%" in ui_common.guide_box_css("diamond")
