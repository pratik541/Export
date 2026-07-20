import cv2
import numpy as np

import decoding
import imaging
import ocr
import parsing
import quality


def _decode_image_bytes(image_bytes: bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def process_image(image_bytes: bytes, filename: str) -> dict:
    """Run the full extraction pipeline on one image's raw bytes."""
    image = _decode_image_bytes(image_bytes)
    if image is None:
        return {
            "filename": filename,
            "accepted": False,
            "reason": "Could not read image file — it may be corrupt.",
        }

    quality_ok, quality_reason = quality.assess_quality(image, ocr.run_ocr)
    if not quality_ok:
        return {"filename": filename, "accepted": False, "reason": quality_reason}

    preprocessed = imaging.preprocess(image)
    decoded = decoding.decode_barcodes(image, preprocessed)
    raw_text = ocr.run_ocr(preprocessed)
    fields = parsing.parse_fields(raw_text)
    validated = parsing.validate_fields(fields, decoded["barcode_value"])

    row = {
        "filename": filename,
        "accepted": True,
        "raw_ocr_text": raw_text,
    }
    row.update(validated)
    return row
