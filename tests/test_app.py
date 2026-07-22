"""Smoke/regression tests for the Streamlit UI in app.py, using Streamlit's
AppTest harness (no browser needed).

These exist because app.py is UI glue with no other automated coverage, and a
real bug shipped through the headless boot check: the session-state key was
originally named "items", which shadows the dict-like `.items()` method on
Streamlit's session state, so `st.session_state.items` returned the *method*
and `len(...)` on it raised `TypeError` — but only once the gallery held an
item, which a plain boot check never exercises. These tests drive the app to
that state.
"""
import cv2
import numpy as np
from streamlit.testing.v1 import AppTest


def _png_bytes():
    img = np.full((40, 120, 3), 200, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _fake_item(item_id=1, ocr_result=None):
    png = _png_bytes()
    return {
        "id": item_id, "source": "upload", "filename": f"tag{item_id}.png",
        "original_bytes": png, "cropped_bytes": png, "crop_box": None,
        "auto_cropped": True, "ocr_result": ocr_result,
    }


def test_app_runs_clean_with_no_items():
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception


def test_app_renders_gallery_with_an_item_present():
    # Regression: this exercises the gallery-render loop that used to crash
    # with `TypeError: object of type 'method' has no len()`.
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    at.session_state["gallery_items"] = [_fake_item(1)]
    at.session_state["seen_hashes"] = {"seed"}
    at.session_state["next_id"] = 2
    at.run()
    assert not at.exception


def test_app_renders_results_table_for_an_ocrd_item():
    # An accepted OCR result should render the results table + export without error.
    ocr_result = {
        "filename": "tag1.png", "accepted": True, "needs_review": False,
        "igi_report_no": "809614206", "report_type": "CVD", "shape": "EMERALD",
        "carat": "3.01", "color": "E", "clarity": "VS1", "raw_ocr_text": "…",
    }
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    at.session_state["gallery_items"] = [_fake_item(1, ocr_result=ocr_result)]
    at.session_state["seen_hashes"] = {"seed"}
    at.session_state["next_id"] = 2
    at.run()
    assert not at.exception
