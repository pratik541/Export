"""Extracts shipment-level fields from the Export Invoice PDF's text (via
pdfplumber), plus a per-category (RITC, gross weight, FOB cost) list used
only to cross-check the Packing List's own numbers in builder.py -- never
as the primary source for those fields.

Per-category values are extracted from each category's own text block
(bounded by consecutive "RITC [NN]" headers), not from a flat whole-document
list zipped to categories by position. A real invoice (JNE019) broke that
positional zip two ways: a stones-free category has no "Total ... Cost ..."
line at all, which silently shifted every following category's cost back by
one; and a gold-rate reference line inserted between "Gross Wt Gms." and its
value moved the weight off the very next line entirely. Scoping each regex
to its own category's block means a missing or reformatted value only
affects that one category (falls back to None) instead of cascading."""
import re
from io import BytesIO

import pdfplumber

_INVOICE_NO_RE = re.compile(r"Invoice No\s+([A-Z0-9/\-]+)")
_INVOICE_DATE_RE = re.compile(r"Invoice Dt\s*:\s*(\S+)")
_STATE_CODE_RE = re.compile(r"ORIGIN OF GOODS\s*:\s*(\d+)")
_DISTRICT_CODE_RE = re.compile(r"DISTRICT OF ORIGIN OF GOODS\s*:\s*(\d+)")
_FTA_CODE_RE = re.compile(r"FTA CODE-([A-Z]+)")
_LUT_RE = re.compile(r"Letter of Undertaking", re.IGNORECASE)
_RODTEP_DISCLAIMED_RE = re.compile(r"NOT CLAIM.*?RoDTEP", re.IGNORECASE | re.DOTALL)

_CATEGORY_HEADER_RE = re.compile(r"(\d{8})\s*\[(\d+)\]")
_CATEGORY_COST_RE = re.compile(r"Total\s+\d+\s+[\d.]+\s+[\d,.]+\s+Cost\s+([\d,.]+)")
# Anchored on the number immediately before "Net Wt GMS." rather than right
# after "Gross Wt Gms.", since a rate-reference line can sit between the
# label and the value -- the number just before the next known section
# start is reliable regardless of what text precedes it on that line.
_CATEGORY_GROSS_WT_RE = re.compile(r"([\d.]+)\s*\nNet Wt GMS\.")


def extract_text(file_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_invoice(file_bytes: bytes) -> dict:
    text = extract_text(file_bytes)

    def _match(pattern):
        found = pattern.search(text)
        return found.group(1) if found else None

    categories = _extract_categories(text)

    return {
        "invoice_no": _match(_INVOICE_NO_RE),
        "invoice_date": _match(_INVOICE_DATE_RE),
        "state_code": _match(_STATE_CODE_RE),
        "district_code": _match(_DISTRICT_CODE_RE),
        "fta_code": _match(_FTA_CODE_RE),
        "igst_status": "LUT" if _LUT_RE.search(text) else "",
        "rodtep": "NO" if _RODTEP_DISCLAIMED_RE.search(text) else "YES",
        "categories": categories,
    }


def _extract_categories(text: str) -> list[dict]:
    headers = list(_CATEGORY_HEADER_RE.finditer(text))
    categories = []
    for i, header_match in enumerate(headers):
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[header_match.start():block_end]

        cost_match = _CATEGORY_COST_RE.search(block)
        gross_wt_match = _CATEGORY_GROSS_WT_RE.search(block)
        categories.append({
            "number": int(header_match.group(2)),
            "ritc": header_match.group(1),
            "cost": float(cost_match.group(1).replace(",", "")) if cost_match else None,
            "gross_wt": float(gross_wt_match.group(1)) if gross_wt_match else None,
        })
    return categories
