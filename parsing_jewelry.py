"""Parser for the IGI Laboratory Grown Diamond Jewelry Report card.

Real phone photos of this card do NOT OCR as clean "Label : value" lines. The
two-column layout makes PaddleOCR zipper adjacent labels and values together on
one line ("Shape and Cut Est, Weight : (1) Oval Brilliant : 0.54 Carat",
"Clarity Color : V5 :E-F"), and OCR sometimes misreads the label words
themselves ("Style#" -> "Stylo#" / "Shyios") or individual characters inside a
value ("VS" -> "V5").

So we LOCATE each field's value by POSITION (which label came first on a
zippered line determines which colon-separated slot is its value) rather than
by matching label spelling or validating value spelling against a whitelist —
validating spelling caused a real failure (clarity "V5" didn't match the "VS"
whitelist and was dropped). Once located, the value is stored EXACTLY as OCR
produced it -- no reformatting, no spelling correction, no guessing."""
import re

_FIELD_KEYS = ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no")


def _value_between_colons_after(pos: int, line: str):
    """Text after position `pos` on `line`, taking the slice between the first
    and second ':' if a second one exists (this drops any label text a zippered
    line injects before the real value's colon), else everything after the
    first ':', else the whole remainder (no colon at all -> old plain layout)."""
    rest = line[pos:]
    if ":" in rest:
        after_first = rest.split(":", 1)[1]
        value = after_first.split(":", 1)[0] if ":" in after_first else after_first
    else:
        value = rest
    value = value.strip(" .:-")
    return value or None


def _extract_after_label(raw_text: str, label_pattern: str):
    """Find a line containing `label_pattern` and return the value located via
    _value_between_colons_after right after the label match."""
    label_re = re.compile(label_pattern, re.IGNORECASE)
    for line in raw_text.splitlines():
        match = label_re.search(line)
        if match:
            value = _value_between_colons_after(match.end(), line)
            if value:
                return value
    return None


def _extract_clarity_and_color(raw_text: str):
    """The card zippers these onto one line: 'Clarity Color : <clarity> :<color>'
    (label order matches value order). Locate by POSITION -- whichever label
    comes first on the line determines which colon-slot is its value -- so an
    OCR misread inside the value (e.g. "VS" -> "V5") never blocks extraction."""
    for line in raw_text.splitlines():
        lower = line.lower()
        clarity_pos = lower.find("clarity")
        color_pos = lower.find("colou")
        if color_pos == -1:
            color_pos = lower.find("color")
        if clarity_pos == -1 or color_pos == -1:
            continue
        parts = line.split(":")
        if len(parts) < 3:
            continue
        first_value = parts[1].strip(" .:-") or None
        second_value = parts[2].strip(" .:-") or None
        if clarity_pos < color_pos:
            return first_value, second_value
        return second_value, first_value
    return None, None


# Report number: a 10-14 char alphanumeric run containing at least one digit
# (e.g. 45J331632607), found shortly after the "Report No" label if possible
# (bounded window, since the value can be far away on a zippered/merged line),
# else the first such run anywhere in the text.
_REPORTNO_TOKEN = r"\b(?=[0-9A-Za-z]*\d)[0-9A-Za-z]{10,14}\b"
_REPORTNO_ANCHORED = re.compile(
    r"report\s*n[o0][\s\S]{0,140}?(" + _REPORTNO_TOKEN + r")", re.IGNORECASE
)
_REPORTNO_GLOBAL = re.compile("(" + _REPORTNO_TOKEN + ")")

# Est. Weight: the carat value has a distinctive numeric shape ("0.56 Carat"),
# so it's found directly regardless of which label it's zippered against.
_WEIGHT_PATTERN_RE = re.compile(r"(\d+\.\d{1,2}\s*carat)", re.IGNORECASE)

# Style code: a real IGI style code looks like AFDN352/9 -- a few uppercase
# letters, then digits, optionally a slash and more digits. The "Style#" label
# itself is frequently misread beyond recognition ("Stylo#", "Shyios"), so the
# code's own shape is the reliable anchor; a nearby-label match is tried first
# for extra precision when the label happens to be legible.
_STYLE_CODE_TOKEN = r"\b[A-Za-z]{2,5}\d{2,4}(?:/\d{1,3})?\b"
_STYLE_ANCHORED = re.compile(
    r"styl\w*\s*#?[^\n]{0,20}?(" + _STYLE_CODE_TOKEN + r")", re.IGNORECASE
)
_STYLE_GLOBAL = re.compile("(" + _STYLE_CODE_TOKEN + ")")


def _first_group(regex, text):
    match = regex.search(text)
    return match.group(1).strip() if match else None


def parse_jewelry(raw_text: str) -> dict:
    """Extract the six jewelry-card fields (verbatim values). Missing fields None."""
    fields = {key: None for key in _FIELD_KEYS}

    fields["report_no"] = (_first_group(_REPORTNO_ANCHORED, raw_text)
                           or _first_group(_REPORTNO_GLOBAL, raw_text))
    fields["shape_cut"] = _extract_after_label(raw_text, r"shape\s*and\s*cut")
    fields["est_weight"] = (_first_group(_WEIGHT_PATTERN_RE, raw_text)
                            or _extract_after_label(raw_text, r"est\.?\s*weight"))

    clarity, color = _extract_clarity_and_color(raw_text)
    fields["clarity"] = clarity or _extract_after_label(raw_text, r"clarity")
    fields["color"] = color or _extract_after_label(raw_text, r"colou?r")

    fields["style_no"] = (_first_group(_STYLE_ANCHORED, raw_text)
                          or _first_group(_STYLE_GLOBAL, raw_text))

    return fields


def validate_jewelry_fields(fields: dict) -> dict:
    """Copy of `fields` plus `needs_review` = True if ANY field is blank/missing.
    No format or whitelist checks — a present value is accepted as-is."""
    result = dict(fields)
    result["needs_review"] = any(not result.get(k) for k in _FIELD_KEYS)
    return result
