import cv2
import numpy as np

from ocr import pipeline


def _encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def _synthetic_image_bytes():
    rng = np.random.default_rng(0)
    image = rng.integers(0, 256, size=(150, 250, 3), dtype=np.uint8)
    return _encode_png(image)


def test_process_image_returns_rejected_for_corrupt_bytes():
    result = pipeline.process_image(b"not an image", "bad.jpg")
    assert result["accepted"] is False
    assert result["filename"] == "bad.jpg"
    assert "could not read" in result["reason"].lower()


def test_process_image_returns_rejected_when_quality_gate_fails(monkeypatch):
    monkeypatch.setattr(
        pipeline.quality, "assess_quality", lambda image, ocr_func: (False, "Image too blurry — please retake.")
    )
    result = pipeline.process_image(_synthetic_image_bytes(), "blurry.jpg")
    assert result["accepted"] is False
    assert result["reason"] == "Image too blurry — please retake."


def test_process_image_runs_ocr_on_the_original_color_image_not_the_preprocessed_one(monkeypatch):
    # PaddleOCR's detection model expects a natural 3-channel image and
    # crashes outright on our single-channel thresholded preprocessing
    # output -- ocr.run_ocr must always be called with the original image.
    monkeypatch.setattr(pipeline.quality, "assess_quality", lambda image, ocr_func: (True, None))
    monkeypatch.setattr(
        pipeline.decoding, "decode_barcodes",
        lambda *images, **kwargs: {"barcode_value": None, "qr_values": []},
    )
    captured = {}

    def fake_run_ocr(image):
        captured["ndim"] = image.ndim
        return ""

    monkeypatch.setattr(pipeline.ocr, "run_ocr", fake_run_ocr)

    pipeline.process_image(_synthetic_image_bytes(), "tag1.jpg")

    assert captured["ndim"] == 3


def test_process_image_builds_full_row_on_success(monkeypatch):
    monkeypatch.setattr(pipeline.quality, "assess_quality", lambda image, ocr_func: (True, None))
    monkeypatch.setattr(
        pipeline.ocr, "run_ocr",
        lambda image: "IGI CERT - 809614206\nREPORT\nCVD\n3.01\nE VS1\nEMERALD",
    )
    monkeypatch.setattr(
        pipeline.decoding, "decode_barcodes",
        lambda *images, **kwargs: {"barcode_value": "809614206", "qr_values": []},
    )

    result = pipeline.process_image(_synthetic_image_bytes(), "tag1.jpg")

    assert result["accepted"] is True
    assert result["filename"] == "tag1.jpg"
    assert result["igi_report_no"] == "809614206"
    assert result["report_type"] == "CVD"
    assert result["carat"] == "3.01"
    assert result["color"] == "E"
    assert result["clarity"] == "VS1"
    assert result["shape"] == "EMERALD"
    assert result["needs_review"] is False
    assert "IGI CERT" in result["raw_ocr_text"]
