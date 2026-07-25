"""Unit tests for the pure helpers in ui_common (no Streamlit runtime needed)."""
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
