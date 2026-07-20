import numpy as np

import imaging


def _synthetic_bgr_image(height=120, width=200, seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def test_preprocess_returns_single_channel_same_size():
    image = _synthetic_bgr_image()
    result = imaging.preprocess(image)
    assert result.shape == (120, 200)
    assert result.dtype == np.uint8


def test_preprocess_output_is_binary():
    image = _synthetic_bgr_image()
    result = imaging.preprocess(image)
    unique_values = set(np.unique(result).tolist())
    assert unique_values.issubset({0, 255})


def test_preprocess_handles_already_grayscale_input():
    rng = np.random.default_rng(1)
    gray_image = rng.integers(0, 256, size=(80, 150), dtype=np.uint8)
    result = imaging.preprocess(gray_image)
    assert result.shape == (80, 150)


def test_preprocess_handles_blank_white_image_without_crashing():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)
    result = imaging.preprocess(blank)
    assert result.shape == (100, 100)
