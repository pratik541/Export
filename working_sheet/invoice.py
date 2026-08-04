"""Extracts shipment-level fields from the Export Invoice PDF's text (via
pdfplumber), plus a per-category (RITC, gross weight, FOB cost) list used
only to cross-check the Packing List's own numbers in builder.py -- never
as the primary source for those fields."""
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
_CATEGORY_GROSS_WT_RE = re.compile(r"Gross Wt Gms\.[^\n]*\n([\d.]+)")


def extract_text(file_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_invoice(file_bytes: bytes) -> dict:
    text = extract_text(file_bytes)

    def _match(pattern):
        found = pattern.search(text)
        return found.group(1) if found else None

    ritc_headers = _CATEGORY_HEADER_RE.findall(text)
    costs = _CATEGORY_COST_RE.findall(text)
    gross_wts = _CATEGORY_GROSS_WT_RE.findall(text)

    categories = []
    for i, (ritc, number) in enumerate(ritc_headers):
        categories.append({
            "number": int(number),
            "ritc": ritc,
            "cost": float(costs[i].replace(",", "")) if i < len(costs) else None,
            "gross_wt": float(gross_wts[i]) if i < len(gross_wts) else None,
        })

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
