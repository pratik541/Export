import cv2
import numpy as np


def preprocess(image: np.ndarray) -> np.ndarray:
    """Grayscale -> denoise -> adaptive threshold. Returns a binarized (0/255)
    single-channel uint8 image the same size as the input.

    Deliberately does not deskew: a whole-photo rotation estimate (e.g. via
    minAreaRect over every foreground pixel) locks onto whatever dominates the
    frame, and in a real phone photo that's background clutter (edges,
    shadows, smudges), not the tag text. On a real sample tag this rotated an
    otherwise-readable image into one Tesseract couldn't read at all."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    return cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15,
    )


# Auto-crop padding, as fractions of the barcode WIDTH (stable across photos;
# the barcode spans most of the label's width). The barcode sits at the label's
# upper-left with grading text to its right and below, so right/down are larger.
# STARTING VALUES — tune in Step 5 against real fixtures.
_PAD_LEFT_FRAC = 0.2
_PAD_RIGHT_FRAC = 1.3
_PAD_UP_FRAC = 0.3
_PAD_DOWN_FRAC = 1.2


def label_crop_box(image, barcode_box):
    """Compute the (left, top, right, bottom) crop rectangle for the label,
    clamped to the image bounds. Separated from crop_to_label so the geometry
    is directly testable."""
    left0, top0, width, height = barcode_box
    h, w = image.shape[:2]
    left = int(round(left0 - _PAD_LEFT_FRAC * width))
    right = int(round(left0 + width + _PAD_RIGHT_FRAC * width))
    top = int(round(top0 - _PAD_UP_FRAC * width))
    bottom = int(round(top0 + height + _PAD_DOWN_FRAC * width))
    left = max(0, min(left, w - 1))
    right = max(left + 1, min(right, w))
    top = max(0, min(top, h - 1))
    bottom = max(top + 1, min(bottom, h))
    return left, top, right, bottom


def crop_to_label(image, barcode_box):
    """Crop `image` to the label region anchored on the decoded barcode's
    position. Returns a copy so the caller can freely encode/modify it."""
    left, top, right, bottom = label_crop_box(image, barcode_box)
    return image[top:bottom, left:right].copy()


# Guide-box geometry. The on-screen camera guide box (CSS in app.py) AND this
# fallback center crop use the SAME relative numbers, so what the user frames in
# the box is what gets cropped. If you change these, change the guide-box CSS in
# app.py to match (width %, vertical center %, 2:1 aspect).
GUIDE_BOX_WIDTH_FRAC = 0.78       # box width as a fraction of image width
GUIDE_BOX_ASPECT = 2.0            # width : height
GUIDE_BOX_CENTER_Y_FRAC = 0.42    # box vertical center as a fraction of image height

# Jewelry-card guide box: bigger and closer to the card's shape so all labels
# (Report No. at top ... Style# at bottom) fit inside. MUST match the drawn box
# in rear_camera/frontend + ui_common.guide_box_css("jewelry"). Starting values.
JEWELRY_GUIDE_BOX_WIDTH_FRAC = 0.92
JEWELRY_GUIDE_BOX_ASPECT = 1.5
JEWELRY_GUIDE_BOX_CENTER_Y_FRAC = 0.45


def center_box_crop(image, *, width_frac=GUIDE_BOX_WIDTH_FRAC,
                    aspect=GUIDE_BOX_ASPECT, center_y_frac=GUIDE_BOX_CENTER_Y_FRAC):
    """Crop to a centered landscape rectangle (the on-screen guide box). Box
    geometry is parameterized so different card types can use different boxes;
    defaults reproduce the diamond-tag box exactly. Clamped; returns a copy."""
    h, w = image.shape[:2]
    box_w = width_frac * w
    box_h = box_w / aspect
    cx = w / 2.0
    cy = center_y_frac * h
    left = int(round(cx - box_w / 2))
    right = int(round(cx + box_w / 2))
    top = int(round(cy - box_h / 2))
    bottom = int(round(cy + box_h / 2))
    left = max(0, min(left, w - 1))
    right = max(left + 1, min(right, w))
    top = max(0, min(top, h - 1))
    bottom = max(top + 1, min(bottom, h))
    return image[top:bottom, left:right].copy()


def guide_box_crop(image, card_type):
    """center_box_crop with the box geometry for the given card type."""
    if card_type == "jewelry":
        return center_box_crop(image, width_frac=JEWELRY_GUIDE_BOX_WIDTH_FRAC,
                               aspect=JEWELRY_GUIDE_BOX_ASPECT,
                               center_y_frac=JEWELRY_GUIDE_BOX_CENTER_Y_FRAC)
    return center_box_crop(image)
