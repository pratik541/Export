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


def build_item(image_bytes: bytes, filename: str, source: str, item_id: int,
               force_guide_box: bool = False, card_type: str = "diamond") -> dict:
    """Turn raw image bytes into a gallery item: decode, then crop for OCR.

    When force_guide_box is True (Scan page), always crop to the on-screen guide
    box (imaging.guide_box_crop, sized for card_type) and skip barcode detection
    — so the crop is identical shot-to-shot and matches the green box the user
    framed.

    Otherwise crop priority is: (1) usable barcode box -> label crop; (2) no
    usable box but source == "camera" -> guide-box region crop; (3) otherwise
    (e.g. uploads with no barcode) -> full image. Does NOT run OCR (ocr_result
    starts None). Raises ValueError on undecodable bytes."""
    image = _decode_image_bytes(image_bytes)
    if image is None:
        raise ValueError("Could not read image file — it may be corrupt.")

    crop_box = None
    if force_guide_box:
        ok, buf = cv2.imencode(".jpg", imaging.guide_box_crop(image, card_type))
        if ok:
            cropped_bytes, crop_method = buf.tobytes(), "guide_box"
        else:
            cropped_bytes, crop_method = image_bytes, None
    else:
        decoded = decoding.decode_barcodes(image)
        barcode_box = decoded.get("barcode_box")
        if _is_usable_box(barcode_box):
            crop_box = imaging.label_crop_box(image, barcode_box)
            ok, buf = cv2.imencode(".jpg", imaging.crop_to_label(image, barcode_box))
            if ok:
                cropped_bytes, crop_method = buf.tobytes(), "barcode"
            else:
                cropped_bytes, crop_method, crop_box = image_bytes, None, None
        elif source == "camera":
            ok, buf = cv2.imencode(".jpg", imaging.guide_box_crop(image, card_type))
            if ok:
                cropped_bytes, crop_method = buf.tobytes(), "guide_box"
            else:
                cropped_bytes, crop_method = image_bytes, None
        else:
            cropped_bytes, crop_method = image_bytes, None

    return {
        "id": item_id,
        "source": source,
        "filename": filename,
        "original_bytes": image_bytes,
        "cropped_bytes": cropped_bytes,
        "crop_box": crop_box,
        "crop_method": crop_method,
        "auto_cropped": crop_method is not None,
        "card_type": card_type,
        "ocr_result": None,
    }
