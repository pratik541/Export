from pyzbar.pyzbar import decode as zbar_decode


def decode_barcodes(*images, decode_func=zbar_decode) -> dict:
    """Decode barcodes/QR codes from one or more image variants (e.g. the original
    and the preprocessed version — barcode decoding is sometimes better on
    non-thresholded images) and merge the results.

    Returns {"barcode_value": <first purely-numeric value or None>,
             "qr_values": [<every other decoded value, in first-seen order>],
             "barcode_box": (left, top, width, height) of the symbol that became
                            barcode_value, or None}."""
    numeric_values = []
    other_values = []
    barcode_box = None
    seen = set()

    for image in images:
        if image is None:
            continue
        for symbol in decode_func(image):
            value = symbol.data.decode("utf-8", errors="ignore").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            if value.isdigit():
                if not numeric_values:
                    rect = symbol.rect
                    barcode_box = (rect.left, rect.top, rect.width, rect.height)
                numeric_values.append(value)
            else:
                other_values.append(value)

    return {
        "barcode_value": numeric_values[0] if numeric_values else None,
        "qr_values": other_values,
        "barcode_box": barcode_box,
    }
