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
    or unbuildable. Cached so the client is created once per session."""
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
