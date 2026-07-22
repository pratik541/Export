import cv2
import numpy as np

import decoding
import imaging


def _decode_image_bytes(image_bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _is_usable_box(box):
    """A barcode box is only usable for auto-crop if it has real extent.
    pyzbar can return a degenerate box (e.g. width=0) on some real fixtures;
    cropping to that produces a useless sliver, so treat it like no box at all."""
    return box is not None and box[2] > 1 and box[3] > 1


def build_item(image_bytes: bytes, filename: str, source: str, item_id: int) -> dict:
    """Turn raw image bytes into a gallery item: decode, auto-crop to the label
    around the barcode when a usable box is found, and package the result. Does
    NOT run OCR (ocr_result starts None). Raises ValueError on undecodable bytes."""
    image = _decode_image_bytes(image_bytes)
    if image is None:
        raise ValueError("Could not read image file — it may be corrupt.")

    decoded = decoding.decode_barcodes(image)
    barcode_box = decoded.get("barcode_box")

    if _is_usable_box(barcode_box):
        crop_box = imaging.label_crop_box(image, barcode_box)
        cropped = imaging.crop_to_label(image, barcode_box)
        ok, buf = cv2.imencode(".jpg", cropped)
        cropped_bytes = buf.tobytes() if ok else image_bytes
        auto_cropped = ok
    else:
        crop_box = None
        cropped_bytes = image_bytes
        auto_cropped = False

    return {
        "id": item_id,
        "source": source,
        "filename": filename,
        "original_bytes": image_bytes,
        "cropped_bytes": cropped_bytes,
        "crop_box": crop_box if auto_cropped else None,
        "auto_cropped": auto_cropped,
        "ocr_result": None,
    }
