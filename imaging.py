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


# Jewelry-card perspective correction. Acceptance thresholds for the detected
# card quadrilateral, applied within the guide-box search region.
JEWELRY_QUAD_MIN_AREA_FRAC = 0.35   # quad must cover at least this much of the search region
JEWELRY_QUAD_MIN_ASPECT = 1.0
JEWELRY_QUAD_MAX_ASPECT = 2.2
JEWELRY_SEARCH_PAD_FRAC = 0.15      # extra margin around the guide box searched for the card's edges


def _jewelry_search_region_box(image):
    """(left, top, right, bottom) for the jewelry guide-box region expanded by
    JEWELRY_SEARCH_PAD_FRAC on each side, clamped to the image bounds. Wider
    than the guide box itself so modest user misalignment doesn't clip the
    card's real edges out of the search."""
    h, w = image.shape[:2]
    box_w = JEWELRY_GUIDE_BOX_WIDTH_FRAC * w
    box_h = box_w / JEWELRY_GUIDE_BOX_ASPECT
    cx = w / 2.0
    cy = JEWELRY_GUIDE_BOX_CENTER_Y_FRAC * h
    pad_w = box_w * JEWELRY_SEARCH_PAD_FRAC
    pad_h = box_h * JEWELRY_SEARCH_PAD_FRAC
    left = int(round(cx - box_w / 2 - pad_w))
    right = int(round(cx + box_w / 2 + pad_w))
    top = int(round(cy - box_h / 2 - pad_h))
    bottom = int(round(cy + box_h / 2 + pad_h))
    left = max(0, min(left, w - 1))
    right = max(left + 1, min(right, w))
    top = max(0, min(top, h - 1))
    bottom = max(top + 1, min(bottom, h))
    return left, top, right, bottom


def _order_quad_points(pts):
    """Order 4 (x, y) points as top-left, top-right, bottom-right, bottom-left,
    independent of the order cv2 returned them in."""
    pts = np.asarray(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    tl = pts[int(np.argmin(s))]
    br = pts[int(np.argmax(s))]
    tr = pts[int(np.argmin(diff))]
    bl = pts[int(np.argmax(diff))]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _find_card_quad(region):
    """Return the 4 ordered corner points of the card within `region`, or None
    if no sufficiently large, plausibly-shaped quadrilateral is found."""
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    region_area = region.shape[0] * region.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        if cv2.contourArea(approx) < JEWELRY_QUAD_MIN_AREA_FRAC * region_area:
            continue
        ordered = _order_quad_points(approx.reshape(4, 2))
        tl, tr, br, bl = ordered
        width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
        height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
        if height == 0:
            continue
        aspect = width / height
        if not (JEWELRY_QUAD_MIN_ASPECT <= aspect <= JEWELRY_QUAD_MAX_ASPECT):
            continue
        return ordered
    return None


def perspective_correct_jewelry_card(image):
    """Detect the jewelry card's edges near the guide box and perspective-warp
    it flat, correcting for camera tilt. Raises ValueError if no confident
    card quadrilateral is found, so the caller can reject the capture and ask
    the user to retake it."""
    left, top, right, bottom = _jewelry_search_region_box(image)
    region = image[top:bottom, left:right]
    quad = _find_card_quad(region)
    if quad is None:
        raise ValueError(
            "Could not detect the card's edges — retake with the card flat, "
            "well-lit, and filling the guide box."
        )
    tl, tr, br, bl = quad
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    height = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
                   dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(region, matrix, (width, height))
