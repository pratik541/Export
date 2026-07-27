"""Shared, page-agnostic UI helpers and session state for the IGI tag scanner.

Both the Manage page (full desktop app) and the Scan page (mobile) import from
here. These helpers are the common vocabulary for adding images, running OCR,
auto-saving to Supabase, deleting, and rendering per-item status. They read and
write st.session_state exactly as the original single-page app did."""
import hashlib

import streamlit as st

import capture
import db
import pipeline

FIELD_LABELS = [
    ("igi_report_no", "IGI no."),
    ("report_type", "Report"),
    ("shape", "Shape"),
    ("carat", "Carat"),
    ("color", "Color"),
    ("clarity", "Clarity"),
]

# Guide box drawn over the camera preview. Its relative numbers (width 78%,
# vertical center 42%, 2:1 aspect) MUST match imaging.GUIDE_BOX_* so the visible
# box matches capture.build_item's guide-box crop. Targets the keyed container's
# stable `st-key-camera_guide` class; pointer-events:none so it never blocks the
# shutter button. Visual aid only — approximate alignment, cannot break the app.
CAMERA_GUIDE_CSS = """
<style>
.st-key-camera_guide { position: relative; }
.st-key-camera_guide::after {
    content: "";
    position: absolute;
    top: 42%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 78%;
    aspect-ratio: 2 / 1;
    border: 3px dashed #00e000;
    border-radius: 8px;
    pointer-events: none;
    z-index: 10;
}
</style>
"""


def init_state():
    """Initialize all session-state keys the app relies on (idempotent)."""
    st.session_state.setdefault("gallery_items", [])
    st.session_state.setdefault("seen_hashes", set())
    st.session_state.setdefault("next_id", 1)
    st.session_state.setdefault("recrop_id", None)
    st.session_state.setdefault("confirm_clear", False)
    st.session_state.setdefault("confirm_delete_all", False)
    st.session_state.setdefault("uploader_gen", 0)   # bump to reset the file uploader
    st.session_state.setdefault("camera_gen", 0)     # bump to reset the camera


def add_image(data: bytes, filename: str, source: str, force_guide_box: bool = False):
    """Add one image as a gallery item. Returns the new item, or None if it was
    a duplicate / unreadable. force_guide_box forces a guide-box crop (Scan)."""
    digest = hashlib.md5(data).hexdigest()
    if digest in st.session_state.seen_hashes:
        return None
    try:
        item = capture.build_item(data, filename, source, st.session_state.next_id,
                                  force_guide_box=force_guide_box)
    except ValueError as exc:
        st.warning(f"{filename}: {exc}")
        st.session_state.seen_hashes.add(digest)
        return None
    st.session_state.gallery_items.append(item)
    st.session_state.seen_hashes.add(digest)
    st.session_state.next_id += 1
    return item


def item_by_id(item_id):
    return next((it for it in st.session_state.gallery_items if it["id"] == item_id), None)


def run_ocr(item):
    try:
        item["ocr_result"] = pipeline.process_image(item["cropped_bytes"], item["filename"])
    except Exception as exc:  # noqa: BLE001 - one bad image must not kill the batch
        item["ocr_result"] = {"filename": item["filename"], "accepted": False,
                              "reason": f"Processing error: {exc}"}


def autosave(item):
    """Auto-save an accepted, IGI-bearing scan to Supabase if configured.
    Records the save outcome ON THE ITEM (item["saved_ok"]: True/False, or absent
    if saving didn't apply) so the indicator reflects that item, not a stale
    session-global flag."""
    r = item.get("ocr_result")
    if not (db.is_enabled() and r and r.get("accepted") and r.get("igi_report_no")):
        return
    item["saved_ok"] = db.save_scan(r, item["source"])


def delete_item(item_id):
    # Keep the hash in seen_hashes so a still-populated uploader/camera widget
    # can't re-add the item on the next rerun.
    st.session_state.gallery_items = [
        it for it in st.session_state.gallery_items if it["id"] != item_id
    ]
    if st.session_state.recrop_id == item_id:
        st.session_state.recrop_id = None


def item_status(item):
    r = item["ocr_result"]
    if r is None:
        hint = "" if item.get("crop_method") else " · not cropped, re-crop"
        return "⏳ Not scanned" + hint
    if not r.get("accepted", False):
        return "❌ " + r.get("reason", "failed")
    return "⚠️ Needs review" if r.get("needs_review") else "✅ OK"
