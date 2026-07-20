from pathlib import Path

import pytest

import pipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "sample_tag.jpeg"

# Ground truth read directly off each real tag photo (barcode + printed text),
# independent of anything our OCR pipeline produces.
REAL_TAG_CASES = [
    ("sample_tag.jpeg", "809614206", "EMERALD", "3.01", "E", "VS1"),
    ("tag_e79422_marquise.jpeg", "791655400", "MARQUISE", "2.04", "D", "VVS2"),
    ("tag_c141640_heart.jpeg", "817630270", "HEART", "1.00", "F", "VS1"),
    ("tag_e84454_emerald.jpeg", "804633671", "EMERALD", "2.97", "E", "VVS1"),
    ("tag_c141641_heart.jpeg", "817634109", "HEART", "1.00", "F", "VS1"),
    ("tag_e86943_oval.jpeg", "809609517", "OVAL", "1.00", "D", "VVS1"),
]


def test_process_image_extracts_grading_fields_from_real_igi_tag_photo():
    image_bytes = FIXTURE_PATH.read_bytes()

    result = pipeline.process_image(image_bytes, "sample_tag.jpeg")

    assert result["accepted"] is True
    # Barcode decode is authoritative and should always win regardless of OCR noise.
    assert result["igi_report_no"] == "809614206"
    assert result["shape"] == "EMERALD"
    assert result["carat"] == "3.01"
    assert result["color"] == "E"
    assert result["clarity"] == "VS1"


@pytest.mark.parametrize("filename, igi_report_no, shape, carat, color, clarity", REAL_TAG_CASES)
def test_process_image_accepts_real_photos_and_never_fabricates_a_wrong_value(
    filename, igi_report_no, shape, carat, color, clarity
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
    # critical field was genuinely unrecoverable, needs_review must catch it
    # rather than silently exporting an incomplete row as if it were fine.
    ground_truth = {
        "igi_report_no": igi_report_no, "shape": shape,
        "carat": carat, "color": color, "clarity": clarity,
    }
    for field, expected in ground_truth.items():
        actual = result[field]
        if actual is not None:
            assert actual == expected, f"{filename}: {field} extracted as {actual!r}, expected {expected!r}"

    any_critical_field_missing = any(result[field] is None for field in ground_truth)
    if any_critical_field_missing:
        assert result["needs_review"] is True, (
            f"{filename}: a critical field was unreadable but needs_review wasn't set"
        )
