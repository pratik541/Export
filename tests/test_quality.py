import numpy as np

import quality


def _sharp_random_gray_bgr(height=100, width=100, seed=0):
    rng = np.random.default_rng(seed)
    gray = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


def _flat_color_bgr(value, height=100, width=100):
    return np.full((height, width, 3), value, dtype=np.uint8)


def _ok_ocr(_image):
    return "IGI CERT - 809614206 3.01 E VS1 EMERALD"


def _empty_ocr(_image):
    return "   "


def test_check_blur_flags_flat_image_as_blurry():
    flat_gray = np.full((100, 100), 128, dtype=np.uint8)
    is_sharp, _variance = quality.check_blur(flat_gray)
    assert is_sharp is False


def test_check_blur_accepts_sharp_random_image():
    rng = np.random.default_rng(0)
    noisy_gray = rng.integers(0, 256, size=(100, 100), dtype=np.uint8)
    is_sharp, _variance = quality.check_blur(noisy_gray)
    assert is_sharp is True


def test_check_exposure_flags_overexposed_image():
    bright = np.full((100, 100), 250, dtype=np.uint8)
    ok, reason = quality.check_exposure(bright)
    assert ok is False
    assert "glare" in reason or "overexposed" in reason


def test_check_exposure_flags_underexposed_image():
    dark = np.full((100, 100), 10, dtype=np.uint8)
    ok, reason = quality.check_exposure(dark)
    assert ok is False
    assert "dark" in reason


def test_check_exposure_accepts_mid_range_image():
    rng = np.random.default_rng(0)
    mid_gray = rng.integers(80, 180, size=(100, 100), dtype=np.uint8)
    ok, reason = quality.check_exposure(mid_gray)
    assert ok is True
    assert reason is None


def test_check_text_presence_accepts_when_ocr_finds_enough_text():
    ok, count = quality.check_text_presence(np.zeros((10, 10), dtype=np.uint8), _ok_ocr)
    assert ok is True
    assert count > 0


def test_check_text_presence_rejects_when_ocr_finds_almost_nothing():
    ok, count = quality.check_text_presence(np.zeros((10, 10), dtype=np.uint8), _empty_ocr)
    assert ok is False
    assert count == 0


def test_assess_quality_rejects_blurry_image():
    ok, reason = quality.assess_quality(_flat_color_bgr(128), _ok_ocr)
    assert ok is False
    assert "blurry" in reason


def test_assess_quality_rejects_overexposed_image():
    ok, reason = quality.assess_quality(_flat_color_bgr(250), _ok_ocr)
    assert ok is False
    assert "please retake" in reason


def test_assess_quality_rejects_when_no_text_found():
    ok, reason = quality.assess_quality(_sharp_random_gray_bgr(), _empty_ocr)
    assert ok is False
    assert "No readable text" in reason


def test_assess_quality_accepts_good_image():
    ok, reason = quality.assess_quality(_sharp_random_gray_bgr(), _ok_ocr)
    assert ok is True
    assert reason is None
