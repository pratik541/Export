import re

SHAPE_WHITELIST = {
    "ROUND", "EMERALD", "OVAL", "PEAR", "CUSHION", "PRINCESS",
    "RADIANT", "HEART", "MARQUISE", "ASSCHER",
}
# Known systematic OCR misreads mapped back to their canonical shape name.
# "MAROUISE" (Q misread as O) was seen on a real tag photo.
SHAPE_OCR_ALIASES = {"MAROUISE": "MARQUISE"}
CLARITY_WHITELIST = {
    "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "SI3", "I1", "I2", "I3",
}
REPORT_TYPE_WHITELIST = {"CVD", "HPHT", "NATURAL", "TREATED"}

CRITICAL_FIELDS = ("igi_report_no", "shape", "carat", "color", "clarity", "report_type")

_CARAT_RE = re.compile(r"(?<!\d)(\d+\.\d{2})(?!\d)")
_COLOR_CLARITY_RE = re.compile(
    r"([D-Z])\s+(FL|IF|VVS1|VVS2|VS1|VS2|SI1|SI2|SI3|I1|I2|I3)$"
)
_IGI_CERT_RE = re.compile(r"IGI\s*CERT\s*-?\s*(\d{8,10})", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z]+")

_FIELD_KEYS = ("igi_report_no", "report_type", "shape", "carat", "color", "clarity")


def _within_one_edit(a: str, b: str) -> bool:
    """True if `a` can be turned into `b` with at most one character
    insertion, deletion, or substitution."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))


def _find_report_type(raw_text: str) -> str | None:
    # "CVD" is only 3 characters, so a single OCR misread (seen on real tag
    # photos as both "CVVD" and "CVB") makes an exact match fail entirely.
    # Rather than exact-match the word right after "REPORT", accept it if
    # it's within one edit of a known report type -- scoped to just the word
    # immediately following the "REPORT" label, so unrelated OCR noise
    # elsewhere in the text can't be mistaken for one.
    words = _WORD_RE.findall(raw_text)
    for i, word in enumerate(words):
        if word.upper() != "REPORT":
            continue
        for candidate in words[i + 1 : i + 3]:
            upper_candidate = candidate.upper()
            for canonical in REPORT_TYPE_WHITELIST:
                if _within_one_edit(upper_candidate, canonical):
                    return canonical
    return None


def parse_fields(raw_text: str) -> dict:
    """Parse raw OCR text from an IGI tag into structured fields via per-line and
    whole-text regex/keyword matching. Missing fields are None."""
    fields = {key: None for key in _FIELD_KEYS}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()

        carat_match = _CARAT_RE.search(line)
        if fields["carat"] is None and carat_match:
            fields["carat"] = carat_match.group(1)
            continue

        cc_match = _COLOR_CLARITY_RE.search(upper)
        if fields["color"] is None and cc_match:
            fields["color"], fields["clarity"] = cc_match.group(1), cc_match.group(2)
            continue

        if fields["shape"] is None:
            candidates = (SHAPE_OCR_ALIASES.get(token, token) for token in re.findall(r"[A-Z]+", upper))
            shape_tokens = [token for token in candidates if token in SHAPE_WHITELIST]
            if shape_tokens:
                fields["shape"] = shape_tokens[0]
                continue

    igi_match = _IGI_CERT_RE.search(raw_text)
    if igi_match:
        fields["igi_report_no"] = igi_match.group(1)

    fields["report_type"] = _find_report_type(raw_text)

    return fields


def _valid_igi(value):
    return bool(value) and bool(re.fullmatch(r"\d{8,10}", value))


def _valid_shape(value):
    return value in SHAPE_WHITELIST


def _valid_carat(value):
    return bool(value) and bool(re.fullmatch(r"\d+\.\d{2}", value))


def _valid_color(value):
    return bool(value) and bool(re.fullmatch(r"[D-Z]", value))


def _valid_clarity(value):
    return value in CLARITY_WHITELIST


def _valid_report_type(value):
    return value in REPORT_TYPE_WHITELIST


def validate_fields(fields: dict, barcode_value: str | None) -> dict:
    """Return a copy of `fields` with `igi_report_no` overridden by a decoded
    barcode value (authoritative) when available, plus a computed `needs_review`
    flag: True if any field is missing or fails its expected format/whitelist
    check. Every field here is critical -- this app only tracks the fields the
    user actually needs (IGI number, shape, carat, color, clarity, report type)."""
    result = dict(fields)
    if barcode_value:
        result["igi_report_no"] = barcode_value

    checks = {
        "igi_report_no": _valid_igi(result.get("igi_report_no")),
        "shape": _valid_shape(result.get("shape")),
        "carat": _valid_carat(result.get("carat")),
        "color": _valid_color(result.get("color")),
        "clarity": _valid_clarity(result.get("clarity")),
        "report_type": _valid_report_type(result.get("report_type")),
    }

    result["needs_review"] = any(not ok for ok in checks.values())
    return result
