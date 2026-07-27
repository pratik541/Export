from pathlib import Path

import cv2
import numpy as np

import capture
import decoding

FIXTURES = Path(__file__).parent / "fixtures"


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


def test_build_item_uses_guide_box_crop_for_camera_without_barcode(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": None, "qr_values": [], "barcode_box": None},
    )
    data = _image_bytes()
    item = capture.build_item(data, "cam.jpg", "camera", 9)
    assert item["crop_method"] == "guide_box"
    assert item["auto_cropped"] is True
    assert item["cropped_bytes"] != data      # a crop happened
    assert item["crop_box"] is None           # box coords only tracked for barcode crop


def test_build_item_upload_without_barcode_stays_full_image(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": None, "qr_values": [], "barcode_box": None},
    )
    data = _image_bytes()
    item = capture.build_item(data, "up.jpg", "upload", 10)
    assert item["crop_method"] is None
    assert item["auto_cropped"] is False
    assert item["cropped_bytes"] == data


def test_build_item_barcode_crop_sets_crop_method_barcode(monkeypatch):
    monkeypatch.setattr(
        capture.decoding, "decode_barcodes",
        lambda *a, **k: {"barcode_value": "809614206", "qr_values": [], "barcode_box": (50, 40, 120, 20)},
    )
    item = capture.build_item(_image_bytes(), "cam.jpg", "camera", 11)
    assert item["crop_method"] == "barcode"
    assert item["auto_cropped"] is True
    assert item["crop_box"] is not None


def _fixture_with_usable_barcode():
    data = (FIXTURES / "sample_tag.jpeg").read_bytes()
    import numpy as np, cv2
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    box = decoding.decode_barcodes(img).get("barcode_box")
    assert capture._is_usable_box(box), "precondition: sample_tag must decode a usable barcode"
    return data


def test_force_guide_box_crops_to_box_even_when_barcode_present():
    data = _fixture_with_usable_barcode()
    item = capture.build_item(data, "sample_tag.jpeg", "camera", 1, force_guide_box=True)
    assert item["crop_method"] == "guide_box"   # NOT "barcode"


def test_without_force_guide_box_barcode_crop_still_used():
    data = _fixture_with_usable_barcode()
    item = capture.build_item(data, "sample_tag.jpeg", "camera", 1)
    assert item["crop_method"] == "barcode"      # default behavior preserved
