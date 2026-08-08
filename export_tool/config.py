"""Config-as-code defaults for the Export Tool's Fantasy File generator --
ported from the source HTML tool's `DEFAULTS`, trimmed to only what the
Fantasy File actually reads. See
docs/superpowers/specs/2026-08-08-poddar-export-tool-design.md (decision 2)
for exactly what was dropped and why: fields/tables that existed only to
feed the source tool's Jewelry Import output, which this port doesn't
generate at all.

No Settings UI exists for these in v1 (decision 1) -- if the ERP renames a
column or a mapping needs to change, edit the values below."""

# KT code -> Fantasy File material codes (C1 slot code, item-name suffix,
# Metal column value). Matched by exact code after whitespace-compaction --
# see materials.resolve_fantasy_material.
FANTASY_MATERIAL_MAP = [
    {"code": "925F", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "925FW", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "925", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "0.950", "c1": "PL", "suffix": "PL", "metal": "PT"},
    {"code": "0.95", "c1": "PL", "suffix": "PL", "metal": "PT"},
    {"code": "PT", "c1": "PL", "suffix": "PL", "metal": "PT"},
    {"code": "14KT", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT Y", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT YG", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT WG", "c1": "14KT WG", "suffix": "14KT WG", "metal": "14KT WG"},
    {"code": "14KT RG", "c1": "14KT RG", "suffix": "14KT RG", "metal": "14KT RG"},
    {"code": "18KT", "c1": "18KT", "suffix": "18KT", "metal": "18KT"},
    {"code": "18KT YG", "c1": "18KT", "suffix": "18KT", "metal": "18KT"},
    {"code": "18KT WG", "c1": "18KT WG", "suffix": "18KT WG", "metal": "18KT WG"},
    {"code": "18KT RG", "c1": "18KT RG", "suffix": "18KT RG", "metal": "18KT RG"},
]

# Packing-list header text per logical field.
PACK_COLUMN_HEADERS = {
    "sr": "Sr No",
    "sn": "Style No.",
    "cat": "Category",
    "kt": "KT",
    "qty": "Qty",
    "gw": "Gross Wt in gms",
    "tmw": "Total Metal wt. gms",
    "mv": "Metal Value",
    "lab": "Lab",
    "cert": "Certificate No",
    "stud": "Studding Type",
    "scc": "Shape/Color Clarity",
    "stnpcs": "Stn Pcs",
    "stncts": "Stn Cts",
    "val": "Value $",
    "making": "Making Value",
}

# OMS Jobsheet CSV column names per logical field.
JOBSHEET_COLUMNS = {
    "design_no": "Original Payment Method",
    "parent_style": "Product Status",
    "setting_cert": "Setting Certificate No",
}

# CSV column names (tried for every row) that can key a jobsheet row -- a
# row is indexed under every one of these it has a non-blank value for.
JOBSHEET_KEY_COLUMNS = ["Order Id", "Setting SKU", "StyleNo", "Style No."]

ITEM_TYPE_ID = 11
NORMALIZE_TWO_LETTER_COLOR = True
MERGE_CATEGORIES = ["CHAIN"]
NO_SIDE_DIAMOND_CATEGORIES = ["BRACELET"]
SINGLE_CENTER_PROMOTION = True
STONE_FALLBACK_LABEL = "LG Diamond"
