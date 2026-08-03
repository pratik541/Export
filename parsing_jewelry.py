"""Parser for the IGI Laboratory Grown Diamond Jewelry Report card.

Real phone photos of this card do NOT OCR as clean "Label : value" lines. The
two-column layout makes PaddleOCR merge labels and values across columns and
rows: the Report No. value lands at the end of the Description line, and Color's
and Clarity's values collapse onto a single line ("Clarity Color : VS :E-F").
So pure "text after the label" parsing cannot separate them.

Instead we LOCATE each field's value by anchoring on its label where the line is
clean (Shape and Cut, Est. Weight) and by the value's own distinctive shape
where the columns are jumbled (report number, colour range, clarity grade, style
code). We only LOCATE the value — the stored string is exactly what OCR produced
(no reformatting, no whitelist correction, no guessing at the characters)."""
import re

_FIELD_KEYS = ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no")

# Report number: a 10-14 char alphanumeric run containing at least one digit
# (e.g. 45J331632607). Prefer one shortly after the "Report No" label; otherwise
# the first such run anywhere in the text.
_REPORTNO_TOKEN = r"\b(?=[0-9A-Za-z]*\d)[0-9A-Za-z]{10,14}\b"
_REPORTNO_ANCHORED = re.compile(
    r"report\s*n[o0][\s\S]{0,140}?(" + _REPORTNO_TOKEN + r")", re.IGNORECASE
)
_REPORTNO_GLOBAL = re.compile("(" + _REPORTNO_TOKEN + ")")

# Clean labelled lines: capture the rest of the line after the label (the ':' is
# optional because OCR sometimes drops it).
_SHAPE_RE = re.compile(r"shape\s*and\s*cut\s*[:.\-]*\s*([^\n]+)", re.IGNORECASE)
_WEIGHT_LABEL_RE = re.compile(r"est\.?\s*weight\s*[:.\-]*\s*([^\n]+)", re.IGNORECASE)
# Prefer the carat value pattern (avoids grabbing the pendant's total gram weight
# from the Description line, which is not followed by "carat").
_WEIGHT_PATTERN_RE = re.compile(r"(\d+\.\d{1,2}\s*carat)", re.IGNORECASE)

# Colour: a diamond colour grade range within D..Z (e.g. "E - F" or "E-F").
_COLOR_RE = re.compile(r"([D-Z]\s*[-–]\s*[D-Z])")
# Clarity: a standard grade token (longest alternatives first so VVS beats VS).
_CLARITY_RE = re.compile(r"\b(FL|IF|VVS[12]?|VS[12]?|SI[123]?|I[123])\b", re.IGNORECASE)
# Style code after a "Styl..." label (tolerates the "Stylo#" OCR misread); the
# code looks like AFDN352/9 — letters then a digit — with any stray chars skipped.
_STYLE_RE = re.compile(
    r"styl\w*\s*#?[^\n]*?([A-Za-z]{2,}\d[A-Za-z0-9/\-]*)", re.IGNORECASE
)


def _first_group(regex, text):
    match = regex.search(text)
    return match.group(1).strip() if match else None


def parse_jewelry(raw_text: str) -> dict:
    """Extract the six jewelry-card fields (verbatim values). Missing fields None."""
    fields = {key: None for key in _FIELD_KEYS}

    fields["report_no"] = (_first_group(_REPORTNO_ANCHORED, raw_text)
                           or _first_group(_REPORTNO_GLOBAL, raw_text))
    fields["shape_cut"] = _first_group(_SHAPE_RE, raw_text)
    fields["est_weight"] = (_first_group(_WEIGHT_PATTERN_RE, raw_text)
                            or _first_group(_WEIGHT_LABEL_RE, raw_text))
    fields["color"] = _first_group(_COLOR_RE, raw_text)
    fields["clarity"] = _first_group(_CLARITY_RE, raw_text)
    fields["style_no"] = _first_group(_STYLE_RE, raw_text)

    return fields


def validate_jewelry_fields(fields: dict) -> dict:
    """Copy of `fields` plus `needs_review` = True if ANY field is blank/missing.
    No format or whitelist checks — a present value is accepted as-is."""
    result = dict(fields)
    result["needs_review"] = any(not result.get(k) for k in _FIELD_KEYS)
    return result
