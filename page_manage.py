"""Manage page: the full desktop scanner UI — upload, camera, gallery, results
table + Excel export, and the shared Supabase saved-records view. Behavior is
identical to the original single-page app; it was relocated here so the app can
also offer a compact mobile Scan page. All the logic lives in ui_common; this
module is presentation only."""
import io
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

import db
import excel_export
import sheets_db
from ui_common import (
    add_image as _add_image, item_by_id as _item_by_id, run_ocr as _run_ocr,
    autosave as _autosave, delete_item as _delete_item, item_status as _item_status,
    FIELD_LABELS as _FIELD_LABELS, JEWELRY_FIELD_LABELS as _JEWELRY_FIELD_LABELS,
    guide_box_css as _guide_box_css,
)


def render():
    st.session_state.setdefault("confirm_delete_all_jewelry", False)

    st.title(":material/diamond: IGI diamond report tag scanner")

    # --- Card-type selector ---
    card_type_choice = st.radio(
        "Card type", ["Diamond tag", "Jewelry card"],
        horizontal=True, key="manage_card_type",
    )
    card_type = "jewelry" if card_type_choice == "Jewelry card" else "diamond"
    st.session_state.card_type = card_type

    # --- Upload (top) ---
    uploaded_files = st.file_uploader(
        "Upload tag photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_gen}",
    )
    if uploaded_files:
        added_any = False
        for uf in uploaded_files:
            if _add_image(uf.getvalue(), uf.name, "upload", card_type=card_type) is not None:
                added_any = True
        if added_any:
            st.toast("Photos added — use 'Run OCR on all' below", icon=":material/upload:")


    # --- Capture (camera left, latest result right) ---
    cam_col, latest_col = st.columns(2)

    with cam_col:
        st.subheader(":material/photo_camera: Take a photo")
        st.markdown(_guide_box_css(card_type), unsafe_allow_html=True)
        with st.container(key="camera_guide"):
            shot = st.camera_input(
                "Point at the tag and shoot", resolution="1080p",
                key=f"camera_{st.session_state.camera_gen}", label_visibility="collapsed",
            )
        st.caption("Fill the box with the tag · hold flat and steady · ~15–30 cm · avoid glare")
        if shot is not None:
            item = _add_image(shot.getvalue(), f"camera_capture_{st.session_state.next_id}.jpg", "camera",
                              card_type=card_type)
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
                    labels = _JEWELRY_FIELD_LABELS if latest.get("card_type") == "jewelry" else _FIELD_LABELS
                    st.dataframe(
                        pd.DataFrame(
                            [(lbl, r.get(key) or "—") for key, lbl in labels],
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
        if clear_col.button(":material/restart_alt: Restart / new batch"):
            st.session_state.confirm_clear = True

        if st.session_state.confirm_clear:
            st.warning("Start a new batch? This clears the captured tags on THIS device (saved database records are not affected).")
            yes_col, no_col = st.columns(2)
            if yes_col.button("Yes, restart", type="primary"):
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
    # Filter to the currently selected card type so diamond and jewelry rows
    # (which have different field sets) never mix in one table. Items with no
    # card_type (e.g. pre-existing diamond items) count as "diamond".
    ocr_rows = [it["ocr_result"] for it in items
                if it["ocr_result"] is not None and it["ocr_result"].get("accepted")
                and (it.get("card_type") or "diamond") == card_type]
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
                dl_col, delall_col = st.columns([3, 1])
                dl_col.download_button(
                    ":material/download: Download all saved records as Excel",
                    data=excel_bytes,
                    file_name=f"tag_scans_all_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_all_saved",
                )
                if delall_col.button(":material/delete_forever: Delete all", key="delete_all_saved"):
                    st.session_state.confirm_delete_all = True

                if st.session_state.confirm_delete_all:
                    st.error("This permanently deletes ALL saved records for everyone. Are you sure?")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes, delete all", type="primary", key="confirm_delete_all_btn"):
                        db.delete_all()
                        sheets_db.delete_all()
                        st.session_state.confirm_delete_all = False
                        if db.fetch_all():  # rows still there -> the delete had no effect
                            st.warning("Delete had no effect — add the delete policy in Supabase (see README).")
                        else:
                            st.toast("All saved records deleted", icon=":material/delete_forever:")
                            st.rerun()
                    if c2.button("No, cancel", key="cancel_delete_all"):
                        st.session_state.confirm_delete_all = False
                        st.rerun()

                st.caption("Delete a single record:")
                for row in rows:
                    igi = row.get("igi_report_no", "")
                    rcol, bcol = st.columns([4, 1])
                    rcol.write(f"{igi} · {row.get('shape') or '—'} · {row.get('carat') or '—'} ct")
                    if bcol.button(":material/delete:", key=f"del_saved_{igi}", help="Delete this record"):
                        db.delete_one(igi)
                        sheets_db.delete_one(igi)
                        st.rerun()

    # --- Saved jewelry records (shared Supabase store) ---
    if db.is_enabled():
        with st.container(border=True):
            header_col, refresh_col = st.columns([3, 1])
            header_col.subheader(":material/cloud: Saved jewelry records (shared)")
            if refresh_col.button(":material/refresh: Refresh", key="refresh_jewelry"):
                st.rerun()
            jewelry_rows = db.fetch_all_jewelry()
            if not jewelry_rows:
                st.caption("No saved records yet (or couldn't reach the database).")
            else:
                jewelry_df = pd.DataFrame(jewelry_rows)
                st.dataframe(jewelry_df, hide_index=True, width="stretch")

                excel_bytes = excel_export.build_excel_bytes(jewelry_df)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dl_col, delall_col = st.columns([3, 1])
                dl_col.download_button(
                    ":material/download: Download all saved jewelry records as Excel",
                    data=excel_bytes,
                    file_name=f"jewelry_scans_all_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_all_jewelry",
                )
                if delall_col.button(":material/delete_forever: Delete all", key="delete_all_jewelry"):
                    st.session_state.confirm_delete_all_jewelry = True

                if st.session_state.confirm_delete_all_jewelry:
                    st.error("This permanently deletes ALL saved jewelry records for everyone. Are you sure?")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes, delete all", type="primary", key="confirm_delete_all_jewelry_btn"):
                        db.delete_all_jewelry()
                        sheets_db.delete_all_jewelry()
                        st.session_state.confirm_delete_all_jewelry = False
                        if db.fetch_all_jewelry():  # rows still there -> the delete had no effect
                            st.warning("Delete had no effect — add the delete policy in Supabase (see README).")
                        else:
                            st.toast("All saved jewelry records deleted", icon=":material/delete_forever:")
                            st.rerun()
                    if c2.button("No, cancel", key="cancel_delete_all_jewelry"):
                        st.session_state.confirm_delete_all_jewelry = False
                        st.rerun()

                st.caption("Delete a single record:")
                for row in jewelry_rows:
                    report_no = row.get("report_no", "")
                    rcol, bcol = st.columns([4, 1])
                    rcol.write(f"{report_no} · {row.get('shape_cut') or '—'} · {row.get('est_weight') or '—'}")
                    if bcol.button(":material/delete:", key=f"del_jewelry_{report_no}", help="Delete this record"):
                        db.delete_one_jewelry(report_no)
                        sheets_db.delete_one_jewelry(report_no)
                        st.rerun()
