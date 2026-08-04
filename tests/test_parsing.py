from ocr import parsing


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


def test_parse_fields_matches_carat_with_trailing_ocr_noise_on_same_line():
    # Seen on real cropped tag photos with PaddleOCR: the carat value's row
    # picked up "VIDEO"/"VID" noise from the nearby "Video Link" label
    # ("1.00 VIDEO", "3.01 VID") rather than sitting alone on its line.
    fields = parsing.parse_fields("1.00 VIDEO")
    assert fields["carat"] == "1.00"


def test_parse_fields_does_not_match_carat_inside_a_longer_number():
    # A decimal-looking substring embedded in a longer digit run (e.g. part
    # of a barcode/report number) must not be mistaken for the carat value.
    fields = parsing.parse_fields("12309614.206")
    assert fields["carat"] is None


def test_parse_fields_matches_shape_with_trailing_ocr_noise_on_same_line():
    # Real OCR output on a genuine tag photo included a stray trailing
    # character on the shape line ("EMERALD #") rather than a clean match.
    fields = parsing.parse_fields("EMERALD #")
    assert fields["shape"] == "EMERALD"


def test_parse_fields_matches_color_clarity_with_leading_ocr_noise_on_same_line():
    # Seen with PaddleOCR: a detected "CERT Link" text box sometimes gets an
    # abnormally tall bounding box whose vertical center lands close enough
    # to the color/clarity row that row-grouping merges them onto one line
    # ("CERT Link D VVS2"). The color/clarity pattern must still find the
    # match even though it isn't at the start of the line -- same tolerance
    # `shape` already has for surrounding noise.
    fields = parsing.parse_fields("CERT Link D VVS2")
    assert fields["color"] == "D"
    assert fields["clarity"] == "VVS2"


def test_parse_fields_accepts_marouise_as_misread_of_marquise():
    # Real OCR output on a genuine tag photo misread "MARQUISE" as "MAROUISE"
    # (Q/O confusion), with trailing noise attached on the same line.
    fields = parsing.parse_fields("MAROUISE! ate")
    assert fields["shape"] == "MARQUISE"


def test_parse_fields_accepts_cvd_with_one_extra_character():
    # Real OCR output on a genuine tag photo: "CVD" read as "cVvD" (extra V).
    fields = parsing.parse_fields("REPORT\ncVvD")
    assert fields["report_type"] == "CVD"


def test_parse_fields_accepts_cvd_with_one_substituted_character():
    # Real OCR output on a genuine tag photo: "CVD" read as "cvb" (D -> b).
    fields = parsing.parse_fields("REPORT\ncvb")
    assert fields["report_type"] == "CVD"


def test_parse_fields_does_not_fabricate_report_type_from_unrelated_text():
    # Real OCR output on a genuine tag photo: "CVD" wasn't captured at all --
    # what follows "REPORT" is unrelated OCR noise, not a near-miss of any
    # known report type, and must not be forced into a match.
    fields = parsing.parse_fields("REPORT\nIG\nRT - 80961420")
    assert fields["report_type"] is None


def test_parse_fields_recognizes_hpht_report_type():
    # IGI lab-grown diamond reports name the growth method as CVD or HPHT.
    fields = parsing.parse_fields("REPORT\nHPHT")
    assert fields["report_type"] == "HPHT"


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
