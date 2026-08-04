"""Extraction pipeline for the IGI jewelry-report card: quality gate -> OCR ->
verbatim jewelry parse -> validate. Same OCR engine as the diamond pipeline, but
no barcode/QR decoding (the report number is read from the printed text)."""
import cv2
import numpy as np

import ocr
from . import parsing_jewelry
from . import quality


def _decode_image_bytes(image_bytes: bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def process_image(image_bytes: bytes, filename: str) -> dict:
    """Run the jewelry-card extraction pipeline on one image's raw bytes."""
    image = _decode_image_bytes(image_bytes)
    if image is None:
        return {"filename": filename, "accepted": False,
                "reason": "Could not read image file — it may be corrupt."}

    quality_ok, quality_reason = quality.assess_quality(image, ocr.run_ocr_jewelry)
    if not quality_ok:
        return {"filename": filename, "accepted": False, "reason": quality_reason}

    raw_text = ocr.run_ocr_jewelry(image)
    fields = parsing_jewelry.parse_jewelry(raw_text)
    validated = parsing_jewelry.validate_jewelry_fields(fields)

    row = {"filename": filename, "accepted": True, "raw_ocr_text": raw_text}
    row.update(validated)
    return row
