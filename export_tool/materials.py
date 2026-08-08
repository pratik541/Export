"""Fantasy-material-code resolution, item-name construction, and Fantasy
File color normalization -- ported from the source HTML tool's
getFantasyMat/buildItemName/normColorOS.

resolve_fantasy_material's matching logic went through two corrections
after being checked against real data, in order:

1. An early version generalized getFantasyMat's hardcoded shortcuts into
   pure table-driven matching by compacting whitespace on BOTH sides of
   the comparison (input and table `code`). That silently changed real
   shipment data (mapped "14KTY" to "14KT" because the table's "14KT Y"
   entry matched once spaces were stripped from both sides, something the
   source tool's raw table comparison never does) -- reverted to reproduce
   the source HTML file's exact default behavior instead.
2. That "exact default behavior" was then checked against a real reference
   "Open Stock" file (Data/JNE016 Open Stock.xls, local-only, real business
   data) and found to disagree with what this business's actual live tool
   produces on most of a real shipment's KT codes -- e.g. the source file's
   hardcoded "14KTR" -> "14KT RG" shortcut doesn't match a single real
   "14KTR" row (real output: "14KR"). The likely explanation: the source
   tool's material tables live in browser localStorage, editable via a
   Settings UI this port doesn't have (decision 1) -- the HTML file's
   *defaults* aren't necessarily what this business's *live, presumably
   customized* config actually contains. FANTASY_MATERIAL_MAP now reflects
   the real reference file's output (see its comment for exactly which
   rows), and the "14KTR" hardcoded trigger was removed since "14KTR" is
   now a plain table row.

What's left:
- One hardcoded shortcut *trigger condition* remains ("18KTW", a
  whitespace-compacted substring check) -- there's no real-shipment
  evidence either confirming or contradicting it (no "18KTW"-shaped code
  appeared in the one real file checked), so it's kept as the source
  file's default, unverified against production.
- The "PT" trigger's *output values* are looked up from
  FANTASY_MATERIAL_MAP by exact code match rather than hardcoded, so
  editing the table also updates it.
- The table-lookup loop compares the raw (trim+uppercase only, spaces
  intact) input against each table code's raw (trim+uppercase only) text
  -- no whitespace compaction on either side, matching the source tool.
- The final fallback returns the raw (trim+uppercase only) input, not a
  compacted form -- matching the source tool's own fallback, which never
  strips internal spaces from the code it echoes back."""
import re
from dataclasses import dataclass

from export_tool import config
from export_tool._util import is_blank

_GRADE_ABBREVIATIONS = {"VS", "SI", "VV", "WS"}

# (compacted substring trigger, table code to look up) -- reproduces the
# source tool's remaining hardcoded shortcuts (see module docstring for why
# "14KTR" isn't one of these anymore). Order matters only in that both are
# checked before the general table lookup.
_SPECIAL_CASE_TRIGGERS = [
    ("18KTW", "18KT WG"),
    ("PT", "PT"),
]


@dataclass(frozen=True)
class FantasyMaterial:
    c1: str
    suffix: str
    metal: str
    # False only for the final raw-passthrough fallback -- lets callers warn
    # when a KT code isn't recognized by any table row or special case,
    # instead of silently shipping the raw code through unmapped.
    matched: bool = True


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
    return FantasyMaterial(c1=raw, suffix=raw, metal=raw, matched=False)


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
