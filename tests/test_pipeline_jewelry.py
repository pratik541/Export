"""pipeline_jewelry orchestration test. OCR is monkeypatched to return crafted
card text, so this is deterministic and needs no real image/model."""
import cv2
import numpy as np

from ocr import pipeline_jewelry
from ocr import quality

_CARD_TEXT = "\n".join([
    "Report No. : 45J331632607",
    "Shape and Cut : (1) Oval Brilliant",
    "Est. Weight : 0.56 Carat",
    "Color : E - F",
    "Clarity : VS",
    "Comments : ... Style# AFDN352/9",
])


def _png_bytes():
    img = np.full((80, 240, 3), 210, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_process_image_returns_jewelry_fields(monkeypatch):
    # Force the quality gate to pass and OCR to return our crafted card text.
    monkeypatch.setattr(quality, "assess_quality", lambda img, fn: (True, None))
    monkeypatch.setattr(pipeline_jewelry.ocr, "run_ocr_jewelry", lambda img: _CARD_TEXT)
    r = pipeline_jewelry.process_image(_png_bytes(), "card.png")
    assert r["accepted"] is True
    assert r["report_no"] == "45J331632607"
    assert r["style_no"] == "AFDN352/9"
    assert r["needs_review"] is False


def test_process_image_rejects_unreadable_bytes():
    r = pipeline_jewelry.process_image(b"not an image", "x.png")
    assert r["accepted"] is False
