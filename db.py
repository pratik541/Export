"""Optional Supabase-backed central store for scan results.

Every function degrades safely: if Supabase isn't configured (no secrets) or a
call fails, the app keeps working locally. `db.py` is the ONLY module that
imports supabase, so the dependency stays isolated here."""
import streamlit as st

try:
    from supabase import create_client
except ImportError:  # dependency missing -> feature simply disabled
    create_client = None

TABLE = "tag_scans"

# Columns written on upsert (scanned_at is filled server-side by a default).
_COLUMNS = ("igi_report_no", "report_type", "shape", "carat", "color", "clarity", "needs_review")


@st.cache_resource
def get_client():
    """Build a Supabase client from st.secrets, or return None if unconfigured
    or unbuildable. Cached with st.cache_resource, so one client is built and
    shared (across sessions) rather than reconstructed per rerun."""
    if create_client is None:
        return None
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def is_enabled() -> bool:
    return get_client() is not None


def save_scan(fields: dict, source: str) -> bool:
    """Upsert one accepted scan into TABLE, keyed on igi_report_no. Returns True
    on success; False (never raises) if disabled, if there's no IGI number to
    key on, or on any client error."""
    client = get_client()
    if client is None:
        return False
    if not fields.get("igi_report_no"):
        return False
    payload = {col: fields.get(col) for col in _COLUMNS}
    payload["source"] = source
    try:
        client.table(TABLE).upsert(payload, on_conflict="igi_report_no").execute()
        return True
    except Exception:
        return False


def fetch_all() -> list:
    """Return all saved rows, newest scanned_at first; [] if disabled or on error."""
    client = get_client()
    if client is None:
        return []
    try:
        result = client.table(TABLE).select("*").order("scanned_at", desc=True).execute()
        return result.data or []
    except Exception:
        return []


def delete_one(igi_report_no: str) -> bool:
    """Delete the saved row with this IGI number. Returns True if the call ran
    without error; False if disabled or on any client error. (Whether a row was
    actually removed also depends on the delete RLS policy — the app verifies
    effect by re-reading.)"""
    client = get_client()
    if client is None:
        return False
    try:
        client.table(TABLE).delete().eq("igi_report_no", igi_report_no).execute()
        return True
    except Exception:
        return False


def delete_all() -> bool:
    """Delete every saved row. PostgREST requires a filter on delete, so match
    all rows via a never-true-exclusion on the primary key. Returns True if the
    call ran without error; False if disabled or on error."""
    client = get_client()
    if client is None:
        return False
    try:
        client.table(TABLE).delete().neq("igi_report_no", "__none__").execute()
        return True
    except Exception:
        return False
