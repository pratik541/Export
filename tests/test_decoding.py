from types import SimpleNamespace

import decoding


def _symbol(data: str):
    return SimpleNamespace(data=data.encode("utf-8"),
                           rect=SimpleNamespace(left=0, top=0, width=0, height=0))


def test_decode_barcodes_returns_none_and_empty_when_nothing_found():
    def fake_decode(_image):
        return []

    result = decoding.decode_barcodes("image1", decode_func=fake_decode)
    assert result == {"barcode_value": None, "qr_values": [], "barcode_box": None}


def test_decode_barcodes_picks_up_numeric_barcode_value():
    def fake_decode(image):
        return [_symbol("809614206")] if image == "original" else []

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
    assert result["qr_values"] == []


def test_decode_barcodes_separates_non_numeric_qr_values():
    def fake_decode(image):
        if image == "original":
            return [_symbol("809614206"), _symbol("https://cert.igi.org/809614206")]
        return []

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
    assert result["qr_values"] == ["https://cert.igi.org/809614206"]


def test_decode_barcodes_dedupes_across_multiple_image_variants():
    def fake_decode(_image):
        return [_symbol("809614206")]

    result = decoding.decode_barcodes("original", "preprocessed", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"


def test_decode_barcodes_skips_none_images():
    def fake_decode(image):
        return [_symbol("809614206")] if image == "original" else []

    result = decoding.decode_barcodes("original", None, decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"


def _symbol_with_rect(data: str, rect):
    # pyzbar symbols expose .data (bytes) and .rect (left, top, width, height).
    return SimpleNamespace(data=data.encode("utf-8"), rect=rect)


def test_decode_barcodes_returns_barcode_box_for_numeric_value():
    rect = SimpleNamespace(left=269, top=792, width=294, height=32)

    def fake_decode(image):
        return [_symbol_with_rect("809614206", rect)]

    result = decoding.decode_barcodes("original", decode_func=fake_decode)
    assert result["barcode_value"] == "809614206"
    assert result["barcode_box"] == (269, 792, 294, 32)


def test_decode_barcodes_barcode_box_is_none_when_no_numeric_value():
    rect = SimpleNamespace(left=1, top=2, width=3, height=4)

    def fake_decode(image):
        return [_symbol_with_rect("https://cert.example/x", rect)]

    result = decoding.decode_barcodes("original", decode_func=fake_decode)
    assert result["barcode_value"] is None
    assert result["barcode_box"] is None
    assert result["qr_values"] == ["https://cert.example/x"]
