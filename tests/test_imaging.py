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


def test_center_box_crop_returns_centered_landscape_region_smaller_than_frame():
    image = np.zeros((1600, 1200, 3), dtype=np.uint8)
    crop = imaging.center_box_crop(image)
    ch, cw = crop.shape[:2]
    assert 0 < cw < 1200 and 0 < ch < 1600
    # ~78% width, 2:1 landscape
    assert abs(cw - round(0.78 * 1200)) <= 2
    assert cw > ch  # landscape
    assert abs(cw / ch - 2.0) < 0.1


def test_center_box_crop_clamps_to_bounds_on_small_image():
    image = np.zeros((50, 60, 3), dtype=np.uint8)
    crop = imaging.center_box_crop(image)
    assert 0 < crop.shape[0] <= 50
    assert 0 < crop.shape[1] <= 60


def test_center_box_crop_returns_a_copy_not_a_view():
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    crop = imaging.center_box_crop(image)
    crop[0, 0] = 255
    assert image[0, 0].tolist() == [0, 0, 0]  # original untouched


def test_jewelry_guide_box_is_wider_and_less_wide_aspect_than_diamond():
    assert imaging.JEWELRY_GUIDE_BOX_WIDTH_FRAC == 0.92
    assert imaging.JEWELRY_GUIDE_BOX_ASPECT == 1.5
    assert imaging.JEWELRY_GUIDE_BOX_CENTER_Y_FRAC == 0.45


def test_guide_box_crop_diamond_matches_default_center_box_crop():
    img = np.full((400, 600, 3), 128, dtype=np.uint8)
    assert imaging.guide_box_crop(img, "diamond").shape == imaging.center_box_crop(img).shape


def test_guide_box_crop_jewelry_is_taller_than_diamond():
    img = np.full((400, 600, 3), 128, dtype=np.uint8)
    d = imaging.guide_box_crop(img, "diamond")
    j = imaging.guide_box_crop(img, "jewelry")
    assert j.shape[0] > d.shape[0]   # jewelry box captures more vertical area
