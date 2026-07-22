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

st.set_page_config(page_title="IGI Tag Scanner", layout="wide")

# Positioning-guide box drawn over the camera widget's live preview. Targets the
# keyed container's stable `st-key-camera_guide` class (a documented Streamlit
# class we set), not Streamlit's internal auto-generated classes. pointer-events
# is none so the box never intercepts clicks on the "Take Photo" button. This is
# a visual aid only — approximate alignment, and if a future Streamlit version
# restructures the camera widget the box may misposition but cannot break the app.
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

st.session_state.setdefault("gallery_items", [])          # list of item dicts (see capture.build_item)
st.session_state.setdefault("seen_hashes", set())  # dedupe by original-bytes hash
st.session_state.setdefault("next_id", 1)
st.session_state.setdefault("recrop_id", None)     # id of the item currently being manually re-cropped

st.title("IGI Diamond Report Tag Scanner")
st.caption(
    "Upload or capture tag photos. Each is auto-cropped to the label; re-crop "
    "manually if needed, then run OCR per item or on the whole batch."
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


# --- Input: upload + camera, both feed the same gallery ---
uploaded_files = st.file_uploader(
    "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
)
if uploaded_files:
    for uf in uploaded_files:
        _add_image(uf.getvalue(), uf.name, "upload")

camera_col, _ = st.columns([1, 2])
with camera_col:
    st.markdown(_CAMERA_GUIDE_CSS, unsafe_allow_html=True)
    with st.container(key="camera_guide"):
        shot = st.camera_input("Or take a photo", resolution="1080p")
    st.caption(
        "Fill the box with the tag · hold it flat and steady · "
        "~15–30 cm away · avoid glare on the label"
    )
if shot is not None:
    _add_image(shot.getvalue(), f"camera_capture_{st.session_state.next_id}.jpg", "camera")


def _item_by_id(item_id):
    return next((it for it in st.session_state.gallery_items if it["id"] == item_id), None)


def _run_ocr(item):
    try:
        item["ocr_result"] = pipeline.process_image(item["cropped_bytes"], item["filename"])
    except Exception as exc:  # noqa: BLE001 - one bad image must not kill the batch
        item["ocr_result"] = {"filename": item["filename"], "accepted": False,
                              "reason": f"Processing error: {exc}"}


# --- Manual re-crop overlay (shown when an item's "Re-crop" was clicked) ---
if st.session_state.recrop_id is not None:
    item = _item_by_id(st.session_state.recrop_id)
    if item is not None:
        st.subheader(f"Re-crop: {item['filename']}")
        pil_img = Image.open(io.BytesIO(item["original_bytes"]))
        cropped_pil = st_cropper(pil_img, realtime_update=True, box_color="#00FF00",
                                 aspect_ratio=None, key=f"cropper_{item['id']}")
        col_ok, col_cancel = st.columns(2)
        if col_ok.button("Use this crop", key=f"usecrop_{item['id']}"):
            arr = cv2.cvtColor(np.array(cropped_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
            ok, buf = cv2.imencode(".jpg", arr)
            if ok:
                item["cropped_bytes"] = buf.tobytes()
                item["auto_cropped"] = False
                item["crop_box"] = None      # manual crop; box coords no longer tracked
                item["ocr_result"] = None    # re-crop invalidates any prior OCR
                st.session_state.recrop_id = None
                st.rerun()
            else:
                st.warning("Could not process the crop — please try again.")
        if col_cancel.button("Cancel", key=f"cancelcrop_{item['id']}"):
            st.session_state.recrop_id = None
            st.rerun()

# --- Gallery ---
if st.session_state.gallery_items:
    st.subheader("Captured tags")
    if st.button("Run OCR on all"):
        pending = [it for it in st.session_state.gallery_items if it["ocr_result"] is None]
        progress = st.progress(0.0, text="Running OCR...")
        for i, it in enumerate(pending):
            _run_ocr(it)
            progress.progress((i + 1) / len(pending), text=f"OCR {i + 1}/{len(pending)}")
        progress.empty()

    cols_per_row = 4
    for row_start in range(0, len(st.session_state.gallery_items), cols_per_row):
        row_items = st.session_state.gallery_items[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, it in zip(cols, row_items):
            with col:
                st.image(it["cropped_bytes"], width="stretch")
                if it["ocr_result"] is None:
                    status = "⏳ not scanned" + ("" if it["auto_cropped"] else " · auto-crop failed, re-crop")
                elif not it["ocr_result"].get("accepted", False):
                    status = "❌ " + it["ocr_result"].get("reason", "failed")
                elif it["ocr_result"].get("needs_review"):
                    status = "⚠️ review"
                else:
                    status = "✅ OK"
                st.caption(f"{it['filename']} — {status}")
                if col.button("Re-crop", key=f"recrop_{it['id']}"):
                    st.session_state.recrop_id = it["id"]
                    st.rerun()
                if col.button("OCR", key=f"ocr_{it['id']}"):
                    _run_ocr(it)
                    st.rerun()

# --- Results table + export (only OCR'd, accepted items) ---
ocr_rows = [it["ocr_result"] for it in st.session_state.gallery_items
            if it["ocr_result"] is not None and it["ocr_result"].get("accepted")]
if ocr_rows:
    st.subheader("Results")
    results_df = pd.DataFrame(ocr_rows).drop(columns=["accepted"], errors="ignore")
    results_df.insert(
        0, "review", results_df["needs_review"].map(lambda f: "⚠️ Review" if f else "✅ OK")
    )
    edited_df = st.data_editor(results_df, num_rows="dynamic", width="stretch")

    excel_bytes = excel_export.build_excel_bytes(edited_df)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Download results as Excel",
        data=excel_bytes,
        file_name=f"tag_scan_results_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
elif not st.session_state.gallery_items:
    st.info("Upload or capture tag photos to get started.")
