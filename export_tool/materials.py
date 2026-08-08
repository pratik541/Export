"""Fantasy-material-code resolution, item-name construction, and Fantasy
File color normalization -- ported from the source HTML tool's
getFantasyMat/buildItemName/normColorOS.

resolve_fantasy_material is a deliberate, verified reproduction of the
source tool's exact matching behavior, not a looser approximation. An
earlier attempt at this port generalized getFantasyMat's two hardcoded
shortcuts (18KT-white, 14KT-rose) into pure table-driven matching by
compacting whitespace on BOTH sides of the comparison (input and table
`code`). That looked cleaner but silently changed real shipment data: on
the real Data/JNE016 sample, it mapped "14KTY" (9 items, ~20% of the file)
to "14KT" because the table's "14KT Y" entry (WITH a space) matched once
spaces were stripped from both sides -- something the source tool's own
raw (non-compacted) table comparison never does, so "14KTY" ships unmapped
in production today. A human reviewed this discrepancy against the source
tool and decided: reproduce production exactly, table-completeness gaps
and all. So:

- The source tool's two hardcoded shortcut *trigger conditions* (a
  whitespace-compacted substring check for "18KTW" / "14KTR") are kept
  as literal special cases -- there's no way to express them as pure
  table lookups without inventing table rows that don't exist in the
  source ("14KTR" alone, without a trailing "G", must still trigger the
  rose-gold shortcut, matching production).
- Their *output values* are no longer separate hardcoded literals (which
  had a spacing typo on the rose-gold branch -- source-tool problem 4).
  Instead they're looked up from FANTASY_MATERIAL_MAP by exact code match,
  so the table's own correctly-spaced text is what comes back, and editing
  the table would (in principle) also update these two cases.
- The table-lookup loop itself compares the raw (trim+uppercase only,
  spaces intact) input against each table code's raw (trim+uppercase only)
  text -- no whitespace compaction on either side. This is why "14KTY"
  correctly stays unmapped: it has no exact match to the spaced "14KT Y"
  table entry.
- The final fallback returns the raw (trim+uppercase only) input, not a
  compacted form -- matching the source tool's own fallback, which never
  strips internal spaces from the code it echoes back."""
import re
from dataclasses import dataclass

from export_tool import config
from export_tool._util import is_blank

_GRADE_ABBREVIATIONS = {"VS", "SI", "VV", "WS"}

# (compacted substring trigger, table code to look up) -- reproduces the
# source tool's two hardcoded shortcuts. Order matters only in that both
# are checked before the general table lookup.
_SPECIAL_CASE_TRIGGERS = [
    ("18KTW", "18KT WG"),
    ("14KTR", "14KT RG"),
    ("PT", "PT"),
]


@dataclass(frozen=True)
class FantasyMaterial:
    c1: str
    suffix: str
    metal: str


def _compact(value) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def _lookup_by_exact_code(code_upper: str):
    for row in config.FANTASY_MATERIAL_MAP:
        if row["code"].strip().upper() == code_upper:
            return FantasyMaterial(c1=row["c1"], suffix=row["suffix"], metal=row["metal"])
    return None


def resolve_fantasy_material(kt_raw) -> FantasyMaterial:
    raw = "" if is_blank(kt_raw) else str(kt_raw).strip().upper()
    compact = _compact(raw)
    for trigger, table_code in _SPECIAL_CASE_TRIGGERS:
        if trigger in compact:
            match = _lookup_by_exact_code(table_code)
            if match is not None:
                return match
    match = _lookup_by_exact_code(raw)
    if match is not None:
        return match
    return FantasyMaterial(c1=raw, suffix=raw, metal=raw)


def _alpha_prefix(text: str) -> str:
    match = re.match(r"^[A-Za-z]+", text)
    return match.group(0) if match else ""


def build_item_name(parent_style, master_style, suffix: str) -> str:
    parent = str(parent_style or "").strip()
    master = str(master_style or "").strip()
    if not parent or parent.lower() in ("nan", "none"):
        return f"{master}-{suffix}"
    if parent.upper().startswith("FREE-"):
        return f"{parent[5:]}-{suffix}"
    if parent == master:
        return f"{master}-{suffix}"
    if _alpha_prefix(parent) == _alpha_prefix(master):
        return f"{parent}-{suffix}"
    return f"{master}-{suffix}"


def normalize_os_color(color):
    if not config.NORMALIZE_TWO_LETTER_COLOR or is_blank(color):
        return color
    text = str(color)
    if len(text) == 2 and text.isalpha() and text.upper() not in _GRADE_ABBREVIATIONS:
        return f"{text[0]}-{text[1]}"
    return text
