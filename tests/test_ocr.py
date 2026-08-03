import numpy as np

import ocr


class _FakeReader:
    def __init__(self, result):
        self._result = result
        self.predict_calls = []

    def predict(self, image):
        self.predict_calls.append(image)
        return self._result


def _detection_result(entries):
    """Build a fake PaddleOCR predict() result from (box, text, score) tuples."""
    return [
        {
            "rec_polys": [box for box, _, _ in entries],
            "rec_texts": [text for _, text, _ in entries],
            "rec_scores": [score for _, _, score in entries],
        }
    ]


def test_group_into_lines_merges_boxes_on_the_same_row():
    detections = [
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "E", 0.9),
        ([[60, 2], [140, 2], [140, 22], [60, 22]], "VS1", 0.9),
    ]
    assert ocr.group_into_lines(detections) == "E VS1"


def test_group_into_lines_keeps_far_apart_rows_separate():
    detections = [
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "REPORT", 0.9),
        ([[0, 100], [50, 100], [50, 120], [0, 120]], "CVD", 0.9),
    ]
    assert ocr.group_into_lines(detections) == "REPORT\nCVD"


def test_group_into_lines_orders_boxes_left_to_right_within_a_row():
    detections = [
        ([[100, 0], [150, 0], [150, 20], [100, 20]], "VS1", 0.9),
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "E", 0.9),
    ]
    assert ocr.group_into_lines(detections) == "E VS1"


def test_run_ocr_returns_grouped_text_from_the_reader(monkeypatch):
    fake_reader = _FakeReader(_detection_result([
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "REPORT", 0.9),
        ([[0, 30], [50, 30], [50, 50], [0, 50]], "CVD", 0.9),
    ]))
    monkeypatch.setattr(ocr, "get_reader", lambda: fake_reader)

    result = ocr.run_ocr(np.zeros((100, 100, 3), dtype=np.uint8))

    assert result == "REPORT\nCVD"


def test_run_ocr_converts_grayscale_input_to_bgr_before_calling_the_reader(monkeypatch):
    fake_reader = _FakeReader(_detection_result([]))
    monkeypatch.setattr(ocr, "get_reader", lambda: fake_reader)

    ocr.run_ocr(np.zeros((100, 100), dtype=np.uint8))

    assert len(fake_reader.predict_calls) == 1
    assert fake_reader.predict_calls[0].ndim == 3


def test_run_ocr_passes_color_images_through_unchanged(monkeypatch):
    fake_reader = _FakeReader(_detection_result([]))
    monkeypatch.setattr(ocr, "get_reader", lambda: fake_reader)

    image = np.zeros((100, 100, 3), dtype=np.uint8)
    ocr.run_ocr(image)

    assert fake_reader.predict_calls[0] is image


def test_get_reader_returns_a_cached_singleton(monkeypatch):
    created = []

    class _StubPaddleOCR:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(ocr, "PaddleOCR", _StubPaddleOCR)
    monkeypatch.setattr(ocr, "_reader", None)

    first = ocr.get_reader()
    second = ocr.get_reader()

    assert first is second
    assert len(created) == 1


def test_group_into_lines_by_overlap_merges_boxes_that_actually_overlap_vertically():
    detections = [
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "E", 0.9),
        ([[60, 2], [140, 2], [140, 22], [60, 22]], "VS1", 0.9),
    ]
    assert ocr.group_into_lines_by_overlap(detections) == "E VS1"


def test_group_into_lines_by_overlap_keeps_far_apart_rows_separate():
    detections = [
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "REPORT", 0.9),
        ([[0, 100], [50, 100], [50, 120], [0, 120]], "CVD", 0.9),
    ]
    assert ocr.group_into_lines_by_overlap(detections) == "REPORT\nCVD"


def test_group_into_lines_by_overlap_orders_boxes_left_to_right_within_a_row():
    detections = [
        ([[100, 0], [150, 0], [150, 20], [100, 20]], "VS1", 0.9),
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "E", 0.9),
    ]
    assert ocr.group_into_lines_by_overlap(detections) == "E VS1"


def test_group_into_lines_by_overlap_keeps_close_but_non_overlapping_rows_separate():
    detections = [
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "REPORT", 0.9),
        ([[0, 20], [50, 20], [50, 30], [0, 30]], "TWO", 0.9),
    ]
    # Centers are only 15px apart (10 vs 25) -- group_into_lines's flat 15px
    # tolerance merges these into one scrambled line. Their y-extents
    # ([0,20] vs [20,30]) don't overlap at all, so overlap-based grouping
    # correctly keeps them as separate rows. This is the exact mechanism
    # behind the real "Clarity Color : VS :E-F" zippering seen in production.
    assert ocr.group_into_lines(detections) == "REPORT TWO"
    assert ocr.group_into_lines_by_overlap(detections) == "REPORT\nTWO"


def test_run_ocr_jewelry_uses_overlap_based_grouping(monkeypatch):
    fake_reader = _FakeReader(_detection_result([
        ([[0, 0], [50, 0], [50, 20], [0, 20]], "REPORT", 0.9),
        ([[0, 20], [50, 20], [50, 30], [0, 30]], "TWO", 0.9),
    ]))
    monkeypatch.setattr(ocr, "get_reader", lambda: fake_reader)
    result = ocr.run_ocr_jewelry(np.zeros((100, 100, 3), dtype=np.uint8))
    assert result == "REPORT\nTWO"
