"""The nav entry (app.py) must boot cleanly and land on the Manage page by
default (Manage-only marker: the 'Upload tag photos' uploader label)."""
import pytest
from streamlit.testing.v1 import AppTest

import db


@pytest.fixture(autouse=True)
def _disable_db(monkeypatch):
    monkeypatch.setattr(db, "get_client", lambda: None)


def test_app_boots_into_manage_by_default():
    at = AppTest.from_file("app.py", default_timeout=180)
    at.run()
    assert not at.exception
    all_text = " ".join(m.value for m in at.markdown)
    labels = " ".join(getattr(el, "label", "") or "" for el in at.get("file_uploader"))
    assert "Upload tag photos" in (all_text + " " + labels)
