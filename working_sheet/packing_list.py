"""Parses per-category totals out of the Packing List export .xlsx by
scanning for structural markers (a "[NN] ..." header, a "Total:" piece
breakdown, and a subtotal row identified by which columns are populated) --
not fixed row numbers, since category count and product mix vary between
shipments."""
import re
from io import BytesIO

import openpyxl

# 0-indexed column positions, matching the Packing List export's lettering.
COL_A_SR_NO = 0
COL_E_TOTAL_BREAKDOWN = 4
COL_D_STYLE_NO = 3
COL_F_CATEGORY = 5
COL_G_RITC = 6
COL_H_KT = 7
COL_J_GROSS_WT = 9
COL_K_NET_WT = 10
COL_AA_STONE_WT = 26
COL_AD_FOB_VALUE = 29

_CATEGORY_HEADER_RE = re.compile(r"^\[(\d+)\]\s*(.+)$")
_PIECE_RE = re.compile(r"(\d+)\s+(.+?)\s+\((\w+)\)")
_ABBREVIATIONS = [
    (re.compile(r"LABORATORY GROWN DIAMOND", re.IGNORECASE), "LGD"),
    (re.compile(r"\(MECHANIZED\)", re.IGNORECASE), "(MECH)"),
]


class PackingListParseError(ValueError):
    """Raised when a category block has no identifiable subtotal row."""


def parse_packing_list(file_bytes: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]

    categories = []
    current = None
    for row in ws.iter_rows(values_only=False):
        a_value = row[COL_A_SR_NO].value

        if isinstance(a_value, str):
            header_match = _CATEGORY_HEADER_RE.match(a_value.strip())
            if header_match:
                if current is not None:
                    categories.append(_finalize_category(current))
                current = {
                    "number": int(header_match.group(1)),
                    "header": _normalize_whitespace(header_match.group(2)),
                    "piece_breakdown": None,
                    "ritc": None,
                    "subtotal_row": None,
                }
                continue

        if current is None:
            continue

        if (current["piece_breakdown"] is None and isinstance(a_value, str)
                and a_value.strip() == "Total:"):
            breakdown = row[COL_E_TOTAL_BREAKDOWN].value
            if isinstance(breakdown, str):
                current["piece_breakdown"] = breakdown
            continue

        if current["ritc"] is None and row[COL_G_RITC].value:
            current["ritc"] = str(row[COL_G_RITC].value)

        if _is_subtotal_row(row):
            current["subtotal_row"] = row

    if current is not None:
        categories.append(_finalize_category(current))

    return categories


def _is_subtotal_row(row) -> bool:
    return (
        row[COL_A_SR_NO].value is None
        and row[COL_D_STYLE_NO].value is None
        and row[COL_F_CATEGORY].value is None
        and row[COL_H_KT].value is None
        and row[COL_J_GROSS_WT].value is not None
    )


def _finalize_category(current: dict) -> dict:
    if current["subtotal_row"] is None:
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            "has no identifiable subtotal row."
        )
    row = current["subtotal_row"]
    raw_values = {
        "gross_wt": row[COL_J_GROSS_WT].value,
        "net_wt": row[COL_K_NET_WT].value,
        "stone_wt": row[COL_AA_STONE_WT].value,
        "fob_value": row[COL_AD_FOB_VALUE].value,
    }
    missing = [name for name, value in raw_values.items() if value is None]
    if missing:
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            f"subtotal row is missing: {', '.join(missing)}."
        )
    gross_wt = float(raw_values["gross_wt"])
    net_wt = float(raw_values["net_wt"])
    stone_wt = float(raw_values["stone_wt"])
    fob_value = float(raw_values["fob_value"])
    if gross_wt == 0:
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            "has a zero gross weight; cannot compute unit price."
        )

    pieces = _PIECE_RE.findall(current["piece_breakdown"] or "")
    if current["piece_breakdown"] and not pieces:
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            f"piece breakdown \"{current['piece_breakdown']}\" could not be parsed."
        )
    piece_desc = ", ".join(
        f"{name}-{int(count):02d} {unit.upper()}" for count, name, unit in pieces
    )
    description = (
        f"{_abbreviate(current['header'])}, {piece_desc}, "
        f"NW-{net_wt:.3f} GMS, SW-{stone_wt:.2f} CTS"
    )

    return {
        "number": current["number"],
        "ritc": current["ritc"],
        "description": description,
        "gross_wt": gross_wt,
        "net_wt": net_wt,
        "stone_wt": stone_wt,
        "fob_value": fob_value,
        "unit_price": fob_value / gross_wt,
        "standard_qty": round(gross_wt / 1000, 2),
    }


def _abbreviate(header: str) -> str:
    text = header
    for pattern, replacement in _ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    return _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
