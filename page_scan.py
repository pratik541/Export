"""Mobile Scan page: rear one-tap camera -> auto-OCR -> auto-save -> a compact
result card that fits on a phone screen without scrolling to verify the reading.
Falls back to a basic camera if the rear-camera component is unavailable."""
import streamlit as st

import db
import ui_common

try:
    from streamlit_back_camera_input import back_camera_input
    _HAS_BACK_CAM = True
except Exception:  # noqa: BLE001 - component missing/broken -> basic-camera fallback
    back_camera_input = None
    _HAS_BACK_CAM = False


def _capture_widget():
    """Show the camera and return captured image bytes, or None. Prefers the
    rear one-tap camera; falls back to the basic camera if unavailable or if the
    user toggles it. The try/except also makes this safe under AppTest, where the
    custom component has no browser."""
    use_basic = st.toggle(
        "Use basic camera", value=not _HAS_BACK_CAM,
        help="Switch this on if the rear camera doesn't work on your phone.",
    )
    key = f"cam_{st.session_state.camera_gen}"
    if _HAS_BACK_CAM and not use_basic:
        st.caption("Tap the video to snap · fill the frame with the tag · avoid glare")
        try:
            shot = back_camera_input(key=f"back_{key}")
        except Exception:  # noqa: BLE001
            st.warning("Rear camera unavailable here — turn on 'Use basic camera'.")
            return None
        return shot.getvalue() if shot is not None else None
    shot = st.camera_input("Point at the tag and shoot", key=f"basic_{key}")
    return shot.getvalue() if shot is not None else None


def _render_result_card(item):
    st.markdown(f"### {ui_common.item_status(item)}")
    st.image(item["cropped_bytes"], width="stretch")
    r = item.get("ocr_result")
    if r and r.get("accepted"):
        for field, label in ui_common.FIELD_LABELS:
            st.markdown(f"**{label}:** {r.get(field) or '—'}")
    if db.is_enabled():
        saved = item.get("saved_ok")
        if saved is True:
            st.caption("☁ saved to database")
        elif saved is False:
            st.caption("⚠ save failed — kept locally")


def _render_fix(item):
    """Editable fields for a review/failed read. Saving writes the corrected
    values back onto the item's ocr_result and re-runs autosave."""
    r = item.get("ocr_result") or {}
    with st.expander("✏️ Fix this reading"):
        new_vals = {
            field: st.text_input(label, value=r.get(field) or "",
                                 key=f"fix_{item['id']}_{field}")
            for field, label in ui_common.FIELD_LABELS
        }
        if st.button("Save correction", type="primary", key=f"savefix_{item['id']}"):
            updated = dict(r)
            updated.update(new_vals)
            updated["accepted"] = True
            updated["needs_review"] = False
            item["ocr_result"] = updated
            ui_common.autosave(item)
            st.toast("Correction saved", icon=":material/check_circle:")
            st.rerun()


def render():
    st.header(":material/photo_camera: Scan a tag")

    data = _capture_widget()
    if data is not None:
        item = ui_common.add_image(data, f"scan_{st.session_state.next_id}.png", "camera")
        if item is not None:
            with st.spinner("Reading tag..."):
                ui_common.run_ocr(item)
            ui_common.autosave(item)
            st.session_state.camera_gen += 1  # reset camera for the next tag
            st.rerun()

    items = st.session_state.gallery_items
    if not items:
        st.info("Snap a tag — its reading shows here.")
        return

    latest = items[-1]
    _render_result_card(latest)

    r = latest.get("ocr_result")
    if r is None or not r.get("accepted") or r.get("needs_review"):
        _render_fix(latest)

    if st.button(":material/photo_camera: Scan next", type="primary", key="scan_next"):
        st.session_state.camera_gen += 1
        st.rerun()

    st.caption("Open **Manage** (top-left menu) for the full table, export, and saved records.")
