import re

SHAPE_WHITELIST = {
    "ROUND", "EMERALD", "OVAL", "PEAR", "CUSHION", "PRINCESS",
    "RADIANT", "HEART", "MARQUISE", "ASSCHER",
}
CLARITY_WHITELIST = {
    "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "SI3", "I1", "I2", "I3",
}
GRADE_WHITELIST = {"EX", "VG", "G", "F", "P"}
FLUORESCENCE_WHITELIST = {"N", "F", "M", "S", "VS"}
REPORT_TYPE_WHITELIST = {"CVD", "NATURAL", "TREATED"}

CRITICAL_FIELDS = ("igi_report_no", "shape", "carat", "color", "clarity")

_CARAT_RE = re.compile(r"^\d+\.\d{2}$")
_COLOR_CLARITY_RE = re.compile(
    r"^([D-Z])\s+(FL|IF|VVS1|VVS2|VS1|VS2|SI1|SI2|SI3|I1|I2|I3)$"
)
_IGI_CERT_RE = re.compile(r"IGI\s*CERT\s*-?\s*(\d{8,10})", re.IGNORECASE)
_LOT_REF_RE = re.compile(r"^[A-Z]\d{5,7}$")
_REPORT_TYPE_RE = re.compile(r"REPORT\s+(CVD|NATURAL|TREATED)", re.IGNORECASE)
_GRADE_LABEL_RE = re.compile(
    r"\b(Cut|Pol|Sym|Svm|Sim|Fl)\s*[-:]\s*([A-Za-z]{1,3})\b", re.IGNORECASE
)
_GRADE_LABEL_MAP = {
    "CUT": "cut", "POL": "polish", "SYM": "symmetry", "SVM": "symmetry",
    "SIM": "symmetry", "FL": "fluorescence",
}

_FIELD_KEYS = (
    "lot_ref_no", "igi_report_no", "report_type", "shape", "carat",
    "color", "clarity", "cut", "polish", "symmetry", "fluorescence",
)


def parse_fields(raw_text: str) -> dict:
    """Parse raw OCR text from an IGI tag into structured fields via per-line and
    whole-text regex/keyword matching. Missing fields are None."""
    fields = {key: None for key in _FIELD_KEYS}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()

        if fields["carat"] is None and _CARAT_RE.match(line):
            fields["carat"] = line
            continue

        cc_match = _COLOR_CLARITY_RE.match(upper)
        if fields["color"] is None and cc_match:
            fields["color"], fields["clarity"] = cc_match.group(1), cc_match.group(2)
            continue

        if fields["shape"] is None and upper in SHAPE_WHITELIST:
            fields["shape"] = upper
            continue

        if fields["lot_ref_no"] is None and _LOT_REF_RE.match(upper):
            fields["lot_ref_no"] = upper
            continue

    igi_match = _IGI_CERT_RE.search(raw_text)
    if igi_match:
        fields["igi_report_no"] = igi_match.group(1)

    report_match = _REPORT_TYPE_RE.search(raw_text.upper())
    if report_match:
        fields["report_type"] = report_match.group(1)

    for label, value in _GRADE_LABEL_RE.findall(raw_text):
        key = _GRADE_LABEL_MAP.get(label.upper())
        if key and fields[key] is None:
            fields[key] = value.upper()

    return fields


def _valid_igi(value):
    return bool(value) and bool(re.fullmatch(r"\d{8,10}", value))


def _valid_shape(value):
    return value in SHAPE_WHITELIST


def _valid_carat(value):
    return bool(value) and bool(_CARAT_RE.match(value))


def _valid_color(value):
    return bool(value) and bool(re.fullmatch(r"[D-Z]", value))


def _valid_clarity(value):
    return value in CLARITY_WHITELIST


def _valid_optional_grade(value):
    return value is None or value in GRADE_WHITELIST


def _valid_optional_fluorescence(value):
    return value is None or value in FLUORESCENCE_WHITELIST


def _valid_optional_report_type(value):
    return value is None or value in REPORT_TYPE_WHITELIST


def validate_fields(fields: dict, barcode_value: str | None) -> dict:
    """Return a copy of `fields` with `igi_report_no` overridden by a decoded
    barcode value (authoritative) when available, plus a computed `needs_review`
    flag: True if any critical field is missing/invalid, or if ANY field
    (critical or not) fails its expected format/whitelist check."""
    result = dict(fields)
    if barcode_value:
        result["igi_report_no"] = barcode_value

    checks = {
        "igi_report_no": _valid_igi(result.get("igi_report_no")),
        "shape": _valid_shape(result.get("shape")),
        "carat": _valid_carat(result.get("carat")),
        "color": _valid_color(result.get("color")),
        "clarity": _valid_clarity(result.get("clarity")),
        "cut": _valid_optional_grade(result.get("cut")),
        "polish": _valid_optional_grade(result.get("polish")),
        "symmetry": _valid_optional_grade(result.get("symmetry")),
        "fluorescence": _valid_optional_fluorescence(result.get("fluorescence")),
        "report_type": _valid_optional_report_type(result.get("report_type")),
    }

    critical_missing = any(not checks[field] for field in CRITICAL_FIELDS)
    any_invalid = any(not ok for ok in checks.values())
    result["needs_review"] = bool(critical_missing or any_invalid)
    return result
