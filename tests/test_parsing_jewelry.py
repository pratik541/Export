"""Tests for the verbatim jewelry-card parser. Values are taken exactly as OCR
reads them after each printed label — no normalization, whitelists, or guessing."""
import parsing_jewelry

# OCR text mirroring the real card layout (label : value per line; Style# lives
# inside the Comments sentence).
SAMPLE = "\n".join([
    "Report No. : 45J331632607",
    "Description : One Silver Pendant with Chain, weighing in total 2.06 g., containing",
    "One (1) Laboratory Grown Diamond",
    "Shape and Cut : (1) Oval Brilliant",
    "Est. Weight : 0.56 Carat",
    "Color : E - F",
    "Clarity : VS",
    "Comments : Grading & Identification as mounting permits. Description and",
    "Weights purported by the client. Report number engraved. Style# AFDN352/9",
])


def test_parse_extracts_all_fields_verbatim():
    f = parsing_jewelry.parse_jewelry(SAMPLE)
    assert f["report_no"] == "45J331632607"
    assert f["shape_cut"] == "(1) Oval Brilliant"   # verbatim, (1) kept
    assert f["est_weight"] == "0.56 Carat"           # verbatim, unit kept
    assert f["color"] == "E - F"                     # verbatim, spacing kept
    assert f["clarity"] == "VS"
    assert f["style_no"] == "AFDN352/9"


def test_validate_ok_when_all_present():
    f = parsing_jewelry.parse_jewelry(SAMPLE)
    v = parsing_jewelry.validate_jewelry_fields(f)
    assert v["needs_review"] is False


def test_validate_flags_review_when_a_field_missing():
    text = SAMPLE.replace("Clarity : VS", "Clarity :")   # blank clarity
    v = parsing_jewelry.validate_jewelry_fields(parsing_jewelry.parse_jewelry(text))
    assert v["needs_review"] is True


def test_missing_labels_give_none_not_crash():
    f = parsing_jewelry.parse_jewelry("nothing useful here")
    assert all(f[k] is None for k in
               ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no"))


def test_parse_handles_missing_colon_separator():
    # Real photos sometimes drop the ':' column -> value follows the label
    # directly. This blanked Report No./Shape/Weight in production; must work now.
    text = "\n".join([
        "Report No. 45J331632607",
        "Shape and Cut (1) Oval Brilliant",
        "Est. Weight 0.56 Carat",
        "Color E - F",
        "Clarity VS",
        "Report number engraved. Style# AFDN352/9",
    ])
    f = parsing_jewelry.parse_jewelry(text)
    assert f["report_no"] == "45J331632607"
    assert f["shape_cut"] == "(1) Oval Brilliant"
    assert f["est_weight"] == "0.56 Carat"
    assert f["color"] == "E - F"
    assert f["clarity"] == "VS"
    assert f["style_no"] == "AFDN352/9"


def test_style_no_skips_stray_chars_before_the_code():
    # Regression: production showed Style# == "r"; the code token must be found
    # even when OCR leaves junk between "Style#" and the actual code.
    f = parsing_jewelry.parse_jewelry("engraved. Style# r AFDN352/16")
    assert f["style_no"] == "AFDN352/16"


# The ACTUAL PaddleOCR output for a real jewelry card (columns merged/jumbled:
# Report No. value stranded on the Description line, Color+Clarity collapsed onto
# one line, "Stylo#" misread). This is the true regression that broke production.
REAL_OCR = "\n".join([
    "GEMOLOGICAL INTERNATIONAL LABORATORY GROWN DIAMOND JEWELRY REPORT",
    "INSTITUTE",
    "Description One (1) Laboratory Grown Diamond Report No. : One Siver Pendant "
    "with Chaln. weighing In total 2.06 .. contalning ：45J331632607",
    "Shape and Cut : (1) Oval Briliant",
    "Est. Weight : 0.56 Carat",
    "Clarity Color : VS :E-F",
    "Weights purported by the client, Report number engraved. Stylo# AFDN352/9 "
    "Comments : Grading & ldentification as mounting permits, Description and",
    "122500 209",
])


def test_parses_real_jumbled_ocr_output():
    f = parsing_jewelry.parse_jewelry(REAL_OCR)
    assert f["report_no"] == "45J331632607"
    assert f["shape_cut"] == "(1) Oval Briliant"
    assert f["est_weight"] == "0.56 Carat"
    assert f["color"] == "E-F"
    assert f["clarity"] == "VS"
    assert f["style_no"] == "AFDN352/9"
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False


# A SECOND real OCR pass of the same card with different, worse misreads: the
# Shape-and-Cut/Est-Weight labels zipper onto one line, Clarity's value itself is
# misread ("VS" -> "V5"), and the "Style#" LABEL is misread beyond recognition
# ("Shyios"). This is the true regression that broke production a second time:
# whitelist-matching the clarity value, and label-anchoring the style code,
# both failed here even though the values are plainly present in the text.
REAL_OCR_2 = "\n".join([
    "INTERNATIONAL GEMOLOGICAL LABORATORY GROWN DIAMOND JEWELRY REPORT",
    "INSTITUTE",
    "Report No. One (1) Laboratory Grawn Diamond Description : One Siver Pendant "
    "with Chaln, welghing In fotal 2.06 g.. containing :45J331622607",
    "Shape and Cut Est, Weight : (1) Oval Brilliant : 0.54 Carat",
    "Clarity Color : V5 :E-F",
    "Comments Weights purported by the cllent. Report number engraved. Shyios "
    "AFDN352/8 : Grading & Identification as mounling permits. Descripfion and",
])


def test_parses_second_real_ocr_pass_with_zippered_lines_and_misreads():
    f = parsing_jewelry.parse_jewelry(REAL_OCR_2)
    assert f["report_no"] == "45J331622607"          # verbatim, incl. OCR digit noise
    assert f["shape_cut"] == "(1) Oval Brilliant"      # NOT "Est, Weight : ..."
    assert f["est_weight"] == "0.54 Carat"
    assert f["color"] == "E-F"
    assert f["clarity"] == "V5"                        # verbatim misread, NOT "VS"
    assert f["style_no"] == "AFDN352/8"                # found despite "Shyios" label
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False
