import parsing


SAMPLE_RAW_TEXT = """C141619
IGI CERT - 809614206
REPORT
CVD
3.01
E VS1
EMERALD
Cut-VG Pol-EX
Sym-EX Fl-N
"""


def test_parse_fields_extracts_all_fields_from_sample_tag():
    fields = parsing.parse_fields(SAMPLE_RAW_TEXT)
    assert fields["lot_ref_no"] == "C141619"
    assert fields["igi_report_no"] == "809614206"
    assert fields["report_type"] == "CVD"
    assert fields["shape"] == "EMERALD"
    assert fields["carat"] == "3.01"
    assert fields["color"] == "E"
    assert fields["clarity"] == "VS1"
    assert fields["cut"] == "VG"
    assert fields["polish"] == "EX"
    assert fields["symmetry"] == "EX"
    assert fields["fluorescence"] == "N"


def test_parse_fields_accepts_svm_as_misread_of_sym_label():
    # IGI tags often OCR "Sym" as "Svm" due to font/glare (seen on the real sample tag).
    fields = parsing.parse_fields("Svm-EX")
    assert fields["symmetry"] == "EX"


def test_parse_fields_returns_none_for_missing_fields():
    fields = parsing.parse_fields("garbage unrelated text\nwith no matches")
    assert fields["igi_report_no"] is None
    assert fields["carat"] is None
    assert fields["shape"] is None


def test_validate_fields_prefers_barcode_value_over_ocr_value():
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "EX", "symmetry": "EX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value="999999999")
    assert result["igi_report_no"] == "999999999"
    assert result["needs_review"] is False


def test_validate_fields_falls_back_to_ocr_value_when_no_barcode():
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "EX", "symmetry": "EX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["igi_report_no"] == "809614206"


def test_validate_fields_flags_needs_review_when_critical_field_missing():
    fields = {
        "lot_ref_no": None, "igi_report_no": None, "report_type": None,
        "shape": None, "carat": None, "color": None, "clarity": None,
        "cut": None, "polish": None, "symmetry": None, "fluorescence": None,
    }
    result = parsing.validate_fields(fields, barcode_value=None)
    assert result["needs_review"] is True


def test_validate_fields_flags_needs_review_on_invalid_grade_code():
    # "FX" is not a valid IGI grade code (real codes are EX/VG/G/F/P) — this is the
    # exact OCR misread ("EX" -> "FX") observed on the real sample tag.
    fields = {
        "lot_ref_no": "C141619", "igi_report_no": "809614206", "report_type": "CVD",
        "shape": "EMERALD", "carat": "3.01", "color": "E", "clarity": "VS1",
        "cut": "VG", "polish": "FX", "symmetry": "FX", "fluorescence": "N",
    }
    result = parsing.validate_fields(fields, barcode_value="809614206")
    assert result["needs_review"] is True
