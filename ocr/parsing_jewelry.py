"""Parser for the IGI Laboratory Grown Diamond Jewelry Report card.

Real phone photos of this card do NOT OCR as clean "Label : value" lines, and
NEITHER the label text NOR the value order is reliable across different scans of
the same card:
  - Labels zipper together on one line in either order ("Shape and Cut Est,
    Weight : v1 : v2" one scan, "Est. Woiolt Shape and Cut : v1 : v2" another).
  - The VALUE order on a zippered line does not always match the label order
    (Clarity/Color values have been seen in both orders across scans).
  - Label AND unit words themselves get misread ("Style#" -> "Shyios", "Weight"
    -> "Woiolt", "Carat" -> "Corat").

So fields are located either (a) by the field's OWN label when it happens to be
legible plus its position on the line (not by the OTHER label's spelling), or
(b) by the VALUE's own distinctive shape (digit run, colour range, carat
number), never by matching a value against a fixed whitelist of spellings. Once
located, the value is stored EXACTLY as OCR produced it -- no reformatting, no
spelling correction, no guessing.

The one exception is LABEL matching for "clarity" (see _fuzzy_label_span):
fuzzy string matching is used to find where that label is on a line despite
misreads, because it has no shape/position fallback the way color/report_no/
style_no do. This never touches the VALUE -- it only decides where to start
slicing, and the slice itself is still returned verbatim."""
import re

from rapidfuzz import fuzz

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
    _value_between_colons_after right after the label match. Order-independent:
    it only looks at what follows the label's OWN match position, so it doesn't
    matter whether some other label was zippered in before it on the line."""
    label_re = re.compile(label_pattern, re.IGNORECASE)
    for line in raw_text.splitlines():
        match = label_re.search(line)
        if match:
            value = _value_between_colons_after(match.end(), line)
            if value:
                return value
    return None


def _last_colon_value(raw_text: str, label_pattern: str):
    """On the line containing `label_pattern`, return the text after the LAST
    ':' on that line. Used as a last-resort positional fallback for a field
    whose own label/unit word got misread: on a two-value zippered line, once
    the OTHER field's value has been claimed from the middle slot, whatever
    follows the final colon is this field's value -- located by position on the
    line, not by this field's own (possibly garbled) label spelling."""
    label_re = re.compile(label_pattern, re.IGNORECASE)
    for line in raw_text.splitlines():
        if label_re.search(line) and line.count(":") >= 2:
            value = line.rsplit(":", 1)[1].strip(" .:-")
            if value:
                return value
    return None


def _fuzzy_label_span(line: str, label: str, threshold: float = 80):
    """Return the (start, end) span of the word in `line` that best fuzzy-
    matches `label` (case-insensitive whole-word similarity), or None if
    nothing on the line scores at/above `threshold`. Checked against every
    word actually seen across the real-scan test fixtures: the one observed
    misread ("Clarity" -> "Clarty") scores 92.3, the next-highest unrelated
    word ("Carat") scores 66.7 -- 80 sits in the middle of that gap. Only
    ever used to locate a label; the value that follows is still sliced out
    positionally and returned verbatim."""
    best_span, best_score = None, 0
    for match in re.finditer(r"[A-Za-z]+", line):
        score = fuzz.ratio(match.group().lower(), label)
        if score > best_score and score >= threshold:
            best_score = score
            best_span = (match.start(), match.end())
    return best_span


_CLARITY_GRADE_TOKEN = r"(?:FL|IF|VVS[12]?|VS[12]?|SI[123]?|I[123])"
_CLARITY_SHAPE_RE = re.compile(
    r"^\s*" + _CLARITY_GRADE_TOKEN + r"(?:\s*[-–]\s*" + _CLARITY_GRADE_TOKEN + r")?\s*$",
    re.IGNORECASE,
)


def _looks_like_clarity_shape(value):
    """A clarity value is a single standard grade (FL, IF, VVS1, VVS2, VS1,
    VS2, SI1, SI2, SI3, I1, I2, I3) or a trade-range combining two of them
    with a dash (e.g. "VVS-VS", parcel/melee grading) -- the WHOLE (stripped)
    value, same anchoring reasoning as _looks_like_color_range."""
    return bool(value) and bool(_CLARITY_SHAPE_RE.match(value.strip()))


def _extract_clarity_fuzzy(raw_text: str):
    """Fallback for clarity when it isn't found zippered with color on one
    line: fuzzy-match the "clarity" label word on each line. Unrelated text
    can land between the label's own colon and the real value's colon (e.g.
    the Comments field's boilerplate getting zippered in when its own label
    is lost: "Clarity : Grading & Identification ... : VVs-VS"), so prefer
    whichever colon-delimited segment after the label actually looks like a
    clarity grade/trade-range shape over the plain positional slice."""
    for line in raw_text.splitlines():
        span = _fuzzy_label_span(line, "clarity")
        if span:
            segments = [s.strip(" .:-") for s in line[span[1]:].split(":")]
            shaped = next((s for s in segments if _looks_like_clarity_shape(s)), None)
            if shaped:
                return shaped
            value = _value_between_colons_after(span[1], line)
            if value:
                return value
    return None


def _looks_like_color_range(value):
    """A colour grade range is the WHOLE value being two single letters
    joined by a dash (e.g. 'E-F', 'E - F'), regardless of OCR noise on the
    letters themselves. Anchored to the full (stripped) value, not a
    substring search: a clarity trade-range like "VVS-VS" or "SI-I" (parcel/
    melee grading -- see the clarity grade list below) contains a hidden
    single-letter-dash-single-letter substring ("S-V" inside "VVS-VS") that a
    plain substring search used to false-positive on, making the clarity/
    color swap-decision below ambiguous and fall back to fragile label-order
    guessing."""
    return bool(value) and bool(re.fullmatch(r"[A-Za-z]\s*[-–]\s*[A-Za-z]", value.strip()))


# Colour value's own shape, searched globally: a colour grade range is a
# standalone single letter, a dash, and another standalone single letter (the
# \b...\b keeps this from matching letters inside an ordinary hyphenated word).
# This has been observed zippered against EITHER "Clarity" or "Est. Weight"
# depending on the scan, so locating it by its own shape -- rather than by
# whichever label it happens to be paired with that time -- is what's reliable.
_COLOR_SHAPE_RE = re.compile(r"(\b[A-Za-z]\s*[-–]\s*[A-Za-z]\b)")


def _extract_clarity_and_color(raw_text: str):
    """The card zippers these onto one line: 'Clarity Color : <v1> :<v2>'. Which
    of v1/v2 is the colour value is decided by SHAPE (colour is a letter-dash-
    letter range) rather than by label print order, because the value order on
    this line has been observed to NOT always match the label order across
    different scans. Falls back to label-print order only when neither/both
    values look like a colour range. Clarity's position is found via
    _fuzzy_label_span so a misread label ("Clarity" -> "Clarty") doesn't
    break the label-order tiebreaker."""
    for line in raw_text.splitlines():
        lower = line.lower()
        clarity_span = _fuzzy_label_span(line, "clarity")
        clarity_pos = clarity_span[0] if clarity_span else -1
        color_pos = lower.find("colou")
        if color_pos == -1:
            color_pos = lower.find("color")
        if clarity_pos == -1 or color_pos == -1:
            continue
        parts = line.split(":")
        if len(parts) < 3:
            continue
        candidates = [parts[1].strip(" .:-") or None, parts[2].strip(" .:-") or None]
        is_color_shaped = [_looks_like_color_range(v) for v in candidates]
        if is_color_shaped[0] and not is_color_shaped[1]:
            return candidates[1], candidates[0]        # clarity, color
        if is_color_shaped[1] and not is_color_shaped[0]:
            return candidates[0], candidates[1]
        # Ambiguous (both or neither look like a colour range) -> label order.
        if clarity_pos < color_pos:
            return candidates[0], candidates[1]
        return candidates[1], candidates[0]
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

# Est. Weight: the carat value has a distinctive numeric shape ("0.56 Carat" or
# the plural "3.24 Carats" for a multi-stone total), so it's usually found
# directly regardless of which label it's zippered against, unless "Carat"
# itself is misread (see the positional fallback below).
_WEIGHT_PATTERN_RE = re.compile(r"(\d+\.\d{1,2}\s*carats?)", re.IGNORECASE)

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
    fields["est_weight"] = (
        _first_group(_WEIGHT_PATTERN_RE, raw_text)
        or _extract_after_label(raw_text, r"est\.?\s*weight")
        or _last_colon_value(raw_text, r"shape\s*and\s*cut")
    )

    clarity, color = _extract_clarity_and_color(raw_text)
    fields["clarity"] = clarity or _extract_clarity_fuzzy(raw_text)
    fields["color"] = (_first_group(_COLOR_SHAPE_RE, raw_text)
                       or color or _extract_after_label(raw_text, r"colou?r"))

    fields["style_no"] = (_first_group(_STYLE_ANCHORED, raw_text)
                          or _first_group(_STYLE_GLOBAL, raw_text))

    return fields


def validate_jewelry_fields(fields: dict) -> dict:
    """Copy of `fields` plus `needs_review` = True if ANY field is blank/missing.
    No format or whitelist checks — a present value is accepted as-is."""
    result = dict(fields)
    result["needs_review"] = any(not result.get(k) for k in _FIELD_KEYS)
    return result
