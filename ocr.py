import os
from pathlib import Path

# Works around a NotImplementedError crash in some PaddlePaddle CPU builds'
# oneDNN (MKL-DNN) backend ("ConvertPirAttribute2RuntimeAttribute not support
# [pir::ArrayAttribute<pir::DoubleAttribute>]"). Must be set before paddleocr
# is imported, since paddlex reads it once at import time.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

import cv2
from paddleocr import PaddleOCR

_MODELS_DIR = Path(__file__).parent / "models"

_reader = None


def get_reader() -> PaddleOCR:
    """Lazily create and cache the PaddleOCR reader -- constructing it loads
    model weights, so it must not happen at import time (every test would pay
    for it) or more than once.

    Model files are bundled in models/ and loaded from there via
    *_model_dir, not fetched at runtime: PaddleX's default behavior tries to
    resolve/download models from a remote hub (HuggingFace/ModelScope/AIStudio/
    BOS) on every fresh environment, which failed outright when deployed
    ("No model source is available for model `PP-OCRv6_tiny_det`") because
    that hosting environment's network couldn't reach any of them. Passing
    *_model_dir avoids that lookup entirely. *_model_name must still be given
    alongside it -- without it, PaddleX assumes a *different* default model
    name (the full "medium" model) and then rejects our tiny-model directory
    for not matching that assumed name.
    """
    global _reader
    if _reader is None:
        _reader = PaddleOCR(
            text_detection_model_name="PP-OCRv6_tiny_det",
            text_detection_model_dir=str(_MODELS_DIR / "PP-OCRv6_tiny_det"),
            text_recognition_model_name="PP-OCRv6_tiny_rec",
            text_recognition_model_dir=str(_MODELS_DIR / "PP-OCRv6_tiny_rec"),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _reader


def group_into_lines(detections, y_tolerance=15) -> str:
    """PaddleOCR returns one (quadrilateral box, text, score) detection per
    text fragment, not one continuous text block. Fragments whose vertical
    centers land within `y_tolerance` of each other are treated as the same
    printed line and joined left-to-right, so the result can be fed into the
    existing line-based parsing.parse_fields."""
    items = []
    for box, text, _score in detections:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        items.append((sum(ys) / len(ys), min(xs), text))
    items.sort(key=lambda item: item[0])

    lines = []
    current_line = []
    current_y = None
    for y, x, text in items:
        if current_y is None or abs(y - current_y) <= y_tolerance:
            current_line.append((x, text))
            current_y = y if current_y is None else (current_y + y) / 2
        else:
            lines.append(" ".join(t for _, t in sorted(current_line)))
            current_line, current_y = [(x, text)], y
    if current_line:
        lines.append(" ".join(t for _, t in sorted(current_line)))
    return "\n".join(lines)


def run_ocr(image) -> str:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    result = get_reader().predict(image)
    detections = zip(result[0]["rec_polys"], result[0]["rec_texts"], result[0]["rec_scores"])
    return group_into_lines(list(detections))
