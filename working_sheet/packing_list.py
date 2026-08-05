"""Parses per-category totals out of the Packing List export .xlsx by
scanning for structural markers (a "[NN] ..." header, a "Total:" piece
breakdown, and a subtotal row identified by which columns are populated) --
not fixed row numbers, since category count and product mix vary between
shipments. Data columns (RITC, weights, stone/FOB value) are resolved from
the header row's labels rather than fixed letters: a real export (JNE019)
omitted a blank spacer column present in the original reference file
(JNE016), shifting every column from "Rate $ Per Cts" onward one position
left -- hardcoded column positions broke on it (IndexError), while
label-based resolution tolerates the shift."""
import re
from io import BytesIO

import openpyxl

# Column A always carries the row-type markers ("[NN] ...", "Total:") --
# structural, not a data column, so it's never resolved from a label.
COL_A_SR_NO = 0
# The "Total:" row's piece-count breakdown is always in column E in both
# real exports seen so far; unlike the data columns below, a shift here
# hasn't been observed, so it's left as a fixed position.
COL_E_TOTAL_BREAKDOWN = 4

# label substrings (matched case-insensitively against each header cell,
# whitespace-normalized) -> resolved-column dict key.
_HEADER_LABELS = {
    "style_no": "style no",
    "category": "category",
    "kt": "kt",
    "ritc": "ritc",
    "gross_wt": "gross wt",
    "net_wt": "net wt",
    "stone_wt": "total cts",
    "fob_value": "total fob value",
}

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
    rows = list(ws.iter_rows(values_only=False))

    col = _resolve_columns(_find_header_row(rows))

    categories = []
    current = None
    for row in rows:
        a_value = row[COL_A_SR_NO].value

        if isinstance(a_value, str):
            header_match = _CATEGORY_HEADER_RE.match(a_value.strip())
            if header_match:
                if current is not None:
                    categories.append(_finalize_category(current, col))
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

        if current["ritc"] is None and row[col["ritc"]].value:
            current["ritc"] = str(row[col["ritc"]].value)

        if _is_subtotal_row(row, col):
            current["subtotal_row"] = row

    if current is not None:
        categories.append(_finalize_category(current, col))

    return categories


def _find_header_row(rows):
    for row in rows:
        labels = [_normalize_whitespace(str(c.value)).lower() for c in row if c.value is not None]
        if any("sr no" in label for label in labels) and any("style" in label for label in labels):
            return row
    raise PackingListParseError(
        "Could not find the header row (expecting columns like \"Sr No\" and "
        "\"Style No.\") in this file. Please confirm this is the packing list export."
    )


def _resolve_columns(header_row) -> dict:
    resolved = {}
    missing = []
    for key, pattern in _HEADER_LABELS.items():
        idx = _find_col(header_row, pattern)
        if idx is None:
            missing.append(key)
        else:
            resolved[key] = idx
    if missing:
        raise PackingListParseError(
            "Could not locate column(s) in the header row: " + ", ".join(missing) +
            ". The packing list layout may have changed."
        )
    return resolved


def _find_col(header_row, pattern):
    for idx, cell in enumerate(header_row):
        if cell.value is None:
            continue
        if pattern in _normalize_whitespace(str(cell.value)).lower():
            return idx
    return None


def _is_subtotal_row(row, col) -> bool:
    return (
        row[COL_A_SR_NO].value is None
        and row[col["style_no"]].value is None
        and row[col["category"]].value is None
        and row[col["kt"]].value is None
        and row[col["gross_wt"]].value is not None
    )


def _finalize_category(current: dict, col: dict) -> dict:
    if current["subtotal_row"] is None:
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            "has no identifiable subtotal row."
        )
    if current["ritc"] is None or not current["ritc"].isdigit():
        raise PackingListParseError(
            f"Category [{current['number']:02d}] \"{current['header']}\" "
            f"has an invalid RITC value: {current['ritc']!r}."
        )
    row = current["subtotal_row"]
    raw_values = {
        "gross_wt": row[col["gross_wt"]].value,
        "net_wt": row[col["net_wt"]].value,
        "stone_wt": row[col["stone_wt"]].value,
        "fob_value": row[col["fob_value"]].value,
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
