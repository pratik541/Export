"""Scan-page tests: result card, inline Fix, and Scan-next reset, driven through
a harness that renders page_scan.render(). The camera component itself cannot be
driven headlessly, so these inject items into session state (same technique as
tests/test_app.py) and assert on the rendered result/controls."""
import cv2
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

import db

HARNESS = "tests/harness_scan.py"


@pytest.fixture(autouse=True)
def _disable_db(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)


def _png_bytes():
    img = np.full((40, 120, 3), 200, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _item(item_id=1, ocr_result=None):
    png = _png_bytes()
    return {"id": item_id, "source": "camera", "filename": f"scan{item_id}.png",
            "original_bytes": png, "cropped_bytes": png, "crop_box": None,
            "crop_method": "barcode", "auto_cropped": True, "ocr_result": ocr_result}


_OK = {"filename": "s.png", "accepted": True, "needs_review": False,
       "igi_report_no": "809614206", "report_type": "CVD", "shape": "EMERALD",
       "carat": "3.01", "color": "E", "clarity": "VS1"}


def _seed(at, item):
    at.session_state["gallery_items"] = [item]
    at.session_state["seen_hashes"] = {"x"}
    at.session_state["next_id"] = 2


def test_scan_page_boots_clean_with_no_items():
    at = AppTest.from_file(HARNESS, default_timeout=120)
    at.run()
    assert not at.exception


def test_result_card_shows_six_fields_for_accepted_item():
    at = AppTest.from_file(HARNESS, default_timeout=120)
    at.run()
    _seed(at, _item(1, dict(_OK)))
    at.run()
    assert not at.exception
    md = " ".join(m.value for m in at.markdown)
    for label in ("IGI no.", "Report", "Shape", "Carat", "Color", "Clarity"):
        assert label in md
    assert "809614206" in md


def test_fix_expander_absent_for_ok_present_for_review():
    at = AppTest.from_file(HARNESS, default_timeout=120)
    at.run()
    _seed(at, _item(1, dict(_OK)))
    at.run()
    assert not any((ti.key or "").startswith("fix_1_") for ti in at.text_input)
    review = dict(_OK); review["needs_review"] = True
    _seed(at, _item(1, review))
    at.run()
    assert any((ti.key or "").startswith("fix_1_") for ti in at.text_input)


def test_save_correction_writes_fields_back():
    at = AppTest.from_file(HARNESS, default_timeout=120)
    at.run()
    review = {"filename": "s.png", "accepted": True, "needs_review": True,
              "igi_report_no": "", "report_type": "", "shape": "", "carat": "",
              "color": "", "clarity": ""}
    _seed(at, _item(1, review))
    at.run()
    at.text_input(key="fix_1_igi_report_no").set_value("809614206").run()
    at.button(key="savefix_1").click().run()
    assert not at.exception
    saved = at.session_state["gallery_items"][0]["ocr_result"]
    assert saved["igi_report_no"] == "809614206"
    assert saved["needs_review"] is False


def test_scan_next_resets_camera_key():
    at = AppTest.from_file(HARNESS, default_timeout=120)
    at.run()
    _seed(at, _item(1, dict(_OK)))
    at.run()
    before = at.session_state["camera_gen"]
    at.button(key="scan_next").click().run()
    assert at.session_state["camera_gen"] == before + 1
