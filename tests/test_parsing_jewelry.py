"""Tests for the verbatim jewelry-card parser. Values are taken exactly as OCR
reads them after each printed label — no normalization, whitelists, or guessing."""
from ocr import parsing_jewelry

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


# A THIRD real OCR pass of the same card: the Shape/Weight labels zipper in the
# OPPOSITE order from REAL_OCR_2 ("Est. Woiolt Shape and Cut : v1 : v2" instead
# of "Shape and Cut Est, Weight : v1 : v2"), BOTH "Weight" and "Carat" are
# misread ("Woiolt", "Corat") so neither anchor works, AND the Clarity/Color
# VALUE ORDER FLIPPED relative to the first two passes (color's value now comes
# BEFORE clarity's value on the zippered line, ":t-F : VS" not ": VS :E-F").
# This is the true regression that broke a third time: label-print-order can't
# be trusted to predict value order, and a garbled label+unit pair can blank a
# field that assumes only one of them will ever be misread at a time.
REAL_OCR_3 = "\n".join([
    "INTERNATIONAL GEMOLOGICAL LAIORATORY GROWN DIAMOND JEWELRY REPORT",
    "ANRw INSTITUTE",
    "Description Report No, One (1) Loboratory Grown Dlomond :45J331622607 : One "
    "siver Pendont wilin Chaln, welghing in fotol 2.06 g. contolning",
    "Est. Woiolt Shape and Cut : (1) Oval Brilliant : 0.54 Corat",
    "Clarity Color :t-F : VS",
    "Comments Weights purported by the cllent, Report rumber engraved. Stylo# "
    "AFDN352/8 : Grading & identincalion as mounting pemits. Description and",
])


def test_parses_third_real_ocr_pass_with_flipped_value_order_and_double_misreads():
    f = parsing_jewelry.parse_jewelry(REAL_OCR_3)
    assert f["report_no"] == "45J331622607"
    assert f["shape_cut"] == "(1) Oval Brilliant"
    assert f["est_weight"] == "0.54 Corat"    # located positionally; "Corat"/"Woiolt" both misread
    assert f["clarity"] == "VS"                # correct despite the value-order flip
    assert f["color"] == "t-F"                 # verbatim; located by its dash shape, not order
    assert f["style_no"] == "AFDN352/8"
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False


# A FOURTH real OCR pass: this time COLOR is zippered with "Est, Weight" instead
# of with "Clarity" ("Est, Weight Color : 0.56 Carat :E-F"), while "Clarity"
# ends up zippered with the unrelated "Comments" label instead ("Clarity
# Comments ... Stylet AFDN352/9 : VS : Grading ..."). This is the true
# regression that broke a fourth time: color's value was located by "whichever
# label it's zippered against" rather than by its own shape, so when Color
# paired with a NUMERIC field instead of Clarity, the numeric value ("0.56
# Carat") was grabbed instead of "E-F".
REAL_OCR_4 = "\n".join([
    "INTERNATIONAL GEMOLOGICAL LABORATORY GROWN DIAMOND JEWELRY REPORT",
    "INSTITUTE",
    "Report No. One (1) Laboratory Grown Diamond Description : One Slver Pendant "
    "with Chain, welghing in total 2.06 g.. containing ：45J331632607",
    "Shape and Cut : (1) Oval Briliant",
    "Est, Weight Color : 0.56 Carat :E-F",
    "Clarity Comments Weights purported by the cllent, Report number engraved. "
    "Stylet AFDN352/9 : VS : Grading & ldentification as mounting permits. "
    "Description and",
])


def test_parses_fourth_real_ocr_pass_with_color_zippered_to_weight_instead_of_clarity():
    f = parsing_jewelry.parse_jewelry(REAL_OCR_4)
    assert f["report_no"] == "45J331632607"
    assert f["shape_cut"] == "(1) Oval Briliant"
    assert f["est_weight"] == "0.56 Carat"
    assert f["color"] == "E-F"    # NOT "0.56 Carat" (color was zippered with weight, not clarity)
    assert f["clarity"] == "VS"   # zippered with "Comments" this time, not "Color"
    assert f["style_no"] == "AFDN352/9"
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False


# A FIFTH real OCR pass, of a DIFFERENT physical card (a multi-stone ring, not
# the single-diamond pendant of the first four fixtures): this time OCR did NOT
# zipper Clarity/Color together at all -- they landed cleanly on separate
# lines -- but the "Clarity" label itself was misread as "Clarty" (missing the
# "i"). Clarity was located two ways: the zippered-line heuristic (moot here,
# nothing zippered) and a fallback requiring the literal substring "clarity" on
# a line -- "Clarty" doesn't contain that substring, so clarity came back None.
# This is the true regression that broke a fifth time: clarity had no
# label-independent fallback the way color/report_no/style_no do. Also caught
# in the same card: "Tot, Est. Weight : 3.24 Carats" (plural, this card totals
# 28 stones) was truncated to "3.24 Carat" -- the weight regex didn't account
# for the plural and silently dropped a verbatim character.
REAL_OCR_5 = "\n".join([
    "INTERNATIONAL LABORATORY GROWN DIAMOND",
    "GEMOLOGICAL JEWELRY REPORT",
    "INSTITUTE",
    "Report No, :43J936232607",
    "Description : One White Gold Ring, weighing in total 3.22 g., confaining",
    "Twenity Eight (28) Laboratory Grown Diamonds",
    "Shape and Cut : (28) Emerald Cut",
    "Tot, Est. Weight : 3.24 Carats",
    "Color :F-G",
    "Clarty : VS",
    "Comments : Grading & Identification as mounting perrmits. Descripticn",
    "and Weighits purported by the cllent., Report number engraved. Style#",
    "AFDRB802/29",
])


def test_parses_fifth_real_ocr_pass_with_misread_clarity_label_and_plural_carats():
    f = parsing_jewelry.parse_jewelry(REAL_OCR_5)
    assert f["report_no"] == "43J936232607"
    assert f["shape_cut"] == "(28) Emerald Cut"
    assert f["est_weight"] == "3.24 Carats"  # verbatim, incl. the plural
    assert f["color"] == "F-G"
    assert f["clarity"] == "VS"              # found despite "Clarty" label
    assert f["style_no"] == "AFDRB802/29"
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False


# A SIXTH real OCR pass, of yet another physical card (a multi-stone ring, 23
# round brilliants): the Comments field's LABEL was lost, and its boilerplate
# VALUE text got zippered onto the Clarity line, landing between Clarity's own
# colon and the real clarity value's colon: "Clarity : Grading &
# Identification as mounting permits. Descripticn : VVs-VS". The fuzzy-label
# fallback used to take the segment between the first two colons (the shape
# built for a *different* zippering pattern -- two labels' worth of text
# before all the values), grabbing the Comments boilerplate instead of the
# real value. Also note the OCR case noise in the trade range itself
# ("VVs-VS", not "VVS-VS") -- must come back exactly as OCR produced it.
REAL_OCR_6 = "\n".join([
    "INTERNATIONAL GEMOLOGICAL LABORATORY GROWN DIAMOND JEWELRY REPORT",
    "INSTITUTE",
    "Description Report No. : One Slver Ring. weighing in total 2.74 g.. "
    "containing Twenty :38J945252606",
    "Three (23) Laboratory Grown Diamonds",
    "Shape and Cut : (23) Round Brillant",
    "Tot. Est. Weight : 2.50 Carats",
    "Color :E-F",
    "Clarity : Grading & Identification as mounting permits. Descripticn : VVs-VS",
    "and Weights purported by the client. Report number engraved. Styles Comments",
    "AFDRB201/110",
])


def test_parses_sixth_real_ocr_pass_with_comments_blob_zippered_onto_clarity_line():
    f = parsing_jewelry.parse_jewelry(REAL_OCR_6)
    assert f["report_no"] == "38J945252606"
    assert f["shape_cut"] == "(23) Round Brillant"
    assert f["est_weight"] == "2.50 Carats"
    assert f["color"] == "E-F"
    assert f["clarity"] == "VVs-VS"  # NOT the Comments boilerplate text; verbatim case noise kept
    assert f["style_no"] == "AFDRB201/110"
    assert parsing_jewelry.validate_jewelry_fields(f)["needs_review"] is False


# Parcel/melee-grading cards report a TRADE RANGE for clarity instead of a
# single grade (e.g. "VVS-VS", not just "VS"). _looks_like_color_range used a
# plain substring search, so a trade range like "VVS-VS" or "SI-I" hides a
# single-letter-dash-single-letter substring ("S-V", "I-I") that false-
# positived as "looks like a colour range" -- making both zippered candidates
# look colour-shaped, so the swap-decision fell back to fragile label-order
# guessing instead of confidently telling clarity and colour apart.
def test_clarity_trade_range_not_misidentified_as_color():
    text = "Clarity Color : VVS-VS :F-G"
    f = parsing_jewelry.parse_jewelry(text)
    assert f["clarity"] == "VVS-VS"
    assert f["color"] == "F-G"


def test_clarity_trade_range_correct_even_with_flipped_value_order():
    # Same failure class as REAL_OCR_3: the VALUE order on a zippered line
    # doesn't always match the label order.
    text = "Clarity Color : F-G :VVS-VS"
    f = parsing_jewelry.parse_jewelry(text)
    assert f["clarity"] == "VVS-VS"
    assert f["color"] == "F-G"


def test_other_clarity_trade_ranges_not_misidentified_as_color():
    for clarity_val, color_val in [
        ("VS-SI", "E-F"), ("SI-I", "D-E"), ("VVS-SI", "F-G"), ("FL-VVS", "D-E"),
    ]:
        text = f"Clarity Color : {clarity_val} :{color_val}"
        f = parsing_jewelry.parse_jewelry(text)
        assert f["clarity"] == clarity_val
        assert f["color"] == color_val
