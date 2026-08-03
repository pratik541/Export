"""Verbatim label-anchored parser for the IGI Laboratory Grown Diamond Jewelry
Report card. The card is clean printed text, so each field is the text printed
after its label, taken EXACTLY as OCR reads it — no normalization, no whitelist
validation, no fuzzy/guess correction. Only the leading label + separators are
stripped; the value is otherwise kept exactly as OCR read it.

We deliberately do NOT require a ':' separator: on real photos OCR sometimes
drops the colon column, so the value is whatever follows the label on that line
(colon or not)."""
import re

_FIELD_KEYS = ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no")

# Printed label -> field key. Each regex matches the label at the start of a line
# (after any leading punctuation) and captures the REST of the line verbatim as
# the value. Separators between the label and value (spaces, ':', '.', '-') are
# stripped; the captured value is otherwise untouched.
_LABEL_PATTERNS = [
    ("report_no", r"report\s*n[o0]"),
    ("shape_cut", r"shape\s*and\s*cut"),
    ("est_weight", r"est\.?\s*weight"),
    ("color", r"colou?r"),
    ("clarity", r"clarity"),
]
_LABEL_RES = [
    (key, re.compile(r"^[\s.:\-]*" + pat + r"[\s.:\-]*(.*)$", re.IGNORECASE))
    for key, pat in _LABEL_PATTERNS
]

# Style code: after "Style#", grab the first code-looking token — letters then a
# digit (e.g. AFDN352/9) — skipping any stray OCR characters in between.
_STYLE_RE = re.compile(r"style\s*#?[^\n]*?([A-Za-z]{2,}\d[A-Za-z0-9/\-]*)", re.IGNORECASE)


def parse_jewelry(raw_text: str) -> dict:
    """Extract the six jewelry-card fields verbatim. Missing fields are None."""
    fields = {key: None for key in _FIELD_KEYS}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for key, label_re in _LABEL_RES:
            if fields[key] is not None:
                continue
            match = label_re.match(line)
            if match:
                value = match.group(1).strip()
                if value:
                    fields[key] = value
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
