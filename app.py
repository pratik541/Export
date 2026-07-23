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

if "ocr_reader_ready" not in st.session_state:
    with st.spinner("Loading OCR model (first run may take a few minutes to download)..."):
        ocr.get_reader()
    st.session_state.ocr_reader_ready = True

st.session_state.setdefault("gallery_items", [])
st.session_state.setdefault("seen_hashes", set())
st.session_state.setdefault("next_id", 1)
st.session_state.setdefault("recrop_id", None)
st.session_state.setdefault("confirm_clear", False)
st.session_state.setdefault("widget_gen", 0)

st.title(":material/diamond: IGI diamond report tag scanner")
st.caption(
    "Add tag photos, review the auto-crop, then run OCR per item or on the whole "
    "batch. Rows flagged for review need a human check before export."
)


def _add_image(data: bytes, filename: str, source: str):
    digest = hashlib.md5(data).hexdigest()
    if digest in st.session_state.seen_hashes:
        return
    try:
        item = capture.build_item(data, filename, source, st.session_state.next_id)
    except ValueError as exc:
        st.warning(f"{filename}: {exc}")
        st.session_state.seen_hashes.add(digest)
        return
    st.session_state.gallery_items.append(item)
    st.session_state.seen_hashes.add(digest)
    st.session_state.next_id += 1
    st.toast(f"Added {filename}", icon=":material/add_photo_alternate:")


def _item_by_id(item_id):
    return next((it for it in st.session_state.gallery_items if it["id"] == item_id), None)


def _run_ocr(item):
    try:
        item["ocr_result"] = pipeline.process_image(item["cropped_bytes"], item["filename"])
    except Exception as exc:  # noqa: BLE001 - one bad image must not kill the batch
        item["ocr_result"] = {"filename": item["filename"], "accepted": False,
                              "reason": f"Processing error: {exc}"}


def _delete_item(item_id):
    item = _item_by_id(item_id)
    if item is not None:
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


# --- Add tags section ---
with st.container(border=True):
    st.subheader(":material/add_a_photo: Add tags")
    up_col, cam_col = st.columns(2)
    with up_col:
        uploaded_files = st.file_uploader(
            "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
            key=f"uploader_{st.session_state.widget_gen}",
        )
        if uploaded_files:
            for uf in uploaded_files:
                _add_image(uf.getvalue(), uf.name, "upload")
    with cam_col:
        st.markdown(_CAMERA_GUIDE_CSS, unsafe_allow_html=True)
        with st.container(key="camera_guide"):
            shot = st.camera_input(
                "Or take a photo", resolution="1080p",
                key=f"camera_{st.session_state.widget_gen}",
            )
        st.caption("Fill the box with the tag · hold flat and steady · ~15–30 cm · avoid glare")
        if shot is not None:
            _add_image(shot.getvalue(), f"camera_capture_{st.session_state.next_id}.jpg", "camera")


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
                    item["ocr_result"] = None
                    st.session_state.recrop_id = None
                    st.rerun()
                else:
                    st.warning("Could not process the crop — please try again.")
            if cancel_col.button("Cancel", key=f"cancelcrop_{item['id']}"):
                st.session_state.recrop_id = None
                st.rerun()


# --- Metrics + batch actions ---
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
            with st.spinner(f"Reading {it['filename']}..."):
                _run_ocr(it)
            progress.progress((i + 1) / max(len(pending), 1), text=f"OCR {i + 1}/{len(pending)}")
        progress.empty()
        st.toast("OCR complete", icon=":material/check_circle:")
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
            st.session_state.widget_gen += 1
            st.rerun()
        if no_col.button("Cancel clear"):
            st.session_state.confirm_clear = False
            st.rerun()

    # --- Gallery ---
    with st.container(border=True):
        st.subheader(":material/photo_library: Captured tags")
        cols_per_row = 4
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
                        st.toast(f"Scanned {it['filename']}", icon=":material/check_circle:")
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
