"""Parses the Packing List export (.xls/.xlsx) into one record per item
(style), with nested stone lines -- unlike working_sheet/packing_list.py,
which parses the same kind of file into one record per *category block*
(the Fantasy File needs per-item detail, not per-category totals). Column
resolution is header-label-driven, not fixed-position, following the same
approach proven in working_sheet/packing_list.py against real ERP exports
whose column positions shift between shipments."""
import re
from io import BytesIO

import openpyxl

from export_tool import config, stones
from export_tool._util import is_blank, safe_num

_HEADER_LABELS = {
    "sr", "sr.", "style no", "style no.", "lab", "laboratory",
    "certificate no", "certificate no.", "certi no", "certino",
    "shape/color clarity", "stn pcs", "stn cts",
    "qty", "gross wt in gms", "total metal wt. gms",
}
_ITEM_LABEL_FIELDS = ["sn", "cat", "kt", "lab", "cert", "stud", "scc", "stnpcs", "stncts"]
_STONE_LABEL_FIELDS = ["lab", "cert", "stud", "scc", "stnpcs", "stncts"]


class PackingListParseError(ValueError):
    """Raised when the packing list's structure can't be understood."""


def parse_packing_list(file_bytes: bytes) -> tuple:
    workbook = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    sheet = workbook.worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))

    columns, warnings = _resolve_columns(_find_header_row(rows))

    items = []
    current = None
    merge_categories = {c.strip().upper() for c in config.MERGE_CATEGORIES}

    for row in rows:
        sr_int = _parse_sr(_cell(row, columns, "sr"))
        style_no = _clean_str(_cell(row, columns, "sn"))
        is_data_row = sr_int is not None and style_no and not _is_label_row(row, columns, _ITEM_LABEL_FIELDS)

        if is_data_row:
            new_item = {
                "sr": sr_int, "sn": style_no,
                "cat": _clean_str(_cell(row, columns, "cat")),
                "kt": _clean_str(_cell(row, columns, "kt")),
                "qty": safe_num(_cell(row, columns, "qty")),
                "gw": safe_num(_cell(row, columns, "gw")),
                "tmw": safe_num(_cell(row, columns, "tmw")),
                "mv": safe_num(_cell(row, columns, "mv")),
                "making": safe_num(_cell(row, columns, "making")),
                "cert": _clean_str(_cell(row, columns, "cert")),
                "stones": [],
            }
            stone = _make_stone(row, columns)
            if stone:
                new_item["stones"].append(stone)

            is_sub_item = (new_item["cat"] or "").strip().upper() in merge_categories
            if is_sub_item and current is not None:
                current["gw"] = (current["gw"] or 0) + (new_item["gw"] or 0)
                current["tmw"] = (current["tmw"] or 0) + (new_item["tmw"] or 0)
                current["mv"] = (current["mv"] or 0) + (new_item["mv"] or 0)
                current["making"] = (current["making"] or 0) + (new_item["making"] or 0)
                current["stones"].extend(new_item["stones"])
            else:
                if current is not None:
                    items.append(current)
                current = new_item
        elif current is not None:
            stone = _make_stone(row, columns)
            if stone:
                current["stones"].append(stone)

    if current is not None:
        items.append(current)

    return items, warnings


def _normalize_header(value) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\r?\n", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _find_header_row(rows):
    for row in rows:
        labels = [_normalize_header(v) for v in row if v is not None]
        if any("sr no" in label for label in labels) and any("style" in label for label in labels):
            return row
    raise PackingListParseError(
        'Could not find the header row (expecting columns like "Sr No" and '
        '"Style No.") in this file. Please confirm this is the packing list export.'
    )


def _resolve_columns(header_row):
    lookup = {_normalize_header(v): idx for idx, v in enumerate(header_row) if v is not None}
    columns = {}
    warnings = []
    for key, header_text in config.PACK_COLUMN_HEADERS.items():
        idx = lookup.get(_normalize_header(header_text))
        if idx is None:
            warnings.append(f'Column not found in file: "{header_text}" ({key}) -- check export_tool/config.py')
        else:
            columns[key] = idx
    if "sr" not in columns or "sn" not in columns:
        raise PackingListParseError(
            "Could not locate the Sr No / Style No. columns needed to identify item rows. "
            "The packing list layout may have changed -- check export_tool/config.py."
        )
    return columns, warnings


def _cell(row, columns, key):
    idx = columns.get(key)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _clean_str(value):
    return None if is_blank(value) else str(value).strip()


def _parse_sr(value):
    if is_blank(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number != int(number):
        return None
    return int(number)


def _is_label_row(row, columns, fields) -> bool:
    for field in fields:
        value = _cell(row, columns, field)
        if value is not None and _normalize_header(value) in _HEADER_LABELS:
            return True
    return False


def _split_scc(scc):
    if is_blank(scc):
        return None, None, None
    parts = (str(scc).strip().split("-") + [None, None, None])[:3]
    return parts[0] or None, parts[1] or None, parts[2] or None


def _make_stone(row, columns):
    scc = _cell(row, columns, "scc")
    if is_blank(scc):
        return None
    if _is_label_row(row, columns, _STONE_LABEL_FIELDS):
        return None
    cert = _clean_str(_cell(row, columns, "cert"))
    pcs = safe_num(_cell(row, columns, "stnpcs"))
    position = stones.classify_position(cert, pcs)
    shape, color, clarity = _split_scc(scc)
    stud = _clean_str(_cell(row, columns, "stud"))
    label = re.sub(r"\s*\(.*?\)", "", stud).strip() if stud else ""
    return {
        "position": position, "label": label or config.STONE_FALLBACK_LABEL,
        "shape": shape, "color": color, "clarity": clarity,
        "lab": _clean_str(_cell(row, columns, "lab")),
        "cert": cert,
        "cts": safe_num(_cell(row, columns, "stncts")),
        "pcs": pcs,
        "val": safe_num(_cell(row, columns, "val")),
    }
