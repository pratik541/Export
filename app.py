import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

import excel_export
import ocr
import pipeline

st.set_page_config(page_title="IGI Tag Scanner", layout="wide")
ocr.configure_tesseract()

st.session_state.setdefault("rows", [])
st.session_state.setdefault("processed_keys", set())
st.session_state.setdefault("camera_shot_count", 0)

st.title("IGI Diamond Report Tag Scanner")
st.caption(
    "Upload tag photos or use the camera below. On desktop, the camera widget "
    "works with any camera the browser can see — including a phone connected as "
    "a webcam via Windows 11's Phone Link (see README)."
)

uploaded_files = st.file_uploader(
    "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
)
camera_photo = st.camera_input("Or take a photo")

candidates = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        candidates.append((uploaded_file.name, uploaded_file.getvalue()))
if camera_photo is not None:
    data = camera_photo.getvalue()
    if hashlib.md5(data).hexdigest() not in st.session_state.processed_keys:
        st.session_state.camera_shot_count += 1
        candidates.append((f"camera_capture_{st.session_state.camera_shot_count}.jpg", data))

new_items = []
for name, data in candidates:
    key = f"{name}:{hashlib.md5(data).hexdigest()}"
    if key not in st.session_state.processed_keys:
        new_items.append((key, name, data))

if new_items:
    progress = st.progress(0.0, text="Processing tag images...")
    for i, (key, name, data) in enumerate(new_items):
        try:
            result = pipeline.process_image(data, name)
        except Exception as exc:  # noqa: BLE001 - one bad file must never kill the batch
            result = {"filename": name, "accepted": False, "reason": f"Processing error: {exc}"}
        st.session_state.processed_keys.add(key)
        if not result["accepted"]:
            st.warning(f"{name}: {result['reason']}")
        else:
            st.session_state.rows.append(result)
        progress.progress((i + 1) / len(new_items), text=f"Processed {i + 1}/{len(new_items)}")
    progress.empty()

if st.session_state.rows:
    results_df = pd.DataFrame(st.session_state.rows).drop(columns=["accepted"], errors="ignore")
    results_df.insert(
        0, "review", results_df["needs_review"].map(lambda flagged: "⚠️ Review" if flagged else "✅ OK")
    )
    edited_df = st.data_editor(results_df, num_rows="dynamic", use_container_width=True)

    excel_bytes = excel_export.build_excel_bytes(edited_df)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Download results as Excel",
        data=excel_bytes,
        file_name=f"tag_scan_results_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Upload or capture tag photos to get started.")
