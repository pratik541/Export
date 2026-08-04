"""Combines Packing List categories (working_sheet.packing_list) and
Invoice shipment fields (working_sheet.invoice) into Working Sheet rows,
filling in the fixed constants neither document supplies, and cross-checks
the two sources against each other."""

WORKING_SHEET_COLUMNS = [
    "Invoice No.", "Item No.", "RITC", "Item Description", "Qty.",
    "Unit of Qty", "Unit Price", "Per", "PMV Unit Price", "Scheme Code",
    "Drawback Sr. No.", "DBK Qty", "DBK Qty Unit", "Reward Item", "STR Code",
    "End Use", "IGST Payment Status", "Taxable Value", "IGST Amount",
    "IGST Rate", "Compensation Cess Amount", "State Code", "District Code",
    "Standard Qty", "Standard Qty Unit", "FTA Code", "Accessory Status",
    "RoDTEP",
]

_WEIGHT_TOLERANCE = 0.01
_VALUE_TOLERANCE = 0.01


def build_rows(categories: list[dict], invoice: dict) -> list[dict]:
    rows = []
    for cat in categories:
        rows.append({
            "Invoice No.": invoice.get("invoice_no") or "",
            "Item No.": cat["number"],
            "RITC": int(cat["ritc"]),
            "Item Description": cat["description"],
            "Qty.": cat["gross_wt"],
            "Unit of Qty": "GMS",
            "Unit Price": cat["unit_price"],
            "Per": "1",
            "PMV Unit Price": "0.00",
            "Scheme Code": "00",
            "Drawback Sr. No.": "",
            "DBK Qty": "",
            "DBK Qty Unit": "",
            "Reward Item": "",
            "STR Code": "",
            "End Use": "GNX100",
            "IGST Payment Status": invoice.get("igst_status") or "",
            "Taxable Value": "",
            "IGST Amount": "",
            "IGST Rate": "",
            "Compensation Cess Amount": "",
            "State Code": int(invoice["state_code"]) if invoice.get("state_code") else "",
            "District Code": int(invoice["district_code"]) if invoice.get("district_code") else "",
            "Standard Qty": cat["standard_qty"],
            "Standard Qty Unit": "KGS",
            "FTA Code": invoice.get("fta_code") or "",
            "Accessory Status": "0",
            "RoDTEP": invoice.get("rodtep") or "",
        })
    return rows


def cross_validate(categories: list[dict], invoice: dict) -> list[str]:
    warnings = []
    invoice_categories = {c["number"]: c for c in invoice.get("categories", [])}

    if len(invoice_categories) != len(categories):
        warnings.append(
            f"Category count mismatch: packing list has {len(categories)}, "
            f"invoice has {len(invoice_categories)}."
        )

    for cat in categories:
        inv_cat = invoice_categories.get(cat["number"])
        if inv_cat is None:
            warnings.append(f"Category [{cat['number']:02d}]: not found in invoice.")
            continue
        if inv_cat["ritc"] and inv_cat["ritc"] != cat["ritc"]:
            warnings.append(
                f"Category [{cat['number']:02d}]: RITC mismatch "
                f"(packing list {cat['ritc']}, invoice {inv_cat['ritc']})."
            )
        if (inv_cat["gross_wt"] is not None
                and abs(inv_cat["gross_wt"] - cat["gross_wt"]) > _WEIGHT_TOLERANCE):
            warnings.append(
                f"Category [{cat['number']:02d}]: gross weight mismatch "
                f"(packing list {cat['gross_wt']}, invoice {inv_cat['gross_wt']})."
            )
        if (inv_cat["cost"] is not None
                and abs(inv_cat["cost"] - cat["fob_value"]) > _VALUE_TOLERANCE):
            warnings.append(
                f"Category [{cat['number']:02d}]: FOB value mismatch "
                f"(packing list {cat['fob_value']}, invoice {inv_cat['cost']})."
            )
    return warnings
