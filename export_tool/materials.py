"""Fantasy-material-code resolution, item-name construction, and Fantasy
File color normalization -- ported from the source HTML tool's
getFantasyMat/buildItemName/normColorOS.

getFantasyMat's hardcoded 18KT-white/14KT-rose shortcut (which bypassed the
editable material table before ever consulting it, and had a spacing typo
on the rose-gold branch -- source-tool problem 4) is replaced here by a
single exact-match pass against FANTASY_MATERIAL_MAP after
whitespace-compaction, so e.g. "18KTWG" and "18KT WG" both resolve to the
same table row and the table's own text (with correct spacing) is always
what comes back. Real shipment KT codes that aren't in the table at all
(e.g. the abbreviated "18KTY") still fall back to the code itself, exactly
as the source tool did -- that's a table-completeness gap, not the bug
being fixed here."""
import re
from dataclasses import dataclass

from export_tool import config
from export_tool._util import is_blank

_GRADE_ABBREVIATIONS = {"VS", "SI", "VV", "WS"}


@dataclass(frozen=True)
class FantasyMaterial:
    c1: str
    suffix: str
    metal: str


def _compact(value) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def resolve_fantasy_material(kt_raw) -> FantasyMaterial:
    compact_kt = _compact(kt_raw)
    for row in config.FANTASY_MATERIAL_MAP:
        if _compact(row["code"]) == compact_kt:
            return FantasyMaterial(c1=row["c1"], suffix=row["suffix"], metal=row["metal"])
    return FantasyMaterial(c1=compact_kt, suffix=compact_kt, metal=compact_kt)


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
