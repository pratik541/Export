from types import SimpleNamespace

import decoding


def _symbol(data: str):
    return SimpleNamespace(data=data.encode("utf-8"))


def test_decode_barcodes_returns_none_and_empty_when_nothing_found():
    def fake_decode(_image):
        return []

    result = decoding.decode_barcodes("image1", decode_func=fake_decode)
    assert result == {"barcode_value": None, "qr_values": []}


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
