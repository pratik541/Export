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
