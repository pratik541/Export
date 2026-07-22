import cv2
import numpy as np

import capture


def _png_bytes(image):
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


def _image_bytes():
    rng = np.random.default_rng(0)
    return _png_bytes(rng.integers(0, 256, size=(200, 300, 3), dtype=np.uint8))


def test_build_item_raises_on_undecodable_bytes():
    try:
        capture.build_item(b"not an image", "bad.jpg", "upload", 1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_item_auto_crops_when_barcode_box_present(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": "809614206", "qr_values": [], "barcode_box": (50, 40, 120, 20)},
    )
    item = capture.build_item(_image_bytes(), "tag.jpg", "camera", 7)
    assert item["id"] == 7
    assert item["source"] == "camera"
    assert item["filename"] == "tag.jpg"
    assert item["auto_cropped"] is True
    assert item["crop_box"] is not None
    assert item["cropped_bytes"] != item["original_bytes"]
    assert item["ocr_result"] is None


def test_build_item_keeps_full_image_when_no_barcode_box(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": None, "qr_values": [], "barcode_box": None},
    )
    data = _image_bytes()
    item = capture.build_item(data, "tag.jpg", "upload", 3)
    assert item["auto_cropped"] is False
    assert item["crop_box"] is None
    assert item["cropped_bytes"] == data
    assert item["ocr_result"] is None


def test_build_item_falls_back_to_full_image_for_degenerate_barcode_box(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": "817630270", "qr_values": [], "barcode_box": (451, 720, 0, 26)},
    )
    data = _image_bytes()
    item = capture.build_item(data, "tag.jpg", "upload", 5)
    assert item["auto_cropped"] is False
    assert item["crop_box"] is None
    assert item["cropped_bytes"] == data
