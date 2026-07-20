from pathlib import Path

import pipeline

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_tag.jpeg"


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
