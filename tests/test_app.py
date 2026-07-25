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
import pytest
from streamlit.testing.v1 import AppTest

import db


@pytest.fixture(autouse=True)
def _disable_db(monkeypatch):
    """Force the Supabase store OFF for every app test, so results are
    deterministic and hermetic regardless of whether a local
    .streamlit/secrets.toml happens to exist — and so tests never make a real
    network call to a configured database. `get_client() -> None` disables
    is_enabled/save_scan/fetch_all together."""
    monkeypatch.setattr(db, "get_client", lambda: None)


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
        "crop_method": None, "auto_cropped": False, "ocr_result": ocr_result,
    }


def test_app_runs_clean_with_no_items():
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    assert not at.exception


def test_app_renders_gallery_with_an_item_present():
    # Regression: this exercises the gallery-render loop that used to crash
    # with `TypeError: object of type 'method' has no len()`.
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    at.session_state["gallery_items"] = [_fake_item(1)]
    at.session_state["seen_hashes"] = {"seed"}
    at.session_state["next_id"] = 2
    at.run()
    assert not at.exception


def test_app_emits_camera_positioning_guide_css():
    # The positioning-guide box is injected CSS targeting the keyed container's
    # `st-key-camera_guide` class. Assert it's actually emitted so the guide
    # can't silently vanish (visual alignment still needs manual browser check).
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    assert not at.exception
    all_markdown = " ".join(m.value for m in at.markdown)
    assert "st-key-camera_guide" in all_markdown


def test_app_renders_results_table_for_an_ocrd_item():
    # An accepted OCR result should render the results table + export without error.
    ocr_result = {
        "filename": "tag1.png", "accepted": True, "needs_review": False,
        "igi_report_no": "809614206", "report_type": "CVD", "shape": "EMERALD",
        "carat": "3.01", "color": "E", "clarity": "VS1", "raw_ocr_text": "…",
    }
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    at.session_state["gallery_items"] = [_fake_item(1, ocr_result=ocr_result)]
    at.session_state["seen_hashes"] = {"seed"}
    at.session_state["next_id"] = 2
    at.run()
    assert not at.exception


def test_app_renders_metrics_row_with_items_present():
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    at.session_state["gallery_items"] = [_fake_item(1), _fake_item(2)]
    at.session_state["seen_hashes"] = {"seed"}
    at.session_state["next_id"] = 3
    at.run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Total tags" in labels


def test_delete_keeps_hash_so_widget_cannot_readd():
    import hashlib
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    it1, it2 = _fake_item(1), _fake_item(2)
    # Give the two items distinct bytes so their md5 hashes differ.
    img1 = np.full((40, 120, 3), 200, dtype=np.uint8)
    img2 = np.full((40, 120, 3), 100, dtype=np.uint8)
    ok1, buf1 = cv2.imencode(".png", img1)
    ok2, buf2 = cv2.imencode(".png", img2)
    assert ok1 and ok2
    it1["original_bytes"] = it1["cropped_bytes"] = buf1.tobytes()
    it2["original_bytes"] = it2["cropped_bytes"] = buf2.tobytes()
    h1 = hashlib.md5(it1["original_bytes"]).hexdigest()
    h2 = hashlib.md5(it2["original_bytes"]).hexdigest()
    assert h1 != h2
    at.session_state["gallery_items"] = [it1, it2]
    at.session_state["seen_hashes"] = {h1, h2}
    at.session_state["next_id"] = 3
    at.run()
    at.button(key="del_1").click().run()
    assert not at.exception
    remaining = [it["id"] for it in at.session_state["gallery_items"]]
    assert remaining == [2]                     # item 1 removed
    assert h1 in at.session_state["seen_hashes"]  # its hash kept -> can't reappear


def test_app_hides_saved_records_when_db_disabled():
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    assert not at.exception
    all_md = " ".join(m.value for m in at.markdown)
    all_subheaders = " ".join(
        el.value for el in at.get("subheader")
    ) if at.get("subheader") else ""
    assert "Saved records" not in all_md and "Saved records" not in all_subheaders


_SAVED_ROW = [
    {"igi_report_no": "809614206", "report_type": "CVD", "shape": "EMERALD",
     "carat": "3.01", "color": "E", "clarity": "VS1", "needs_review": False,
     "source": "camera", "scanned_at": "2026-07-25T00:00:00+00:00"},
]


def test_saved_records_per_row_delete_calls_delete_one(monkeypatch):
    import db
    calls = []
    monkeypatch.setattr(db, "is_enabled", lambda: True)
    monkeypatch.setattr(db, "fetch_all", lambda: list(_SAVED_ROW))
    monkeypatch.setattr(db, "delete_all", lambda: True)
    monkeypatch.setattr(db, "delete_one", lambda igi: calls.append(igi) or True)
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    assert not at.exception
    all_sub = " ".join(el.value for el in at.get("subheader")) if at.get("subheader") else ""
    assert "Saved records" in all_sub          # section actually rendered
    at.button(key="del_saved_809614206").click().run()
    assert calls == ["809614206"]              # per-row delete really called db.delete_one


def test_delete_all_only_fires_when_DELETE_typed(monkeypatch):
    import db
    n = {"count": 0}
    monkeypatch.setattr(db, "is_enabled", lambda: True)
    monkeypatch.setattr(db, "fetch_all", lambda: list(_SAVED_ROW))
    monkeypatch.setattr(db, "delete_one", lambda igi: True)
    monkeypatch.setattr(db, "delete_all", lambda: (n.__setitem__("count", n["count"] + 1), True)[1])
    at = AppTest.from_file("tests/harness_manage.py", default_timeout=120)
    at.run()
    at.button(key="delete_all_saved").click().run()                    # reveal confirm box
    at.text_input(key="delete_all_confirm_text").set_value("nope").run()
    at.button(key="confirm_delete_all_btn").click().run()
    assert n["count"] == 0                                             # wrong text -> no delete
    at.text_input(key="delete_all_confirm_text").set_value("DELETE").run()
    at.button(key="confirm_delete_all_btn").click().run()
    assert n["count"] == 1                                             # correct text -> delete fires
    assert not at.exception
