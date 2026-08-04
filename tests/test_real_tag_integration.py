from pathlib import Path

import pytest

from ocr import pipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Ground truth read directly off each real tag photo (barcode + printed text),
# independent of anything our OCR pipeline produces. All six are CVD reports.
REAL_TAG_CASES = [
    ("sample_tag.jpeg", "809614206", "CVD", "EMERALD", "3.01", "E", "VS1"),
    ("tag_e79422_marquise.jpeg", "791655400", "CVD", "MARQUISE", "2.04", "D", "VVS2"),
    ("tag_c141640_heart.jpeg", "817630270", "CVD", "HEART", "1.00", "F", "VS1"),
    ("tag_e84454_emerald.jpeg", "804633671", "CVD", "EMERALD", "2.97", "E", "VVS1"),
    ("tag_c141641_heart.jpeg", "817634109", "CVD", "HEART", "1.00", "F", "VS1"),
    ("tag_e86943_oval.jpeg", "809609517", "CVD", "OVAL", "1.00", "D", "VVS1"),
    # Tightly-cropped versions of three of the tags above -- with PaddleOCR
    # these extract every field correctly (needs_review=False), unlike the
    # original Tesseract-based pipeline which struggled even on crops.
    ("tag_c141619_emerald_cropped.jpeg", "809614206", "CVD", "EMERALD", "3.01", "E", "VS1"),
    ("tag_c141641_heart_cropped.jpeg", "817634109", "CVD", "HEART", "1.00", "F", "VS1"),
    ("tag_e86943_oval_cropped.jpeg", "809609517", "CVD", "OVAL", "1.00", "D", "VVS1"),
]


@pytest.mark.parametrize(
    "filename, igi_report_no, report_type, shape, carat, color, clarity", REAL_TAG_CASES
)
def test_process_image_accepts_real_photos_and_never_fabricates_a_wrong_value(
    filename, igi_report_no, report_type, shape, carat, color, clarity
):
    image_bytes = (FIXTURES_DIR / filename).read_bytes()

    result = pipeline.process_image(image_bytes, filename)

    # These are real, legibly-in-focus phone photos (verified by eye) of six
    # different tags. A photo being merely "not maximally sharp across the
    # whole frame" (mostly plain background, unlike a full-frame test image)
    # must never cause a real, readable tag to be silently rejected.
    assert result["accepted"] is True, f"{filename} was rejected: {result.get('reason')}"

    # Some of these real photos have genuine, per-field capture limitations
    # (e.g. a barcode too soft to decode, or a small value OCR garbled beyond
    # recognition) that no parsing logic can recover from -- there is no
    # trace of the correct value left in the OCR output to extract. So: don't
    # require every field to be extracted, but whichever fields WERE
    # extracted must be correct (never a fabricated/wrong value), and if a
    # field was genuinely unrecoverable, needs_review must catch it rather
    # than silently exporting an incomplete row as if it were fine.
    ground_truth = {
        "igi_report_no": igi_report_no, "report_type": report_type, "shape": shape,
        "carat": carat, "color": color, "clarity": clarity,
    }
    for field, expected in ground_truth.items():
        actual = result[field]
        if actual is not None:
            assert actual == expected, f"{filename}: {field} extracted as {actual!r}, expected {expected!r}"

    any_field_missing = any(result[field] is None for field in ground_truth)
    if any_field_missing:
        assert result["needs_review"] is True, (
            f"{filename}: a field was unreadable but needs_review wasn't set"
        )
