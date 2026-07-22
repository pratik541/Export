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


def test_crop_to_label_returns_region_containing_the_barcode():
    image = np.zeros((1600, 1200, 3), dtype=np.uint8)
    barcode_box = (269, 792, 294, 32)  # left, top, width, height (from a real fixture)
    crop = imaging.crop_to_label(image, barcode_box)
    # crop is smaller than the full frame in both dimensions
    assert crop.shape[0] < image.shape[0]
    assert crop.shape[1] < image.shape[1]
    # and non-empty
    assert crop.shape[0] > 0 and crop.shape[1] > 0


def test_crop_to_label_clamps_to_image_bounds_for_edge_barcode():
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    # barcode near the top-left corner: padding would go negative without clamping
    barcode_box = (5, 5, 200, 20)
    crop = imaging.crop_to_label(image, barcode_box)
    # no crash, valid non-empty region fully inside the image
    assert 0 < crop.shape[0] <= 400
    assert 0 < crop.shape[1] <= 400


def test_crop_to_label_expands_right_and_down_more_than_left_and_up():
    image = np.zeros((2000, 2000, 3), dtype=np.uint8)
    bl, bt, bw, bh = 800, 800, 300, 30
    crop = imaging.crop_to_label(image, (bl, bt, bw, bh))
    left, top, right, bottom = imaging.label_crop_box(image, (bl, bt, bw, bh))
    # barcode's own edges
    assert left <= bl and top <= bt
    assert right >= bl + bw and bottom >= bt + bh
    # right/down padding larger than left/up padding
    assert (right - (bl + bw)) > (bl - left)
    assert (bottom - (bt + bh)) > (bt - top)
