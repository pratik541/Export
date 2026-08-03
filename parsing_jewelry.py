"""Verbatim label-anchored parser for the IGI Laboratory Grown Diamond Jewelry
Report card. The card is clean printed text, so each field is the text printed
after its label, taken EXACTLY as OCR reads it — no normalization, no whitelist
validation, no fuzzy/guess correction. Only surrounding whitespace and the ':'
separator are trimmed."""
import re

_FIELD_KEYS = ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no")

# Printed label -> field key. Matched case-insensitively at the start of a line's
# text (ignoring leading punctuation). The value is everything after the first
# ':' on that line, trimmed.
_LABELS = [
    ("report_no", r"report\s*no"),
    ("shape_cut", r"shape\s*and\s*cut"),
    ("est_weight", r"est\.?\s*weight"),
    ("color", r"colou?r"),
    ("clarity", r"clarity"),
]

_STYLE_RE = re.compile(r"style#?\s*[:\-]?\s*([^\s]+)", re.IGNORECASE)


def _value_after_colon(line: str):
    """Return the trimmed text after the first ':' on the line, or None if there
    is no non-empty value."""
    if ":" not in line:
        return None
    value = line.split(":", 1)[1].strip()
    return value or None


def parse_jewelry(raw_text: str) -> dict:
    """Extract the six jewelry-card fields verbatim. Missing fields are None."""
    fields = {key: None for key in _FIELD_KEYS}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower().lstrip(" .:-")
        for key, label_pattern in _LABELS:
            if fields[key] is None and re.match(label_pattern, lowered):
                fields[key] = _value_after_colon(line)
                break

    style_match = _STYLE_RE.search(raw_text)
    if style_match:
        fields["style_no"] = style_match.group(1)

    return fields


def validate_jewelry_fields(fields: dict) -> dict:
    """Copy of `fields` plus `needs_review` = True if ANY field is blank/missing.
    No format or whitelist checks — a present value is accepted as-is."""
    result = dict(fields)
    result["needs_review"] = any(not result.get(k) for k in _FIELD_KEYS)
    return result
