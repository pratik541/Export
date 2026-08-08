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
# Metal column value). Matched by exact code on the raw (trimmed/uppercased,
# NOT whitespace-compacted) KT text -- adding a spaceless variant of an
# existing code (e.g. "14KTY" alongside "14KT Y") does NOT make it match;
# it needs its own row. Two literal substring special cases in
# materials.resolve_fantasy_material ("18KTW", "PT") are checked against
# the whitespace-compacted input before this table lookup runs -- see that
# function's docstring for why they can't be expressed as table rows.
#
# The "0.950"/"0.95"/"PT" entries (c1="PT", suffix="PL", metal="PL") and the
# compact abbreviated rows below (10KTW, 10KTY, 14KTR, 14KTW, 14KTY, 18KTY)
# were corrected/added after comparing this port's output against a real
# reference "Open Stock" file (Data/JNE016 Open Stock.xls, local-only, real
# business data) covering all 8 distinct KT codes in that real shipment: the
# source HTML tool's *default* config (a browser-localStorage value, editable
# via its Settings UI, which this port deliberately doesn't have -- decision
# 1) does not match what this business's actual, presumably-customized live
# tool produces. In particular the source file's hardcoded "14KTR" -> "14KT
# RG" special case was found to disagree with all real "14KTR" rows checked
# (real output: "14KR") and was replaced by a plain table row instead.
FANTASY_MATERIAL_MAP = [
    {"code": "925F", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "925FW", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "925", "c1": "925F", "suffix": "925F", "metal": "925F"},
    {"code": "0.950", "c1": "PT", "suffix": "PL", "metal": "PL"},
    {"code": "0.95", "c1": "PT", "suffix": "PL", "metal": "PL"},
    {"code": "PT", "c1": "PT", "suffix": "PL", "metal": "PL"},
    {"code": "14KT", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT Y", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT YG", "c1": "14KT", "suffix": "14KT", "metal": "14KT"},
    {"code": "14KT WG", "c1": "14KT WG", "suffix": "14KT WG", "metal": "14KT WG"},
    {"code": "14KT RG", "c1": "14KT RG", "suffix": "14KT RG", "metal": "14KT RG"},
    {"code": "18KT", "c1": "18KT", "suffix": "18KT", "metal": "18KT"},
    {"code": "18KT YG", "c1": "18KT", "suffix": "18KT", "metal": "18KT"},
    {"code": "18KT WG", "c1": "18KT WG", "suffix": "18KT WG", "metal": "18KT WG"},
    {"code": "18KT RG", "c1": "18KT RG", "suffix": "18KT RG", "metal": "18KT RG"},
    {"code": "10KTW", "c1": "10KW", "suffix": "10KW", "metal": "10KW"},
    {"code": "10KTY", "c1": "10KY", "suffix": "10KY", "metal": "10KY"},
    {"code": "14KTR", "c1": "14KR", "suffix": "14KR", "metal": "14KR"},
    {"code": "14KTW", "c1": "14KW", "suffix": "14KW", "metal": "14KW"},
    {"code": "14KTY", "c1": "14KY", "suffix": "14KY", "metal": "14KY"},
    {"code": "18KTY", "c1": "18KY", "suffix": "18KY", "metal": "18KY"},
    # Added after export_tool.fantasy_file.build_rows's new "KT code not in
    # FANTASY_MATERIAL_MAP" warning (see fantasy_file.py) flagged it against
    # a second real shipment (Data/JNE013 Packing List.xlsx, local-only):
    # same "strip the T" pattern as the rows above.
    {"code": "10KTR", "c1": "10KR", "suffix": "10KR", "metal": "10KR"},
    # "18KT2T" (two-tone) was ALSO flagged by that warning on the same
    # shipment, but checked against Data/JNE013 Open Stock.xls and found to
    # stay verbatim/unmapped in real production too -- no row added; the
    # existing raw fallback is already correct for it.
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
#
# design_no was "Original Payment Method" in the source HTML tool's default
# config -- ported as-is, then checked against a real jobsheet export
# (Data/JNE016 jobsheet.csv, local-only, real business data): "Original
# Payment Method" is blank on every real row, while "Order Id" holds
# exactly the order-reference values the real "Open Stock" output's
# "Order #" column shows (verified: item AFDRW30804/7's jobsheet row has
# Order Id "FD-1784699200", matching that item's real Order # verbatim).
# Corrected to the column that's actually populated.
JOBSHEET_COLUMNS = {
    "design_no": "Order Id",
    "parent_style": "Product Status",
}

# CSV column names (tried for every row) that can key a jobsheet row -- a
# row is indexed under every one of these it has a non-blank value for.
#
# "Third Code" was not in the source HTML tool's hardcoded list -- added
# after checking against the real jobsheet (Data/JNE016 jobsheet.csv):
# "Setting SKU" is a generic placeholder ("CUSTOM_PRODUCT") for most real
# orders, and the real style number (matching the packing list's Style No.,
# e.g. "R15531/1") lives in "Third Code" instead. Without it, only 6 of 44
# real items in that shipment matched a jobsheet row at all; with it, 44/44
# match.
JOBSHEET_KEY_COLUMNS = ["Order Id", "Setting SKU", "StyleNo", "Style No.", "Third Code"]

ITEM_TYPE_ID = 11
NORMALIZE_TWO_LETTER_COLOR = True
MERGE_CATEGORIES = ["CHAIN"]
NO_SIDE_DIAMOND_CATEGORIES = ["BRACELET"]
SINGLE_CENTER_PROMOTION = True
