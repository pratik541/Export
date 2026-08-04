import cv2
import numpy as np

# Calibrated against 6 real IGI tag phone photos (see tests/fixtures/), not
# synthetic full-frame noise: a real photo is mostly plain background around a
# small tag, so its whole-frame Laplacian variance runs far lower than a
# maximally-detailed synthetic test image even when the tag itself is sharp and
# legible. The lowest variance among 6 verified-legible real photos was 11.3
# (and it did NOT correspond to the most in-focus-looking one — variance did
# not even reliably rank sharpness among them). A threshold near that range
# would reject real, usable photos; this only screens out near-blank/degenerate
# captures (a truly uniform image scores 0), and leaves distinguishing "good
# enough to read" to the text-presence check below, which is a direct
# measurement rather than a proxy.
BLUR_VARIANCE_THRESHOLD = 5.0
DARK_PIXEL_RATIO_THRESHOLD = 0.6
BRIGHT_PIXEL_RATIO_THRESHOLD = 0.4
MIN_OCR_CHARS = 10


def check_blur(gray_image: np.ndarray) -> tuple[bool, float]:
    variance = cv2.Laplacian(gray_image, cv2.CV_64F).var()
    return bool(variance >= BLUR_VARIANCE_THRESHOLD), variance


def check_exposure(gray_image: np.ndarray) -> tuple[bool, str | None]:
    total_pixels = gray_image.size
    dark_ratio = np.count_nonzero(gray_image < 40) / total_pixels
    bright_ratio = np.count_nonzero(gray_image > 235) / total_pixels
    if dark_ratio >= DARK_PIXEL_RATIO_THRESHOLD:
        return False, "too dark"
    if bright_ratio >= BRIGHT_PIXEL_RATIO_THRESHOLD:
        return False, "glare/overexposed"
    return True, None


def check_text_presence(image: np.ndarray, ocr_func) -> tuple[bool, int]:
    text = ocr_func(image)
    char_count = len("".join(text.split()))
    return char_count >= MIN_OCR_CHARS, char_count


def assess_quality(image: np.ndarray, ocr_func) -> tuple[bool, str | None]:
    """Run the capture quality gate. `ocr_func` is injected (pass ocr.run_ocr in
    production) so this module never needs a real tesseract install to be tested."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    is_sharp, _ = check_blur(gray)
    if not is_sharp:
        return False, "Image too blurry — please retake."

    exposure_ok, reason = check_exposure(gray)
    if not exposure_ok:
        return False, f"Image {reason} — please retake."

    text_ok, _ = check_text_presence(gray, ocr_func)
    if not text_ok:
        return False, "No readable text detected — please retake."

    return True, None
