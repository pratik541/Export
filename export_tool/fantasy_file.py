"""Builds and writes the Fantasy File (the source HTML tool's "Open Stock"
export, renamed per user decision) -- a wide layout with fixed C1/C2 metal+
labor slots and 20 further stone slots (C3-C22). Column layout and header
text are dictated by the receiving system and are NOT configurable."""
from export_tool import config, materials, stones
from export_tool._util import is_blank, master_style, safe_num

MAX_SLOTS = 22

_CORE_COLUMNS = [
    "PO Doc ID", "PO Doc Line", "Item Name", "LotName", "Metal", "Order #",
    "Qty", "Weight", " Total H.Cost", "ItemTypeID",
    "C1:Item Name", "C1:LotName", "C1:Weight", "C1: Total H.Cost",
    "C2:Item Name", "C2:LotName", "C2: Qty", "C2: Total H.Cost",
]


def _stone_columns(slot: int) -> list:
    position_col = f"C{slot}: Stone Position" if slot == 3 else f"C{slot}:Stone Position"
    return [
        f"C{slot}:Item Name", f"C{slot}:LotName", f"C{slot}: Qty", f"C{slot}:Weight",
        f"C{slot}:Shape", f"C{slot}:Color", f"C{slot}:Clarity", f"C{slot}: Lab",
        f"C{slot}:Cert#", f"C{slot}: Total H.Cost", position_col,
    ]


FANTASY_COLUMNS = list(_CORE_COLUMNS)
for _slot in range(3, MAX_SLOTS + 1):
    FANTASY_COLUMNS.extend(_stone_columns(_slot))

_NUMERIC_COLUMNS = {
    "Qty", "Weight", " Total H.Cost", "ItemTypeID",
    "C1:Weight", "C1: Total H.Cost", "C2: Qty", "C2: Total H.Cost",
}
for _slot in range(3, MAX_SLOTS + 1):
    _NUMERIC_COLUMNS.update({f"C{_slot}: Qty", f"C{_slot}:Weight", f"C{_slot}: Total H.Cost"})

_AVAILABLE_SLOTS = MAX_SLOTS - 3 + 1


def build_rows(items: list, jobsheet_index: dict) -> tuple:
    rows = []
    warnings = []
    no_side_categories = {c.strip().upper() for c in config.NO_SIDE_DIAMOND_CATEGORIES}

    for item in items:
        style_no = item["sn"]
        jobsheet_row = (
            jobsheet_index.get(style_no)
            or jobsheet_index.get(master_style(style_no))
            or {}
        )
        fantasy = materials.resolve_fantasy_material(item["kt"])
        design_no = _jobsheet_value(jobsheet_row, config.JOBSHEET_COLUMNS["design_no"])
        parent_style = _jobsheet_value(jobsheet_row, config.JOBSHEET_COLUMNS["parent_style"])

        groups = stones.aggregate(item["stones"])
        if (item["cat"] or "").strip().upper() in no_side_categories:
            groups = [g for g in groups if g["position"] == "center"]

        row = {column: None for column in FANTASY_COLUMNS}
        row["Item Name"] = materials.build_item_name(parent_style, master_style(style_no), fantasy.suffix)
        row["LotName"] = (
            _jobsheet_value(jobsheet_row, config.JOBSHEET_COLUMNS["setting_cert"])
            or item["cert"]
            or _first_stone_cert(item["stones"])
            or style_no
        )
        row["Metal"] = fantasy.metal
        row["Order #"] = design_no
        row["Qty"] = safe_num(item["qty"])
        row["Weight"] = safe_num(item["gw"])
        row[" Total H.Cost"] = 0
        row["ItemTypeID"] = config.ITEM_TYPE_ID
        row["C1:Item Name"] = fantasy.c1
        row["C1:LotName"] = fantasy.c1
        metal_weight = safe_num(item["tmw"])
        row["C1:Weight"] = None if metal_weight is None else round(metal_weight, 2)
        row["C1: Total H.Cost"] = safe_num(item["mv"])
        row["C2:Item Name"] = "Labor"
        row["C2:LotName"] = "Labor"
        row["C2: Qty"] = safe_num(item["qty"])
        row["C2: Total H.Cost"] = safe_num(item["making"])

        if len(groups) > _AVAILABLE_SLOTS:
            warnings.append(
                f'Item "{style_no}": {len(groups) - _AVAILABLE_SLOTS} stone group(s) '
                f"truncated to fit C3-C{MAX_SLOTS}."
            )

        for slot_index, group in enumerate(groups[:_AVAILABLE_SLOTS]):
            slot = slot_index + 3
            is_center = group["position"] == "center"
            lot = group["cert"] if (is_center and not is_blank(group["cert"])) else "Diamonds"
            row[f"C{slot}:Item Name"] = "Diamonds"
            row[f"C{slot}:LotName"] = lot
            row[f"C{slot}: Qty"] = safe_num(group["pcs"])
            row[f"C{slot}:Weight"] = safe_num(group["cts"])
            row[f"C{slot}:Shape"] = group["shape"]
            row[f"C{slot}:Color"] = materials.normalize_os_color(group["color"])
            row[f"C{slot}:Clarity"] = group["clarity"]
            row[f"C{slot}: Lab"] = group["lab"] if (is_center and not is_blank(group["lab"])) else None
            row[f"C{slot}:Cert#"] = group["cert"] if (is_center and not is_blank(group["cert"])) else None
            row[f"C{slot}: Total H.Cost"] = safe_num(group["val"])
            position_col = f"C{slot}: Stone Position" if slot == 3 else f"C{slot}:Stone Position"
            row[position_col] = "C" if is_center else "S"

        rows.append(row)

    return rows, warnings


def _jobsheet_value(jobsheet_row: dict, column_name: str):
    value = jobsheet_row.get(column_name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_stone_cert(stones_list):
    for stone in stones_list:
        if not is_blank(stone.get("cert")):
            return str(stone["cert"]).strip()
    return None
