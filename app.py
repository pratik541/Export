import hashlib
import io
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

import capture
import db
import excel_export
import ocr
import pipeline

st.set_page_config(page_title="IGI Tag Scanner", page_icon="💎", layout="wide")

# Guide box drawn over the camera preview. Its relative numbers (width 78%,
# vertical center 42%, 2:1 aspect) MUST match imaging.GUIDE_BOX_* so the visible
# box matches capture.build_item's guide-box crop. Targets the keyed container's
# stable `st-key-camera_guide` class; pointer-events:none so it never blocks the
# shutter button. Visual aid only — approximate alignment, cannot break the app.
_CAMERA_GUIDE_CSS = """
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

_FIELD_LABELS = [
    ("igi_report_no", "IGI no."),
    ("report_type", "Report"),
    ("shape", "Shape"),
    ("carat", "Carat"),
    ("color", "Color"),
    ("clarity", "Clarity"),
]

if "ocr_reader_ready" not in st.session_state:
    with st.spinner("Loading OCR model (first run may take a few minutes to download)..."):
        ocr.get_reader()
    st.session_state.ocr_reader_ready = True

st.session_state.setdefault("gallery_items", [])
st.session_state.setdefault("seen_hashes", set())
st.session_state.setdefault("next_id", 1)
st.session_state.setdefault("recrop_id", None)
st.session_state.setdefault("confirm_clear", False)
st.session_state.setdefault("uploader_gen", 0)   # bump to reset the file uploader
st.session_state.setdefault("camera_gen", 0)     # bump to reset the camera (one-click repeat capture)

st.title(":material/diamond: IGI diamond report tag scanner")


def _add_image(data: bytes, filename: str, source: str):
    """Add one image as a gallery item. Returns the new item, or None if it was
    a duplicate / unreadable (so the caller can decide whether to auto-OCR)."""
    digest = hashlib.md5(data).hexdigest()
    if digest in st.session_state.seen_hashes:
        return None
    try:
        item = capture.build_item(data, filename, source, st.session_state.next_id)
    except ValueError as exc:
        st.warning(f"{filename}: {exc}")
        st.session_state.seen_hashes.add(digest)
        return None
    st.session_state.gallery_items.append(item)
    st.session_state.seen_hashes.add(digest)
    st.session_state.next_id += 1
    return item


def _item_by_id(item_id):
    return next((it for it in st.session_state.gallery_items if it["id"] == item_id), None)


def _run_ocr(item):
    try:
        item["ocr_result"] = pipeline.process_image(item["cropped_bytes"], item["filename"])
    except Exception as exc:  # noqa: BLE001 - one bad image must not kill the batch
        item["ocr_result"] = {"filename": item["filename"], "accepted": False,
                              "reason": f"Processing error: {exc}"}


def _autosave(item):
    """Auto-save an accepted, IGI-bearing scan to Supabase if configured.
    Records the save outcome ON THE ITEM (item["saved_ok"]: True/False, or absent
    if saving didn't apply) so the indicator reflects that item, not a stale
    session-global flag."""
    r = item.get("ocr_result")
    if not (db.is_enabled() and r and r.get("accepted") and r.get("igi_report_no")):
        return
    item["saved_ok"] = db.save_scan(r, item["source"])


def _delete_item(item_id):
    # Keep the hash in seen_hashes so a still-populated uploader/camera widget
    # can't re-add the item on the next rerun.
    st.session_state.gallery_items = [
        it for it in st.session_state.gallery_items if it["id"] != item_id
    ]
    if st.session_state.recrop_id == item_id:
        st.session_state.recrop_id = None


def _item_status(item):
    r = item["ocr_result"]
    if r is None:
        hint = "" if item.get("crop_method") else " · not cropped, re-crop"
        return "⏳ Not scanned" + hint
    if not r.get("accepted", False):
        return "❌ " + r.get("reason", "failed")
    return "⚠️ Needs review" if r.get("needs_review") else "✅ OK"


# --- Upload (top) ---
uploaded_files = st.file_uploader(
    "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_gen}",
)
if uploaded_files:
    added_any = False
    for uf in uploaded_files:
        if _add_image(uf.getvalue(), uf.name, "upload") is not None:
            added_any = True
    if added_any:
        st.toast("Photos added — use 'Run OCR on all' below", icon=":material/upload:")


# --- Capture (camera left, latest result right) ---
cam_col, latest_col = st.columns(2)

with cam_col:
    st.subheader(":material/photo_camera: Take a photo")
    st.markdown(_CAMERA_GUIDE_CSS, unsafe_allow_html=True)
    with st.container(key="camera_guide"):
        shot = st.camera_input(
            "Point at the tag and shoot", resolution="1080p",
            key=f"camera_{st.session_state.camera_gen}", label_visibility="collapsed",
        )
    st.caption("Fill the box with the tag · hold flat and steady · ~15–30 cm · avoid glare")
    if shot is not None:
        item = _add_image(shot.getvalue(), f"camera_capture_{st.session_state.next_id}.jpg", "camera")
        if item is not None:
            with st.spinner("Reading tag..."):
                _run_ocr(item)
            _autosave(item)
            st.session_state.camera_gen += 1  # reset camera to live preview for the next shot
            st.toast(f"Scanned {item['filename']} — {_item_status(item)}", icon=":material/check_circle:")
            st.rerun()

with latest_col:
    st.subheader(":material/center_focus_strong: Latest capture")
    items = st.session_state.gallery_items
    if not items:
        st.info("Snap a tag — its reading shows here.")
    else:
        latest = items[-1]
        img_col, data_col = st.columns([1, 1])
        with img_col:
            st.image(latest["cropped_bytes"], width="stretch")
        with data_col:
            st.markdown(f"**{_item_status(latest)}**")
            r = latest["ocr_result"]
            if r and r.get("accepted"):
                st.dataframe(
                    pd.DataFrame(
                        [(lbl, r.get(key) or "—") for key, lbl in _FIELD_LABELS],
                        columns=["Field", "Value"],
                    ),
                    hide_index=True, width="stretch",
                )
            if db.is_enabled():
                saved = latest.get("saved_ok")
                if saved is True:
                    st.caption("☁ saved to database")
                elif saved is False:
                    st.caption("⚠ save failed — kept locally")
        rc1, rc2, rc3 = st.columns(3)
        if rc1.button(":material/document_scanner: Rescan", key=f"latest_rescan_{latest['id']}"):
            with st.spinner("Reading tag..."):
                _run_ocr(latest)
            _autosave(latest)
            st.rerun()
        if rc2.button(":material/crop: Re-crop", key=f"latest_recrop_{latest['id']}"):
            st.session_state.recrop_id = latest["id"]
            st.rerun()
        if rc3.button(":material/delete: Delete", key=f"latest_del_{latest['id']}"):
            _delete_item(latest["id"])
            st.rerun()


# --- Manual re-crop overlay ---
if st.session_state.recrop_id is not None:
    item = _item_by_id(st.session_state.recrop_id)
    if item is not None:
        with st.container(border=True):
            st.subheader(f":material/crop: Re-crop: {item['filename']}")
            pil_img = Image.open(io.BytesIO(item["original_bytes"]))
            cropped_pil = st_cropper(pil_img, realtime_update=True, box_color="#00FF00",
                                     aspect_ratio=None, key=f"cropper_{item['id']}")
            ok_col, cancel_col = st.columns(2)
            if ok_col.button("Use this crop", key=f"usecrop_{item['id']}", type="primary"):
                arr = cv2.cvtColor(np.array(cropped_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
                ok, buf = cv2.imencode(".jpg", arr)
                if ok:
                    item["cropped_bytes"] = buf.tobytes()
                    item["auto_cropped"] = False
                    item["crop_box"] = None
                    item["crop_method"] = "manual"
                    with st.spinner("Reading tag..."):
                        _run_ocr(item)   # re-crop -> rescan so the shown result matches the new crop
                    _autosave(item)
                    st.session_state.recrop_id = None
                    st.rerun()
                else:
                    st.warning("Could not process the crop — please try again.")
            if cancel_col.button("Cancel", key=f"cancelcrop_{item['id']}"):
                st.session_state.recrop_id = None
                st.rerun()


# --- Gallery + batch actions ---
items = st.session_state.gallery_items
if items:
    total = len(items)
    scanned = [it["ocr_result"] for it in items if it["ocr_result"] is not None]
    accepted = [r for r in scanned if r.get("accepted")]
    ok = sum(1 for r in accepted if not r.get("needs_review"))
    review = sum(1 for r in accepted if r.get("needs_review"))
    not_scanned = total - len(scanned)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total tags", total)
    m2.metric("OK", ok)
    m3.metric("Needs review", review)
    m4.metric("Not scanned", not_scanned)

    action_col, clear_col = st.columns([3, 1])
    if action_col.button(":material/document_scanner: Run OCR on all", type="primary"):
        pending = [it for it in items if it["ocr_result"] is None]
        progress = st.progress(0.0, text="Running OCR...")
        for i, it in enumerate(pending):
            _run_ocr(it)
            _autosave(it)
            progress.progress((i + 1) / max(len(pending), 1), text=f"OCR {i + 1}/{len(pending)}")
        progress.empty()
        st.toast("OCR complete", icon=":material/check_circle:")
        st.rerun()
    if clear_col.button(":material/delete_sweep: Clear all"):
        st.session_state.confirm_clear = True

    if st.session_state.confirm_clear:
        st.warning("Remove all captured tags?")
        yes_col, no_col = st.columns(2)
        if yes_col.button("Yes, clear all", type="primary"):
            st.session_state.gallery_items = []
            st.session_state.seen_hashes = set()
            st.session_state.recrop_id = None
            st.session_state.confirm_clear = False
            st.session_state.uploader_gen += 1
            st.session_state.camera_gen += 1
            st.rerun()
        if no_col.button("Cancel clear"):
            st.session_state.confirm_clear = False
            st.rerun()

    with st.container(border=True):
        st.subheader(":material/photo_library: All tags")
        cols_per_row = 5
        for row_start in range(0, len(items), cols_per_row):
            for col, it in zip(st.columns(cols_per_row), items[row_start:row_start + cols_per_row]):
                with col:
                    st.image(it["cropped_bytes"], width="stretch")
                    st.caption(f"{it['filename']} — {_item_status(it)}")
                    b1, b2, b3 = st.columns(3)
                    if b1.button(":material/crop:", key=f"recrop_{it['id']}", help="Re-crop"):
                        st.session_state.recrop_id = it["id"]
                        st.rerun()
                    if b2.button(":material/document_scanner:", key=f"ocr_{it['id']}", help="Run OCR"):
                        with st.spinner("Reading..."):
                            _run_ocr(it)
                        _autosave(it)
                        st.rerun()
                    if b3.button(":material/delete:", key=f"del_{it['id']}", help="Delete"):
                        _delete_item(it["id"])
                        st.rerun()

# --- Results table + export ---
ocr_rows = [it["ocr_result"] for it in items
            if it["ocr_result"] is not None and it["ocr_result"].get("accepted")]
if ocr_rows:
    with st.container(border=True):
        st.subheader(":material/table_view: Results")
        results_df = pd.DataFrame(ocr_rows).drop(columns=["accepted"], errors="ignore")
        results_df.insert(
            0, "review", results_df["needs_review"].map(lambda f: "⚠️ Review" if f else "✅ OK")
        )
        edited_df = st.data_editor(results_df, num_rows="dynamic", width="stretch")

        excel_bytes = excel_export.build_excel_bytes(edited_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            ":material/download: Download results as Excel",
            data=excel_bytes,
            file_name=f"tag_scan_results_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
elif not items:
    st.info("Upload or capture tag photos to get started.")

# --- Saved records (shared Supabase store) ---
if db.is_enabled():
    with st.container(border=True):
        header_col, refresh_col = st.columns([3, 1])
        header_col.subheader(":material/cloud: Saved records (shared)")
        if refresh_col.button(":material/refresh: Refresh"):
            st.rerun()
        rows = db.fetch_all()
        if not rows:
            st.caption("No saved records yet (or couldn't reach the database).")
        else:
            saved_df = pd.DataFrame(rows)
            st.dataframe(saved_df, hide_index=True, width="stretch")
            excel_bytes = excel_export.build_excel_bytes(saved_df)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                ":material/download: Download all saved records as Excel",
                data=excel_bytes,
                file_name=f"tag_scans_all_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_all_saved",
            )
