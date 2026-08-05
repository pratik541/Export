"""Optional Google Sheets central store for scan results, run ALONGSIDE
Supabase (db.py) as a write-side shadow copy -- not yet the app's read
source. Every function degrades safely: if Sheets isn't configured (no
secrets) or a call fails, the app keeps working exactly as it does with
Supabase alone. sheets_db.py is the ONLY module that imports gspread, so the
dependency stays isolated here, same as db.py does for supabase."""
import json
from datetime import datetime, timezone

import streamlit as st

try:
    import gspread
except ImportError:  # dependency missing -> feature simply disabled
    gspread = None

TAG_TAB = "tag_scans"
JEWELRY_TAB = "jewelry_scans"

# Columns written on save, in sheet-column order (A, B, C, ...). "source" and
# "scanned_at" are appended after these, mirroring db.py's payload shape plus
# a client-side timestamp (Sheets has no server-side default the way
# Postgres does).
_COLUMNS = ("igi_report_no", "report_type", "shape", "carat", "color", "clarity", "needs_review")
_JEWELRY_COLUMNS = ("report_no", "shape_cut", "est_weight", "color", "clarity", "style_no", "needs_review")


@st.cache_resource
def get_client():
    """Build and cache the opened Google Spreadsheet from st.secrets, or None
    if unconfigured/unbuildable. Returns the Spreadsheet (not the raw gspread
    Client) since every caller needs a worksheet from this same sheet --
    keeping the one secrets-driven build step in one place, cached with
    st.cache_resource so it's built once and shared, not per rerun."""
    if gspread is None:
        return None
    try:
        cfg = st.secrets["gsheets"]
        info = json.loads(cfg["service_account"])
        spreadsheet_id = cfg["spreadsheet_id"]
    except Exception:
        return None
    try:
        client = gspread.service_account_from_dict(info)
        return client.open_by_key(spreadsheet_id)
    except Exception:
        return None


def is_enabled() -> bool:
    return get_client() is not None


def _worksheet(title: str):
    spreadsheet = get_client()
    if spreadsheet is None:
        return None
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return None


def _find_row(worksheet, key_value: str):
    """1-indexed row number of the data row (row 1 is the header) whose
    first column equals key_value, or None if not found."""
    col = worksheet.col_values(1)
    for i, value in enumerate(col):
        if i == 0:
            continue  # header row
        if value == key_value:
            return i + 1
    return None


def _cell(fields: dict, key: str):
    value = fields.get(key)
    return "" if value is None else value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_scan(fields: dict, source: str) -> bool:
    """Upsert one accepted scan into the tag_scans worksheet, keyed on
    igi_report_no (find the row, update it in place, or append a new row --
    the Sheets equivalent of db.save_scan's Postgres upsert). Returns True on
    success; False (never raises) if disabled, if there's no IGI number to
    key on, or on any client error."""
    key = fields.get("igi_report_no")
    if not key:
        return False
    worksheet = _worksheet(TAG_TAB)
    if worksheet is None:
        return False
    row = [_cell(fields, col) for col in _COLUMNS] + [source, _now_iso()]
    try:
        existing_row = _find_row(worksheet, key)
        if existing_row:
            worksheet.update([row], range_name=f"A{existing_row}")
        else:
            worksheet.append_row(row)
        return True
    except Exception:
        return False


def fetch_all() -> list:
    """Return all saved rows, newest scanned_at first; [] if disabled or on
    error."""
    worksheet = _worksheet(TAG_TAB)
    if worksheet is None:
        return []
    try:
        records = worksheet.get_all_records()
        return sorted(records, key=lambda r: r.get("scanned_at", ""), reverse=True)
    except Exception:
        return []


def delete_one(igi_report_no: str) -> bool:
    """Delete the saved row with this IGI number, if any. Returns True if
    the call ran without error (including when no matching row was found);
    False if disabled or on any client error."""
    worksheet = _worksheet(TAG_TAB)
    if worksheet is None:
        return False
    try:
        row = _find_row(worksheet, igi_report_no)
        if row:
            worksheet.delete_rows(row)
        return True
    except Exception:
        return False


def delete_all() -> bool:
    """Delete every saved row by truncating the sheet back down to just the
    header row. Returns True if the call ran without error; False if
    disabled or on error."""
    worksheet = _worksheet(TAG_TAB)
    if worksheet is None:
        return False
    try:
        worksheet.resize(rows=1)
        return True
    except Exception:
        return False
