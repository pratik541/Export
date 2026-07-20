import parsing


SAMPLE_RAW_TEXT = """C141619
IGI CERT - 809614206
REPORT
CVD
3.01
E VS1
EMERALD
"""


def test_parse_fields_extracts_all_fields_from_sample_tag():
    fields = parsing.parse_fields(SAMPLE_RAW_TEXT)
    assert fields["igi_report_no"] == "809614206"
    assert fields["report_type"] == "CVD"
    assert fields["shape"] == "EMERALD"
    assert fields["carat"] == "3.01"
    assert fields["color"] == "E"
    assert fields["clarity"] == "VS1"


def test_parse_fields_returns_none_for_missing_fields():
    fields = parsing.parse_fields("garbage unrelated text\nwith no matches")
    assert fields["igi_report_no"] is None
    assert fields["carat"] is None
    assert fields["shape"] is None
    assert fields["report_type"] is None


def test_parse_fields_matches_shape_with_trailing_ocr_noise_on_same_line():
    # Real OCR output on a genuine tag photo included a stray trailing
    # character on the shape line ("EMERALD #") rather than a clean match.
    fields = parsing.parse_fields("EMERALD #")
    assert fields["shape"] == "EMERALD"


def test_parse_fields_accepts_marouise_as_misread_of_marquise():
    # Real OCR output on a genuine tag photo misread "MARQUISE" as "MAROUISE"
    # (Q/O confusion), with trailing noise attached on the same line.
    fields = parsing.parse_fields("MAROUISE! ate")
    assert fields["shape"] == "MARQUISE"


def test_validate_fields_prefers_barcode_value_over_ocr_value():
    fields = {
        "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
    }
    result = parsing.validate_fields(fields, barcode_value="999999999")
    assert result["igi_report_no"] == "999999999"
    assert result["needs_review"] is False


def test_validate_fields_falls_back_to_ocr_value_when_no_barcode():
    fields = {
        "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["igi_report_no"] == "809614206"


def test_validate_fields_flags_needs_review_when_field_missing():
    fields = {
        "igi_report_no": None, "report_type": None,
        "shape": None, "carat": None, "color": None, "clarity": None,
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["needs_review"] is True


def test_validate_fields_flags_needs_review_on_invalid_report_type():
    fields = {
        "igi_report_no": "809614206", "report_type": "GARBLED",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
    }
    result = parsing.validate_fields(fields, barcode_value="809614206")
    assert result["needs_review"] is True
