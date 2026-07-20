import cv2
import numpy as np


def preprocess(image: np.ndarray) -> np.ndarray:
    """Grayscale -> denoise -> adaptive threshold -> deskew. Returns a binarized
    (0/255) single-channel uint8 image the same size as the input."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binarized = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15,
    )
    return _deskew(binarized)


def _deskew(binary_image: np.ndarray) -> np.ndarray:
    dark_pixel_coords = np.column_stack(np.where(binary_image < 255))
    if dark_pixel_coords.size == 0:
        return binary_image

    angle = cv2.minAreaRect(dark_pixel_coords.astype(np.float32))[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return binary_image

    height, width = binary_image.shape[:2]
    center = (width // 2, height // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        binary_image, rotation_matrix, (width, height),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )
